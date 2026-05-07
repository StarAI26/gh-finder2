---
name: gh-score
category: devops
version: 1.0
description: Score and rank fetched GitHub repos using Python + LLM. / 用 Python 确定性规则 + LLM 判断对项目打分排名。
metadata:
  hermes:
    tags: [scoring, ranking, relevance, readme-analysis]
---

# gh-score: Score + Rank GitHub Repos

> "Python measures signals. LLM judges fit."

## Workflow

```
Step 5b: rank_description.py prepare → LLM ranks by description → rank → kept.json
Step 7a: fetch_readmes.py → download READMEs for kept repos only
Step 7a: rank_readme.py prepare → LLM ranks by README → merge → llm_scores.json
Step 7a: validate_scores.py → verify 4 keys complete
Step 7b: scorer.py → converts rankings to percentiles + runs scorers → scored.json
```

**LLM only ranks — Python assigns scores.** Position in ordered list IS the ranking signal. Never output 0-100 scores.

---

## Step 5b: Description Pre-screen (via rank_description.py)

The script handles everything. You (the LLM) only provide an ordered list.

```bash
# Script outputs formatted repo descriptions for you to rank:
python sub-skills/gh-score/src/rank_description.py prepare

# You respond with a JSON array: [{"full_name": "...", "rank": 1, "reason": "..."}]
# Then feed it back to:
python sub-skills/gh-score/src/rank_description.py rank
```

**What the script does**:
- Reads `fetched.json` + `intent.json`
- Outputs all repos with description, stars, language
- You rank by relevance to `intent.summary`
- Script applies `prescreen_keep_ratio` (0.5 = top 50%) from `config.toml`
- Merges top 50% with seed repos → writes `kept.json`
- Writes `prescreen_ranking` + `kept_for_scoring` to `llm_scores.json`

---

## Step 7a: README Ranking (via rank_readme.py)

First, download READMEs only for kept repos:
```bash
python sub-skills/gh-score/src/fetch_readmes.py
```

Then rank based on README content:
```bash
# Script outputs kept repos with README previews:
python sub-skills/gh-score/src/rank_readme.py prepare

# You respond with TWO ordered lists:
python sub-skills/gh-score/src/rank_readme.py merge
```

**Your response format**:
```json
{
  "purpose_order": ["repo-a", "repo-b", "repo-c", ...],
  "fit_order": ["repo-x", "repo-y", "repo-z", ...],
  "reasons": {"repo-a": "explanation", "repo-b": "explanation"}
}
```

**Purpose ranking**: Most→least relevant to user's intent. Question: Which project's core function best matches what the user wants?

**Fit ranking**: Best→worst fit for user's specific scenario. Question: Given the user's constraints, which project is the best overall fit? Consider complexity, scope, target user, language preference.

**Validate before scoring**:
```bash
python sub-skills/gh-score/src/validate_scores.py
```

---

## Step 7b: Python Scoring (automatic)

```bash
python sub-skills/gh-score/src/scorer.py
```

Python converts your rankings to percentile scores:
- For a repo ranked #R out of N kept repos: Percentile = (N - R + 1) / N × 100
- #1 → 100, middle → 50, last → ~0

**Purpose score** (weight: 30) = percentile from purpose ranking.
**Fit score** (weight: 20) = percentile from fit ranking.

Then Python runs its 6 deterministic scorers: community(10) + trust(15) + quality(10) + momentum(5) + infrastructure(10) = 50 total, merges everything → weighted composite → outputs `cache/scored.json`.

Unkept repos get purpose=0, fit=0 — they can't win.

---

## Output: cache/llm_scores.json

Produced by the `rank_description.py` and `rank_readme.py` scripts. Must contain ALL four keys:

```json
{
  "prescreen_ranking": [{"full_name": "...", "rank": 1, "reason": "..."}],
  "kept_for_scoring": ["repo-a", "repo-b", ...],
  "purpose_ranking": [{"full_name": "...", "rank": 1, "reason": "..."}],
  "fit_ranking": [{"full_name": "...", "rank": 1, "reason": "..."}]
}
```

- `prescreen_ranking`: Every repo, ranked by description relevance (written by `rank_description.py`)
- `kept_for_scoring`: Top 50% ∪ seeds (written by `rank_description.py`)
- `purpose_ranking`: Kept repos only, ranked by purpose (written by `rank_readme.py merge`)
- `fit_ranking`: Kept repos only, ranked by fit (written by `rank_readme.py merge`)

**⚠️ Missing any key → scorer gives 0 for that dimension.** Always run `validate_scores.py` before `scorer.py`.
