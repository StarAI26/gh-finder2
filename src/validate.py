#!/usr/bin/env python3
"""Validate gh-finder2 output files from each stage.

Usage: python src/validate.py <stage>
  stage: intents | fetch | score

Exits 0 on success, 1 on failure with error details to stderr.
"""

import json
import sys

from common import ROOT


def validate_intents() -> list[str]:
    """Validate gh-intents output."""
    path = ROOT / "cache" / "intent.json"
    errors = []

    if not path.exists():
        return ["cache/intent.json not found"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    intent = data.get("intent", {})
    if not intent.get("summary"):
        errors.append("intent.summary is empty or missing")
    if "constraints" not in intent:
        errors.append("intent.constraints is missing")
    if "insights" not in intent:
        errors.append("intent.insights is missing")

    queries = data.get("queries", [])
    if not isinstance(queries, list) or len(queries) < 1:
        errors.append("queries must be a non-empty list")
    else:
        for i, q in enumerate(queries):
            if "query" not in q:
                errors.append(f"queries[{i}] missing 'query'")
            elif len(q["query"].split()) > 3:
                errors.append(f"queries[{i}].query has >3 words: '{q['query']}'")
            if "reason" not in q:
                errors.append(f"queries[{i}] missing 'reason'")
            elif not q.get("reason"):
                errors.append(f"queries[{i}].reason is empty")

    return errors


def validate_fetch() -> list[str]:
    """Validate gh-fetch output."""
    path = ROOT / "cache" / "fetched.json"
    errors = []

    if not path.exists():
        return ["cache/fetched.json not found"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    if not isinstance(data, dict):
        return ["fetched.json must be an object with 'seed_repo_names' and 'repos'"]
    if "repos" not in data or not isinstance(data["repos"], list) or len(data["repos"]) < 1:
        return ["fetched.json must have 'repos' array with ≥1 element"]
    if "seed_repo_names" not in data or not isinstance(data["seed_repo_names"], list):
        return ["fetched.json must have 'seed_repo_names' array"]

    required = ["full_name", "html_url", "description", "search_score", "owner", "metrics", "activity", "releases", "readme"]
    owner_keys = ["login", "type"]
    metrics_keys = ["stars", "forks", "watchers", "open_issues", "language", "is_archived", "is_fork", "license_key", "topics"]
    activity_keys = ["pushed_at", "created_at", "updated_at", "days_since_last_push", "default_branch"]
    releases_keys = ["has_releases", "total_releases", "latest_release", "published_at", "days_since_last_release"]

    repos = data["repos"]
    seen: set[str] = set()
    for i, r in enumerate(repos):
        name = r.get("full_name", f"[index {i}]")
        seen.add(name)

        for k in required:
            if k not in r:
                errors.append(f"{name}: missing '{k}'")
        for k in owner_keys:
            if k not in r.get("owner", {}):
                errors.append(f"{name}: missing owner.'{k}'")
        for k in metrics_keys:
            if k not in r.get("metrics", {}):
                errors.append(f"{name}: missing metrics.'{k}'")
        for k in activity_keys:
            if k not in r.get("activity", {}):
                errors.append(f"{name}: missing activity.'{k}'")
        for k in releases_keys:
            if k not in r.get("releases", {}):
                errors.append(f"{name}: missing releases.'{k}'")

        stars = r.get("metrics", {}).get("stars")
        if stars is not None and (not isinstance(stars, int) or stars < 0):
            errors.append(f"{name}: metrics.stars must be int >= 0")

    if len(seen) != len(repos):
        errors.append(f"duplicate full_name found: {len(repos)} repos but {len(seen)} unique")

    # Check all seeds exist in repos
    for seed in data.get("seed_repo_names", []):
        if seed not in seen:
            errors.append(f"seed '{seed}' not found in repos array")

    return errors


def validate_score() -> list[str]:
    """Validate gh-score output."""
    path = ROOT / "cache" / "scored.json"
    if not path.exists():
        return ["cache/scored.json not found (gh-score not run yet)"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return ["scored.json must be an array"]
        return []
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]


STAGES = {
    "intents": validate_intents,
    "fetch": validate_fetch,
    "score": validate_score,
}


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python validate.py <{'|'.join(STAGES)}>", file=sys.stderr)
        sys.exit(1)

    stage = sys.argv[1]
    if stage not in STAGES:
        print(f"Unknown stage: {stage}", file=sys.stderr)
        sys.exit(1)

    errors = STAGES[stage]()
    if errors:
        for e in errors:
            print(f"  FAIL: {e}", file=sys.stderr)
        print(f"\nValidation FAILED: {len(errors)} error(s)", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Validation PASSED: {stage}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
