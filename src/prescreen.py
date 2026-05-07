#!/usr/bin/env python3
"""Step 5b: Pre-screen repos by description relevance.

Usage:
  python src/prescreen.py prepare    # Output descriptions to stdout for LLM ranking
  python src/prescreen.py rank       # Read LLM ranking from stdin, validate, write kept.json
  python src/prescreen.py --help     # Show usage

Workflow:
  1. Agent runs: `python src/prescreen.py prepare` → gets formatted repo list
  2. Agent (LLM) ranks by relevance to intent.summary
  3. Agent feeds ranking back via stdin or pipe to: `python src/prescreen.py rank`
  4. Script validates format, applies prescreen_keep_ratio, writes kept.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    """Load scoring config for prescreen_keep_ratio."""
    cfg_path = ROOT / "config" / "scoring.json"
    with open(cfg_path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("scoring", {}).get("prescreen_keep_ratio", 0.5)


def prepare() -> None:
    """Print formatted repo descriptions for LLM pre-screening."""
    fetched_path = ROOT / "cache" / "fetched.json"
    intent_path = ROOT / "cache" / "intent.json"

    if not fetched_path.exists():
        print("ERROR: cache/fetched.json not found", file=sys.stderr)
        sys.exit(1)
    if not intent_path.exists():
        print("ERROR: cache/intent.json not found", file=sys.stderr)
        sys.exit(1)

    with open(fetched_path, encoding="utf-8") as f:
        fetched = json.load(f)
    with open(intent_path, encoding="utf-8") as f:
        intent = json.load(f)

    repos = fetched.get("repos", [])
    seeds = set(fetched.get("seed_repo_names", []))
    intent_summary = intent.get("intent", {}).get("summary", "unknown")
    keep_ratio = load_config()
    keep_count = max(int(len(repos) * keep_ratio), 1)

    print(f"=== INTENT ===")
    print(intent_summary)
    print(f"\n=== PRESCREEN SETTINGS ===")
    print(f"Total repos: {len(repos)}")
    print(f"Keep ratio: {keep_ratio} → top {keep_count} + seeds")
    print(f"Seeds: {sorted(seeds)}")
    print(f"\n=== REPOS (respond with ranked full_name list) ===")
    print(f"Format: full_name:relevance_score(1-100):reason")
    print()

    for i, r in enumerate(repos, 1):
        name = r["full_name"]
        desc = r.get("description", "") or "[NO DESCRIPTION]"
        stars = r["metrics"]["stars"]
        lang = r["metrics"]["language"] or "N/A"
        is_seed = "SEED" if name in seeds else ""
        print(f"{i:2d}. {name} ({stars}⭐, {lang}) {is_seed}")
        print(f"    {desc[:150]}")


def rank() -> None:
    """Read LLM ranking from stdin, validate, write kept.json."""
    fetched_path = ROOT / "cache" / "fetched.json"

    with open(fetched_path, encoding="utf-8") as f:
        fetched = json.load(f)

    seeds = set(fetched.get("seed_repo_names", []))
    all_names = {r["full_name"] for r in fetched.get("repos", [])}
    keep_ratio = load_config()
    keep_count = max(int(len(fetched["repos"]) * keep_ratio), 1)

    # Read ranking from stdin
    raw_input = sys.stdin.read().strip()
    if not raw_input:
        print("ERROR: No ranking input from stdin", file=sys.stderr)
        sys.exit(1)

    # Parse ranking: expect JSON array of {full_name, rank, reason, score}
    try:
        ranking = json.loads(raw_input)
    except json.JSONDecodeError:
        # Fallback: parse line-by-line "full_name:score:reason"
        ranking = []
        for line in raw_input.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("==="):
                continue
            parts = line.split(":", 2)
            if len(parts) >= 2:
                ranking.append({
                    "full_name": parts[0].strip(),
                    "rank": len(ranking) + 1,
                    "score": int(parts[1].strip()) if parts[1].strip().isdigit() else 50,
                    "reason": parts[2].strip() if len(parts) > 2 else "",
                })

    if not isinstance(ranking, list):
        print("ERROR: Ranking must be a JSON array", file=sys.stderr)
        sys.exit(1)

    # Validate entries
    errors = []
    for entry in ranking:
        if not isinstance(entry, dict):
            errors.append(f"Entry must be object: {entry}")
            continue
        if "full_name" not in entry:
            errors.append(f"Entry missing 'full_name': {entry}")
        elif entry["full_name"] not in all_names:
            errors.append(f"Unknown repo: {entry['full_name']}")

    if errors:
        for e in errors:
            print(f"  WARN: {e}", file=sys.stderr)
        # Don't fail — just log warnings

    # Sort by rank (or score if rank missing)
    ranking.sort(key=lambda x: x.get("rank", x.get("score", 50)))

    # Extract kept repos: top N + seeds
    top_names = [e["full_name"] for e in ranking[:keep_count]]
    kept_set = set(top_names) | seeds
    kept_list = sorted(kept_set)

    # Write kept.json
    kept_path = ROOT / "cache" / "kept.json"
    kept_path.parent.mkdir(parents=True, exist_ok=True)
    with open(kept_path, "w", encoding="utf-8") as f:
        json.dump(kept_list, f, indent=2)

    # Write prescreen_ranking for llm_scores.json
    prescreen_ranking = []
    for i, e in enumerate(ranking, 1):
        prescreen_ranking.append({
            "full_name": e["full_name"],
            "rank": e.get("rank", i),
            "reason": e.get("reason", ""),
        })

    llm_scores_path = ROOT / "cache" / "llm_scores.json"
    if llm_scores_path.exists():
        with open(llm_scores_path, encoding="utf-8") as f:
            llm_scores = json.load(f)
    else:
        llm_scores = {}

    llm_scores["prescreen_ranking"] = prescreen_ranking
    llm_scores["kept_for_scoring"] = kept_list

    with open(llm_scores_path, "w", encoding="utf-8") as f:
        json.dump(llm_scores, f, indent=2)

    print(f"✅ Pre-screen complete", file=sys.stderr)
    print(f"   Kept: {len(kept_list)} repos (top {keep_count} + {len(seeds)} seeds)", file=sys.stderr)
    for name in kept_list:
        is_seed = "🌱" if name in seeds else "  "
        print(f"   {is_seed} {name}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "prepare":
        prepare()
    elif cmd == "rank":
        rank()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
