#!/usr/bin/env python3
"""Fetch README content for kept repos only.

Part of the gh-score sub-skill. Downloads READMEs for repos that passed
the description pre-screen (Step 5b), so they can be used for LLM ranking (Step 7a).

Usage:
  python sub-skills/gh-score/src/fetch_readmes.py --kept-list PATH

Reads:  cache/fetched.json + cache/kept.json
Writes: cache/fetched.json (in-place, fills in 'readme' field for kept repos)

Requires: GITHUB_TOKEN environment variable (optional but recommended)
"""

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Navigate up from: sub-skills/gh-score/src/fetch_readmes.py → project root
ROOT = Path(__file__).resolve().parent.parent.parent.parent

MAX_RETRIES = 3
BACKOFF_BASE = 2.0


def _github_request(url: str, headers: dict, retries: int = MAX_RETRIES) -> dict | None:
    """Execute GitHub API request with retry logic."""
    for attempt in range(retries + 1):
        if attempt > 0:
            delay = BACKOFF_BASE ** attempt
            print(f"  Retry {attempt}/{retries} in {delay}s: {url}", file=sys.stderr)
            time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (ssl.SSLError, urllib.error.HTTPError) as e:
            if isinstance(e, ssl.SSLError):
                print(f"  SSL error: {e}", file=sys.stderr)
                continue
            if e.code == 403:
                print(f"  403 rate limit, skipping", file=sys.stderr)
                return None
            if e.code == 404:
                return None  # No README
            if e.code == 422:
                return None
            if e.code >= 500:
                continue
            print(f"  HTTP {e.code}: {url}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            continue
    return None


def fetch_readme(full_name: str, headers: dict) -> str:
    """Fetch and decode README, return plain text or empty string."""
    url = f"https://api.github.com/repos/{full_name}/readme"
    data = _github_request(url, headers)
    if not data:
        return ""
    content = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return content


def get_token() -> str | None:
    """Get GitHub token from environment."""
    return os.environ.get("GITHUB_TOKEN")


def main():
    fetched_path = ROOT / "cache" / "fetched.json"
    kept_path = ROOT / "cache" / "kept.json"

    if not fetched_path.exists():
        print("ERROR: cache/fetched.json not found", file=sys.stderr)
        sys.exit(1)
    if not kept_path.exists():
        print("ERROR: cache/kept.json not found", file=sys.stderr)
        sys.exit(1)

    with open(fetched_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(kept_path, encoding="utf-8") as f:
        kept_repos = json.load(f)

    kept_set = set(kept_repos)
    repos = data.get("repos", [])

    # Build auth headers
    token = get_token()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "gh-finder2/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("[readmes] WARNING: GITHUB_TOKEN not set, using unauthenticated API (60 req/h)", file=sys.stderr)

    # Rate control
    has_token = bool(token)
    request_gap = 0.1 if has_token else 1.0

    # Fetch README for kept repos only
    count = 0
    for i, repo in enumerate(repos):
        name = repo["full_name"]
        if name not in kept_set:
            continue
        
        # Skip if README already fetched
        if repo.get("readme", ""):
            print(f"  [{i+1}/{len(repos)}] {name} ... already has README, skip", file=sys.stderr)
            continue

        print(f"  [{i+1}/{len(repos)}] {name} ... downloading README", file=sys.stderr)
        repo["readme"] = fetch_readme(name, headers)
        count += 1
        time.sleep(request_gap)

    # Write back
    with open(fetched_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[readmes] Done → {count} READMEs downloaded", file=sys.stderr)


if __name__ == "__main__":
    main()
