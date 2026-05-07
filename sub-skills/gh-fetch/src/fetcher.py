#!/usr/bin/env python3
"""Fetch GitHub repos via Search API, grab READMEs + releases, write structured JSON.

Usage: python sub-skills/gh-fetch/src/fetcher.py

Reads:  cache/intent.json
Writes: cache/fetched.json

Requires: GITHUB_TOKEN environment variable
"""

import argparse
import base64
import json
import os
import subprocess
import time
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# ─── Config ──────────────────────────────────────────────────────────

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from common import ROOT, Config

config = Config.load()

QUERY_PATH = config.path("query")
OUTPUT_PATH = config.path("fetched")

PER_PAGE = config.fetch.get("per_page", 30)
MIN_STARS = config.fetch.get("min_stars", 2)
MAX_RETRIES = config.fetch.get("max_retries", 3)
BACKOFF_BASE = 2.0
REQUEST_GAP = config.fetch.get("request_gap_with_token", 0.1) if os.environ.get("GITHUB_TOKEN") else config.fetch.get("request_gap_without_token", 1.0)

# Per-type result limits
TYPE_LIMITS = {
    "exact": config.fetch.get("exact_limit", 5),
    "websearch": config.fetch.get("websearch_limit", 5),
    "semantic": config.fetch.get("semantic_limit", 5),
    "complexity": config.fetch.get("complexity_limit", 3),
}

# ─── Helpers ─────────────────────────────────────────────────────────


