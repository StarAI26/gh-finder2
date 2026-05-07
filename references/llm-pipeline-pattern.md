# LLM Pipeline Pattern (prepare → LLM input → merge/rank)

Both Step 5b and Step 7a use the same standardized pipeline under `sub-skills/gh-score/src/`.
This eliminates hand-written JSON for cache files.

## Pattern

```
prepare subcommand → formatted text to stdout
         ↓
    LLM produces ordering (text or JSON)
         ↓
merge/rank subcommand ← LLM output via stdin
         ↓
    Script writes to cache/*.json
         ↓
    validate_scores.py → verify completeness
```

## Step 5b: rank_description.py

| Subcommand | Purpose |
|------------|---------|
| `prepare` | Reads fetched.json + intent.json, outputs formatted repo descriptions |
| `rank` | Reads LLM ranking from stdin, writes kept.json + llm_scores.json (prescreen_ranking, kept_for_scoring) |

Input format for `rank`:
- JSON array of `{"full_name": "...", "rank": N, "reason": "..."}`

## Step 7a: rank_readme.py

| Subcommand | Purpose |
|------------|---------|
| `prepare` | Reads fetched.json + kept.json, outputs README previews for LLM ranking |
| `merge` | Reads LLM orderings from stdin, appends purpose_ranking + fit_ranking to llm_scores.json |

Input format for `merge`:
```json
{
  "purpose_order": ["repo-a", "repo-b", "..."],
  "fit_order": ["repo-c", "repo-d", "..."],
  "reasons": {"repo-a": "...", "repo-b": "..."}
}
```

## Key Design Decision: LLM Only Ranks, Python Scores

LLM outputs **ordered lists only** — no 0-100 scores. Scripts assign rank by position (1-based), `scorer.py` converts to percentile.

**Why**: LLM scoring is subjective and biased toward well-known projects (high stars). Position-based ranking removes the "how good is this on a scale of 100?" question — only relative ordering matters, which LLMs are good at.

## Key Properties

1. **Key preservation**: `rank_readme.py merge` preserves existing keys from `rank_description.py rank`. Never overwrites `prescreen_ranking` or `kept_for_scoring`.
2. **Fallback safety**: If Step 5b was skipped, `merge` creates fallback `prescreen_ranking` and `kept_for_scoring` from kept.json.
3. **Validation gate**: Always run `validate_scores.py` after `merge` and before `scorer.py`. It checks all 4 required keys exist.
4. **No hand-editing**: Agent should NEVER directly write to llm_scores.json, kept.json, or any cache file. All writes go through scripts.

## Common Failure Modes

| Failure | Cause | Fix |
|---------|-------|-----|
| scorer gives 0 for purpose/fit | `merge` not run, or stdin was empty | Re-run `rank_readme.py merge` with valid JSON |
| validate fails: missing prescreen_ranking | Step 5b `rank_description.py rank` not run | Run `rank_description.py rank` first |
| validate fails: missing kept_for_scoring | Step 5b output overwritten | Re-run `rank_description.py rank`, then `rank_readme.py merge` |
| JSON parse error | LLM output was not valid JSON | Ensure LLM responds with valid JSON array |
