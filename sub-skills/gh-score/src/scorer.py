#!/usr/bin/env python3
"""Score + rank fetched repos. Python does signals, LLM does fit judgment.

Usage: python sub-skills/gh-score/src/scorer.py

Reads:  cache/fetched.json, cache/intent.json, cache/llm_scores.json
Writes: cache/scored.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Resolve paths
HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]  # gh-finder2/
sys.path.insert(0, str(ROOT / "src"))
from common import Config

sys.path.insert(0, str(HERE.parent))
from registry import load_scorers


def main():
    config = Config.load()
    fetched_path = config.path("fetched")
    intent_path = config.path("intent")
    scored_path = config.path("scored")

    # ── Load inputs ──
    if not fetched_path.exists():
        print(f"[score] ERROR: {fetched_path} not found", file=sys.stderr)
        sys.exit(1)

    fetched = json.loads(fetched_path.read_text(encoding="utf-8"))
    repos = fetched.get("repos", fetched)  # new format: {"seed_repo_names": [...], "repos": [...]}
    seed_repo_names = set(fetched.get("seed_repo_names", []))
    if not repos:
        print("[score] ERROR: no repos to score", file=sys.stderr)
        sys.exit(1)

    intent_summary = intent_path.read_text(encoding="utf-8")  # TODO: parse intent
    # TODO: actually load intent.json properly

    # ── Load LLM rankings ──
    llm_path = ROOT / "cache" / "llm_scores.json"
    llm_data = {}
    if llm_path.exists():
        llm_data = json.loads(llm_path.read_text(encoding="utf-8"))

    purpose_ranking = llm_data.get("purpose_ranking", [])
    fit_ranking = llm_data.get("fit_ranking", [])
    llm_kept = set(llm_data.get("kept_for_scoring", []))
    kept = llm_kept | seed_repo_names  # seeds always kept even if LLM didn't include them

    # ── Convert LLM rankings to percentile scores ──
    n_purpose = len(purpose_ranking)
    n_fit = len(fit_ranking)
    purpose_scores = {}
    fit_scores = {}

    for entry in purpose_ranking:
        rank = entry["rank"]
        pct = (n_purpose - rank + 1) / n_purpose * 100 if n_purpose > 0 else 50
        purpose_scores[entry["full_name"]] = round(pct, 1)

    for entry in fit_ranking:
        rank = entry["rank"]
        pct = (n_fit - rank + 1) / n_fit * 100 if n_fit > 0 else 50
        fit_scores[entry["full_name"]] = round(pct, 1)

    # ── Run Python scorers ──
    scorers = load_scorers(config)
    print(f"[score] Python scorers: {list(scorers.keys())}", file=sys.stderr)

    scored = []
    for repo in repos:
        name = repo["full_name"]
        is_kept = name in kept

        breakdown = {}
        for sname, scorer in scorers.items():
            score = scorer.compute(repo, config)
            breakdown[sname] = round(score, 1)

        # LLM dimensions (from percentile)
        breakdown["purpose"] = purpose_scores.get(name, 0) if is_kept else 0
        breakdown["fit"] = fit_scores.get(name, 0) if is_kept else 0

        # Composite: weighted average
        total_weight = 0
        weighted_sum = 0.0
        for dim, val in breakdown.items():
            w = config.weights.get(dim, 0)
            weighted_sum += val * w
            total_weight += w

        composite = weighted_sum / total_weight if total_weight > 0 else 0.0

        scored.append({
            "full_name": name,
            "html_url": repo.get("html_url", ""),
            "description": repo.get("description", ""),
            "composite_score": round(composite, 1),
            "score_breakdown": breakdown,
            "is_seed": name in seed_repo_names,
            "kept_by_llm": name in llm_kept,
            "evidence": _extract_evidence(repo),
        })

    # ── Sort + save ──
    scored.sort(key=lambda r: r["composite_score"], reverse=True)
    for rank, repo in enumerate(scored, 1):
        repo["rank"] = rank

    scored_path.parent.mkdir(parents=True, exist_ok=True)
    with open(scored_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)

    print(f"[score] Done → {scored_path} ({len(scored)} repos)", file=sys.stderr)
    print(f"[score] Top 5:", file=sys.stderr)
    for r in scored[:5]:
        print(f"  #{r['rank']} {r['full_name']}: {r['composite_score']} (kept={r['kept_by_llm']})", file=sys.stderr)


def _extract_evidence(repo: dict) -> str:
    """Find a relevant sentence/phrase from README."""
    readme = repo.get("readme", "")
    first_line = readme.split("\n")[0].strip()[:200]
    return first_line or repo.get("description", "")


if __name__ == "__main__":
    main()
