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