def _iso_days_since(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except (ValueError, TypeError):
        return None


def _github_request(url: str, headers: dict, retries: int = MAX_RETRIES) -> Optional[dict]:
    for attempt in range(retries + 1):
        if attempt > 0:
            delay = BACKOFF_BASE ** attempt
            print(f"[fetch] Retry {attempt}/{retries} in {delay}s: {url}", file=sys.stderr)
            time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (ssl.SSLError, urllib.error.HTTPError) as e:
            if isinstance(e, ssl.SSLError):
                print(f"[fetch] SSL error: {e}: {url}", file=sys.stderr)
                continue  # Retry on SSL errors
            if e.code == 403:
                print(f"[fetch] 403 rate limit: {url}, skipping", file=sys.stderr)
                return None  # Don't retry — rate limit won't lift instantly
            if e.code == 422:
                return None  # Invalid query, skip
            if e.code >= 500:
                continue  # Server error, retry
            print(f"[fetch] HTTP {e.code}: {url}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[fetch] Error: {e}: {url}", file=sys.stderr)
            continue
    return None


# ─── Fetch layers ────────────────────────────────────────────────────


def search_repos(query: str, headers: dict) -> list[dict]:
    """Execute GitHub Search API query, return items list."""
    q = f"{query} stars:>{MIN_STARS - 1}"
    url = (
        f"https://api.github.com/search/repositories?"
        f"q={urllib.parse.quote(q)}&per_page={PER_PAGE}"
        f"&sort=stars&order=desc"
    )
    data = _github_request(url, headers)
    if not data:
        return []
    return data.get("items", [])


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


def fetch_releases(full_name: str, headers: dict) -> dict:
    """Fetch latest release info and total count."""
    # Get total count from header
    url = f"https://api.github.com/repos/{full_name}/releases?per_page=1&page=1"
    req = urllib.request.Request(url, headers=headers)
    total_count = 0
    items = []
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            # Link header has total info, but we parse the body instead
            items = json.loads(resp.read().decode("utf-8"))
            # Try to get total from Link header or first page size
            link = resp.headers.get("Link", "")
            if link:
                # Parse last page number from Link header for total
                import re
                pages = re.findall(r'page=(\d+)', link)
                if pages:
                    total_count = int(pages[-1])
                else:
                    total_count = len(items)
            else:
                total_count = len(items)
    except Exception:
        pass

    if not items:
        return {
            "has_releases": False,
            "total_releases": total_count,
            "latest_release": None,
            "published_at": None,
            "days_since_last_release": None,
        }

    latest = items[0]
    published = latest.get("published_at")
    return {
        "has_releases": True,
        "total_releases": total_count,
        "latest_release": latest.get("tag_name") or latest.get("name"),
        "published_at": published,
        "days_since_last_release": _iso_days_since(published),
    }


# ─── Repo parsing ────────────────────────────────────────────────────


def parse_repo(full_name: str, raw: dict, headers: dict, idx: int, total: int,
               with_readme: bool = True) -> dict:
    """Convert raw Search API item into structured dict per SKILL.md spec."""
    pushed_at = raw.get("pushed_at")
    updated_at = raw.get("updated_at")

    sys.stderr.write(f"  [{idx}/{total}] {full_name} ... ")
    sys.stderr.flush()

    readme_text = ""
    if with_readme:
        readme_text = fetch_readme(full_name, headers)
        sys.stderr.write(f"README {len(readme_text)} chars, ")
        sys.stderr.flush()
        time.sleep(REQUEST_GAP)
    else:
        sys.stderr.write("metadata only, ")
        sys.stderr.flush()

    releases = fetch_releases(full_name, headers)
    has_rel = releases["has_releases"]
    sys.stderr.write(f"releases={has_rel}\n")
    sys.stderr.flush()
    time.sleep(REQUEST_GAP)

    return {
        "full_name": full_name,
        "html_url": raw["html_url"],
        "description": raw.get("description") or "",
        "search_score": round(raw.get("score", 0), 1),
        "owner": {
            "login": raw.get("owner", {}).get("login", ""),
            "type": raw.get("owner", {}).get("type", "User"),
        },
        "metrics": {
            "stars": raw.get("stargazers_count", 0),
            "forks": raw.get("forks_count", 0),
            "watchers": raw.get("watchers_count", 0),
            "open_issues": raw.get("open_issues_count", 0),
            "language": raw.get("language"),
            "is_archived": raw.get("archived", False),
            "is_fork": raw.get("fork", False),
            "license_key": (raw.get("license") or {}).get("spdx_id"),
            "topics": raw.get("topics") or [],
        },
        "activity": {
            "pushed_at": pushed_at,
            "created_at": raw.get("created_at"),
            "updated_at": updated_at,
            "days_since_last_push": _iso_days_since(pushed_at),
            "default_branch": raw.get("default_branch") or "main",
        },
        "releases": releases,
        "readme": readme_text,
    }


# ─── Main ────────────────────────────────────────────────────────────


def _get_token() -> Optional[str]:
    """Get GitHub token: env var first, then gh CLI fallback."""
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    # Dev fallback: try gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub repos and READMEs.")
    parser.add_argument("--readmes-only", action="store_true", help="Skip search; only download READMEs for kept repos.")
    parser.add_argument("--kept-list", type=str, help="Path to JSON file with list of repo full_names to fetch READMEs for.")
    args = parser.parse_args()

    token = _get_token()
    if not token:
        print("[fetch] WARNING: GITHUB_TOKEN not set, using unauthenticated API (60 req/h limit)", file=sys.stderr)

    if not QUERY_PATH.exists() and not args.readmes_only:
        print(f"[fetch] ERROR: {QUERY_PATH} not found", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "gh-finder2/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if args.readmes_only:
        if not args.kept_list or not os.path.exists(args.kept_list):
            print("[fetch] ERROR: --kept-list required with --readmes-only", file=sys.stderr)
            sys.exit(1)
        with open(args.kept_list, "r", encoding="utf-8") as f:
            kept_repos = json.load(f)
        
        if not OUTPUT_PATH.exists():
            print("[fetch] ERROR: fetched.json not found", file=sys.stderr)
            sys.exit(1)
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        repos = data.get("repos", [])
        kept_set = set(kept_repos)
        
        for i, repo in enumerate(repos):
            if repo["full_name"] in kept_set:
                print(f"[fetch] Downloading README for {repo['full_name']} ({i+1}/{len(repos)})", file=sys.stderr)
                repo["readme"] = fetch_readme(repo["full_name"], headers)
                time.sleep(REQUEST_GAP)
            else:
                print(f"[fetch] Skipping {repo['full_name']} (not in kept list)", file=sys.stderr)
        
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[fetch] Done → {OUTPUT_PATH} (READMEs downloaded for kept repos)", file=sys.stderr)
        return

    with open(QUERY_PATH, "r", encoding="utf-8") as f:
        intent = json.load(f)

    queries = intent.get("queries", [])
    if not queries:
        print("[fetch] ERROR: no queries in intent.json", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "gh-finder2/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    seen: dict[str, dict] = {}
    seed_repos: set[str] = set()
    warnings: list[str] = []

    for i, q_obj in enumerate(queries, 1):
        query = q_obj["query"]
        q_type = q_obj.get("type", "semantic")
        print(f"[fetch] Query {i}/{len(queries)}: {query} ({q_type})", file=sys.stderr)
        items = search_repos(query, headers)
        # Limit results by query type (configured in config/scoring.json)
        limit = TYPE_LIMITS.get(q_type, 30)
        items = items[:limit]
        print(f"[fetch]   → {len(items)} results", file=sys.stderr)

        # Validate exact/websearch queries: first result must contain the query name
        if q_type in ("exact", "websearch") and items:
            first_name = items[0].get("full_name", "")
            if query.lower() not in first_name.lower():
                warn = f"{q_type} query '{query}' → first result is '{first_name}', doesn't match"
                print(f"[fetch] WARN: {warn}", file=sys.stderr)
                warnings.append(warn)
                # Don't seed — the expected project wasn't found

        for j, item in enumerate(items):
            full_name = item.get("full_name", "")
            if not full_name or full_name in seen:
                continue
            seen[full_name] = item

            # First result of every query → seed (skip if exact/websearch query validation failed)
            if j == 0 and query.lower() in first_name.lower() if q_type in ("exact", "websearch") else True:
                seed_repos.add(full_name)

        time.sleep(REQUEST_GAP)

    print(f"[fetch] {len(seen)} unique repos, fetching metadata (Stage 1: no READMEs)...", file=sys.stderr)

    repos = []
    for i, (name, raw) in enumerate(seen.items(), 1):
        repo = parse_repo(name, raw, headers, i, len(seen), with_readme=False)
        repos.append(repo)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "seed_repo_names": sorted(seed_repos),
        "repos": repos,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[fetch] Done → {OUTPUT_PATH} ({len(repos)} repos, {len(seed_repos)} seeds)", file=sys.stderr)


if __name__ == "__main__":
    main()
