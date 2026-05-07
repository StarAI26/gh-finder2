#!/usr/bin/env python3
"""Validate llm_scores.json completeness before scorer.py runs.

Ensures llm_scores.json has ALL four required keys:
- prescreen_ranking
- kept_for_scoring
- purpose_ranking
- fit_ranking

Usage:
  python sub-skills/gh-score/src/validate_scores.py
  python sub-skills/gh-score/src/validate_scores.py --generate  # Generate template with placeholder rankings
"""

import json
import sys
from pathlib import Path

# Navigate up from: sub-skills/gh-score/src/validate_scores.py → project root
ROOT = Path(__file__).resolve().parent.parent.parent.parent

REQUIRED_KEYS = ["prescreen_ranking", "kept_for_scoring", "purpose_ranking", "fit_ranking"]


def validate() -> list[str]:
    """Validate llm_scores.json has all required fields."""
    path = ROOT / "cache" / "llm_scores.json"
    errors = []

    if not path.exists():
        return ["cache/llm_scores.json not found — run rank_description.py rank first"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    # Check required keys
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: '{key}'")

    if errors:
        return errors

    # Validate prescreen_ranking
    ps = data["prescreen_ranking"]
    if not isinstance(ps, list) or len(ps) < 1:
        errors.append("prescreen_ranking must be a non-empty array")
    else:
        for i, entry in enumerate(ps):
            if not isinstance(entry, dict):
                errors.append(f"prescreen_ranking[{i}] must be an object")
            elif "full_name" not in entry:
                errors.append(f"prescreen_ranking[{i}] missing 'full_name'")

    # Validate kept_for_scoring
    kept = data["kept_for_scoring"]
    if not isinstance(kept, list) or len(kept) < 1:
        errors.append("kept_for_scoring must be a non-empty array")

    # Validate purpose_ranking
    pr = data["purpose_ranking"]
    if not isinstance(pr, list) or len(pr) < 1:
        errors.append("purpose_ranking must be a non-empty array")
    else:
        for i, entry in enumerate(pr):
            if not isinstance(entry, dict):
                errors.append(f"purpose_ranking[{i}] must be an object")
            elif "full_name" not in entry:
                errors.append(f"purpose_ranking[{i}] missing 'full_name'")
            elif "rank" not in entry:
                errors.append(f"purpose_ranking[{i}] missing 'rank'")

    # Validate fit_ranking
    fr = data["fit_ranking"]
    if not isinstance(fr, list) or len(fr) < 1:
        errors.append("fit_ranking must be a non-empty array")
    else:
        for i, entry in enumerate(fr):
            if not isinstance(entry, dict):
                errors.append(f"fit_ranking[{i}] must be an object")
            elif "full_name" not in entry:
                errors.append(f"fit_ranking[{i}] missing 'full_name'")
            elif "rank" not in entry:
                errors.append(f"fit_ranking[{i}] missing 'rank'")

    # Cross-check: all kept repos should appear in purpose and fit rankings
    if kept and pr and fr:
        kept_set = set(kept)
        purpose_names = {e.get("full_name") for e in pr if isinstance(e, dict)}
        fit_names = {e.get("full_name") for e in fr if isinstance(e, dict)}

        missing_purpose = kept_set - purpose_names
        missing_fit = kept_set - fit_names

        if missing_purpose:
            errors.append(f"kept repos missing from purpose_ranking: {sorted(missing_purpose)}")
        if missing_fit:
            errors.append(f"kept repos missing from fit_ranking: {sorted(missing_fit)}")

    return errors


def generate_template():
    """Generate a template llm_scores.json with all required keys."""
    fetched_path = ROOT / "cache" / "fetched.json"
    if not fetched_path.exists():
        print("ERROR: cache/fetched.json not found", file=sys.stderr)
        sys.exit(1)

    with open(fetched_path, encoding="utf-8") as f:
        fetched = json.load(f)

    repos = fetched.get("repos", [])
    seeds = fetched.get("seed_repo_names", [])

    # Create template with placeholder rankings
    template = {
        "prescreen_ranking": [
            {"full_name": r["full_name"], "rank": i + 1, "reason": "TBD: assess relevance to intent"}
            for i, r in enumerate(repos)
        ],
        "kept_for_scoring": [r["full_name"] for r in repos[:len(repos) // 2 + 1]] + seeds,
        "purpose_ranking": [
            {"full_name": r["full_name"], "rank": i + 1, "reason": "TBD: assess purpose fit"}
            for i, r in enumerate(repos)
        ],
        "fit_ranking": [
            {"full_name": r["full_name"], "rank": i + 1, "reason": "TBD: assess scenario fit"}
            for i, r in enumerate(repos)
        ],
    }

    path = ROOT / "cache" / "llm_scores.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)

    print(f"✅ Template generated: {path}", file=sys.stderr)
    print(f"   {len(template['prescreen_ranking'])} repos in prescreen_ranking", file=sys.stderr)
    print(f"   {len(template['kept_for_scoring'])} repos in kept_for_scoring", file=sys.stderr)
    print(f"   {len(template['purpose_ranking'])} repos in purpose_ranking", file=sys.stderr)
    print(f"   {len(template['fit_ranking'])} repos in fit_ranking", file=sys.stderr)


def main():
    if "--generate" in sys.argv:
        generate_template()
        return

    errors = validate()
    if errors:
        for e in errors:
            print(f"  FAIL: {e}", file=sys.stderr)
        print(f"\nValidation FAILED: {len(errors)} error(s)", file=sys.stderr)
        sys.exit(1)
    else:
        print("Validation PASSED: llm_scores", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
