#!/usr/bin/env python3
"""Step 7a: LLM ranking for purpose and fit dimensions.

Standardized workflow: LLM ranks kept repos based on README content.
LLM only provides ORDER — Python assigns rank by position.

Usage:
  python sub-skills/gh-score/src/rank_readme.py prepare   # Output kept repos + READMEs for LLM ranking
  python sub-skills/gh-score/src/rank_readme.py merge     # Read LLM orderings from stdin, merge into llm_scores.json
"""

import json
import sys
from pathlib import Path

# Navigate up from: sub-skills/gh-score/src/rank_readme.py → project root
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from common import Config

config = Config.load()


def load_fetched():
    """Load fetched.json."""
    path = config.path("fetched")
    if not path.exists():
        print("ERROR: cache/fetched.json not found", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_kept():
    """Load kept.json."""
    path = config.path("kept")
    if not path.exists():
        print("ERROR: cache/kept.json not found", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_llm_scores():
    """Load existing llm_scores.json or create empty."""
    path = config.path("llm_scores")
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_llm_scores(data):
    """Save llm_scores.json."""
    path = config.path("llm_scores")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def prepare() -> None:
    """Print formatted repo + README data for LLM ranking."""
    fetched = load_fetched()
    kept_list = load_kept()
    intent_path = config.path("intent")

    if not intent_path.exists():
        print("ERROR: cache/intent.json not found", file=sys.stderr)
        sys.exit(1)
    with open(intent_path, encoding="utf-8") as f:
        intent = json.load(f)

    intent_summary = intent.get("intent", {}).get("summary", "unknown")
    repos = {r["full_name"]: r for r in fetched.get("repos", [])}

    print(f"=== INTENT ===")
    print(intent_summary)
    print(f"\n=== RANKING SETTINGS ===")
    print(f"Kept repos: {len(kept_list)}")
    print(f"Provide TWO ordered lists (no scores):")
    print(f"  purpose_order: most→least relevant to user's intent")
    print(f"  fit_order: best→worst fit for user's specific scenario")
    print(f"\n=== REPOS (respond with ordering JSON) ===")
    print(f'Format: {{"purpose_order": [...], "fit_order": [...], "reasons": {{"repo": "explanation"}}}}')
    print()

    for name in kept_list:
        repo = repos.get(name)
        if not repo:
            print(f"  [MISSING] {name}")
            continue

        desc = repo.get("description", "") or "[NO DESCRIPTION]"
        readme = repo.get("readme", "") or "[NO README]"
        stars = repo["metrics"]["stars"]
        lang = repo["metrics"]["language"] or "N/A"

        # Truncate README for display (first 500 chars)
        readme_preview = readme[:500]
        if len(readme) > 500:
            readme_preview += f"\n  [... truncated, {len(readme) - 500} more chars ...]"

        print(f"\n--- {name} ({stars}⭐, {lang}) ---")
        print(f"Description: {desc[:150]}")
        print(f"README preview:")
        print(readme_preview)


def merge() -> None:
    """Read LLM orderings from stdin, merge into llm_scores.json.

    LLM only provides ORDER — Python assigns rank by position.

    Expected input format:
    {
      "purpose_order": ["repo-a", "repo-b", ...],  // most→least relevant to intent
      "fit_order": ["repo-c", "repo-d", ...],       // best→worst fit for scenario
      "reasons": {"repo-a": "...", "repo-b": "..."} // optional reasons per repo
    }
    """
    kept_list = load_kept()
    llm_scores = load_llm_scores()
    kept_set = set(kept_list)

    raw_input = sys.stdin.read().strip()
    if not raw_input:
        print("ERROR: No ranking input from stdin", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError:
        # Fallback: try parsing as list of names (purpose order only)
        try:
            names = json.loads(raw_input)
            data = {"purpose_order": names, "fit_order": names, "reasons": {}}
        except json.JSONDecodeError:
            print("ERROR: Invalid JSON input. Expected {\"purpose_order\": [...], \"fit_order\": [...]}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(data, dict):
        print("ERROR: Input must be a JSON object", file=sys.stderr)
        sys.exit(1)

    purpose_order = data.get("purpose_order", [])
    fit_order = data.get("fit_order", [])
    reasons = data.get("reasons", {})

    if not isinstance(purpose_order, list) or not purpose_order:
        print("ERROR: purpose_order must be a non-empty list", file=sys.stderr)
        sys.exit(1)
    if not isinstance(fit_order, list) or not fit_order:
        print("ERROR: fit_order must be a non-empty list", file=sys.stderr)
        sys.exit(1)

    # Validate names
    errors = []
    purpose_valid = [n for n in purpose_order if n in kept_set]
    fit_valid = [n for n in fit_order if n in kept_set]

    for name in purpose_order:
        if name not in kept_set:
            errors.append(f"purpose_order: unknown repo '{name}'")
    for name in fit_order:
        if name not in kept_set:
            errors.append(f"fit_order: unknown repo '{name}'")

    # Add missing kept repos at the end
    for name in kept_list:
        if name not in purpose_valid:
            purpose_valid.append(name)
            errors.append(f"purpose_order: missing '{name}', added at end")
        if name not in fit_valid:
            fit_valid.append(name)
            errors.append(f"fit_order: missing '{name}', added at end")

    if errors:
        for e in errors:
            print(f"  WARN: {e}", file=sys.stderr)

    # Build rankings: position in list = rank (1-based)
    purpose_ranking = []
    for rank, name in enumerate(purpose_valid, 1):
        purpose_ranking.append({
            "full_name": name,
            "rank": rank,
            "reason": reasons.get(name, ""),
        })

    fit_ranking = []
    for rank, name in enumerate(fit_valid, 1):
        fit_ranking.append({
            "full_name": name,
            "rank": rank,
            "reason": reasons.get(name, ""),
        })

    # Update llm_scores.json (preserve existing keys)
    llm_scores["purpose_ranking"] = purpose_ranking
    llm_scores["fit_ranking"] = fit_ranking

    # Re-merge kept_for_scoring if missing (from prescreen stage)
    if "kept_for_scoring" not in llm_scores:
        llm_scores["kept_for_scoring"] = kept_list

    # Add prescreen_ranking if missing (fallback)
    if "prescreen_ranking" not in llm_scores:
        llm_scores["prescreen_ranking"] = [
            {"full_name": name, "rank": i + 1, "reason": "Pre-screened by description relevance"}
            for i, name in enumerate(kept_list)
        ]

    save_llm_scores(llm_scores)

    print(f"✅ LLM rankings merged into llm_scores.json", file=sys.stderr)
    print(f"   purpose_ranking: {len(purpose_ranking)} repos", file=sys.stderr)
    print(f"   fit_ranking: {len(fit_ranking)} repos", file=sys.stderr)
    
    if purpose_ranking:
        print(f"\n   Top 3 by purpose:", file=sys.stderr)
        for entry in purpose_ranking[:3]:
            reason = entry["reason"][:80] if entry["reason"] else ""
            print(f"     #{entry['rank']} {entry['full_name']}: {reason}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "prepare":
        prepare()
    elif cmd == "merge":
        merge()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
