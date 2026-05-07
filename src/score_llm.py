#!/usr/bin/env python3
"""Step 7a: LLM scoring pipeline.

Standardized workflow for LLM to produce purpose_ranking and fit_ranking
after READMEs have been fetched.

Usage:
  python3 src/score_llm.py prepare   # Output kept repos + READMEs for LLM scoring
  python3 src/score_llm.py merge     # Read LLM scores from stdin, merge into llm_scores.json

Workflow:
  1. Agent runs: `python3 src/score_llm.py prepare` → gets formatted repo + README data
  2. Agent (LLM) scores each kept repo:
     - purpose_score(1-100): relevance to user's intent
     - fit_score(1-100): fit for user's specific scenario
     - reason: brief explanation
  3. Agent feeds scores back to: `python3 src/score_llm.py merge`
  4. Script validates, updates llm_scores.json, ready for validate_llm_scores.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_fetched():
    """Load fetched.json."""
    path = ROOT / "cache" / "fetched.json"
    if not path.exists():
        print("ERROR: cache/fetched.json not found", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_kept():
    """Load kept.json."""
    path = ROOT / "cache" / "kept.json"
    if not path.exists():
        print("ERROR: cache/kept.json not found", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_llm_scores():
    """Load existing llm_scores.json or create empty."""
    path = ROOT / "cache" / "llm_scores.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_llm_scores(data):
    """Save llm_scores.json."""
    path = ROOT / "cache" / "llm_scores.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def prepare() -> None:
    """Print formatted repo + README data for LLM scoring."""
    fetched = load_fetched()
    kept_list = load_kept()
    intent_path = ROOT / "cache" / "intent.json"

    if not intent_path.exists():
        print("ERROR: cache/intent.json not found", file=sys.stderr)
        sys.exit(1)
    with open(intent_path, encoding="utf-8") as f:
        intent = json.load(f)

    intent_summary = intent.get("intent", {}).get("summary", "unknown")
    repos = {r["full_name"]: r for r in fetched.get("repos", [])}

    print(f"=== INTENT ===")
    print(intent_summary)
    print(f"\n=== SCORING SETTINGS ===")
    print(f"Kept repos: {len(kept_list)}")
    print(f"Score each repo on two dimensions (1-100):")
    print(f"  purpose: relevance to user's intent")
    print(f"  fit: fit for user's specific scenario")
    print(f"\n=== REPOS (respond with scoring JSON) ===")
    print(f'Format: JSON array of {{"full_name": "...", "purpose_score": N, "fit_score": N, "reason": "..."}}')
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
    """Read LLM scoring from stdin, merge into llm_scores.json."""
    kept_list = load_kept()
    llm_scores = load_llm_scores()

    raw_input = sys.stdin.read().strip()
    if not raw_input:
        print("ERROR: No scoring input from stdin", file=sys.stderr)
        sys.exit(1)

    try:
        scoring = json.loads(raw_input)
    except json.JSONDecodeError:
        print("ERROR: Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    if not isinstance(scoring, list):
        print("ERROR: Scoring must be a JSON array", file=sys.stderr)
        sys.exit(1)

    # Validate entries
    kept_set = set(kept_list)
    errors = []
    purpose_ranking = []
    fit_ranking = []

    for entry in scoring:
        if not isinstance(entry, dict):
            errors.append(f"Entry must be object: {entry}")
            continue

        name = entry.get("full_name", "")
        if name not in kept_set:
            errors.append(f"Unknown repo: {name}")
            continue

        purpose = entry.get("purpose_score", 50)
        fit = entry.get("fit_score", 50)
        reason = entry.get("reason", "")

        purpose_ranking.append({
            "full_name": name,
            "rank": purpose,  # Will be sorted later
            "score": purpose,
            "reason": reason,
        })
        fit_ranking.append({
            "full_name": name,
            "rank": fit,  # Will be sorted later
            "score": fit,
            "reason": reason,
        })

    if errors:
        for e in errors:
            print(f"  WARN: {e}", file=sys.stderr)

    # Sort by score descending (highest = rank 1)
    purpose_ranking.sort(key=lambda x: x.get("score", 50), reverse=True)
    fit_ranking.sort(key=lambda x: x.get("score", 50), reverse=True)

    # Assign ranks
    for i, entry in enumerate(purpose_ranking, 1):
        entry["rank"] = i
        entry.pop("score", None)

    for i, entry in enumerate(fit_ranking, 1):
        entry["rank"] = i
        entry.pop("score", None)

    # Update llm_scores.json (preserve existing keys)
    llm_scores["purpose_ranking"] = purpose_ranking
    llm_scores["fit_ranking"] = fit_ranking
    
    # Re-merge kept_for_scoring if missing (from prescreen stage)
    if "kept_for_scoring" not in llm_scores:
        llm_scores["kept_for_scoring"] = kept_list
    
    # Add prescreen_ranking if missing (fallback: same as purpose for kept repos)
    if "prescreen_ranking" not in llm_scores:
        llm_scores["prescreen_ranking"] = [
            {"full_name": name, "rank": i + 1, "reason": "Pre-screened by description relevance"}
            for i, name in enumerate(kept_list)
        ]

    save_llm_scores(llm_scores)

    print(f"✅ LLM scores merged into llm_scores.json", file=sys.stderr)
    print(f"   purpose_ranking: {len(purpose_ranking)} repos", file=sys.stderr)
    print(f"   fit_ranking: {len(fit_ranking)} repos", file=sys.stderr)
    
    # Show top 3
    if purpose_ranking:
        print(f"\n   Top 3 by purpose:", file=sys.stderr)
        for entry in purpose_ranking[:3]:
            print(f"     #{entry['rank']} {entry['full_name']}: {entry['reason'][:80]}", file=sys.stderr)


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
