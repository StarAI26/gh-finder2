# gh-finder2 Session Learnings

## Script Ownership Rule

**"Who uses it, owns it."** Scripts live where their consumers live:

| Script | Location | Reason |
|--------|----------|--------|
| `common.py`, `validate.py` | `src/` | Cross-cutting, called from root steps |
| `cache.py`, `fetcher.py` | `sub-skills/gh-fetch/src/` | gh-fetch's responsibility |
| `rank_description.py`, `rank_readme.py`, `fetch_readmes.py`, `validate_scores.py`, `scorer.py` | `sub-skills/gh-score/src/` | gh-score's responsibility (LLM ranking + scoring) |

## Key Architecture Decisions

### README Fetch Moved to Step 7a

READMEs are no longer fetched during Step 5 (gh-fetch). They are downloaded in Step 7a by `fetch_readmes.py`, **only for repos that passed the description pre-screen**. This saves ~50% of GitHub API calls.

### LLM Only Ranks, Python Scores

LLM provides **ordered lists only** — no 0-100 scores. Position in list IS the ranking signal. Python converts rank to percentile: `#1 → 100, #N → 0`. This eliminates LLM subjective scoring bias (tendency to inflate scores for well-known projects).

### Config: TOML Format

`config.toml` at project root. Python 3.11+ `tomllib` reads it — zero dependencies, supports `#` comments. Replaced the confusing `config/scoring.json` (wrong name, nested folder, no comments).

### Pipeline Pattern

Both Step 5b and Step 7a follow the same pattern:
```
prepare subcommand → formatted text to stdout
         ↓
    LLM produces ordering (no scores)
         ↓
merge/rank subcommand ← LLM output via stdin
         ↓
    Script writes to cache/*.json (Agent never hand-edits)
         ↓
    validate_*.py → verify completeness
```

## Pitfalls Discovered

1. **Exact query first result mismatch**: GitHub Search API sorts by stars, not relevance. Query `playwright` → first result was `browser-use` (92K⭐), not `microsoft/playwright` (88K⭐). Seed detection may fail.

2. **Parameter name shadowing**: `parse_repo(fetch_readme=True)` shadows the `fetch_readme()` function. Rename parameter to `with_readme`.

3. **Semantic queries on GitHub API are noisy**: API does substring match + stars sort, NOT semantic search. `"github project recommendation"` matches hospital recommendation systems.

4. **Missing llm_scores.json keys**: If `purpose_ranking` or `fit_ranking` are missing, scorer gives 0 for that dimension. Always validate before scoring.

5. ~~**GitHub Search API returns NULL fields**~~ → **Data is NESTED under `metrics`/`activity`** (2026-05-07): The Search API actually returns COMPLETE data, but nested under `metrics` and `activity` keys, NOT as flat top-level fields. If you see "null" for stars/language, you're reading the wrong path. `fetched.json` structure: `repos[].metrics.stars`, `repos[].metrics.language`, `repos[].metrics.topics`, `repos[].activity.days_since_last_push`. No batch-fetch needed. The only real gap was `scorer.py` not forwarding `metrics`/`activity` to `scored.json` output (fixed by adding these fields to the scorer output dict).

6. **Step 8 output format requires independent project summary**: User expects "项目介绍" section to be written in Agent's own words based on understanding, NOT copied from description or README. "为什么匹配你的意图" must explain the connection to user's specific problem.

7. **python vs python3**: Container may only have `python3`. All scripts in SKILL.md and commands must use `python3`, never `python`.

## 2026-05-07 Session: Full Pipeline Run Findings

### `scorer.py` output was incomplete
`scored.json` was missing `metrics` and `activity` fields, making Step 8 output unable to show ⭐ stars, language, or last-push info. Fix: added `"metrics": repo.get("metrics", {})` and `"activity": repo.get("activity", {})` to the scorer output dict (SKILL.md patched with this pitfall).

### `fetched.json` data is complete, just nested
Initial inspection showed "null" for stars/language because the read path was wrong (`repo["stargazers_count"]` instead of `repo["metrics"]["stars"]`). The fetcher already populates all fields correctly — just nested.

### `rank_readme.py merge` handles missing repos gracefully
When a repo name in `purpose_order`/`fit_order` doesn't exist in fetched data, the script logs a warning and skips it — doesn't crash.

### Error recording during skill execution
User explicitly requested: "使用skill的时候，你需要时刻注意 skill与脚本产生的任何细小错误，都需要记录下来". All errors encountered during skill execution (script failures, data format mismatches, missing fields) must be patched into the relevant skill's Pitfalls section immediately.
