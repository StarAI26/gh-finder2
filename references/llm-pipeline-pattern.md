# LLM Pipeline Pattern (prepare → LLM input → merge/rank)

Both Step 5b (pre-screen) and Step 7a (LLM scoring) use the same standardized pipeline. This eliminates hand-written JSON for cache files.

## Pattern

```
prepare subcommand → formatted text to stdout
         ↓
    LLM produces ranking/scoring (text or JSON)
         ↓
merge/rank subcommand ← LLM output via stdin
         ↓
    Script writes to cache/*.json
         ↓
    validate_*.py → verify completeness
```

## Step 5b: prescreen.py

| Subcommand | Purpose |
|------------|---------|
| `prepare` | Reads fetched.json + intent.json, outputs formatted repo descriptions |
| `rank` | Reads LLM ranking from stdin, writes kept.json + llm_scores.json (prescreen_ranking, kept_for_scoring) |

Input format for `rank`: JSON array of `{"full_name": "...", "rank": N, "reason": "..."}`

## Step 7a: score_llm.py

| Subcommand | Purpose |
|------------|---------|
| `prepare` | Reads fetched.json + kept.json, outputs README previews for LLM scoring |
| `merge` | Reads LLM scores from stdin, appends purpose_ranking + fit_ranking to llm_scores.json |

Input format for `merge`: JSON array of `{"full_name": "...", "purpose_score": N, "fit_score": N, "reason": "..."}`

## Key Properties

1. **Key preservation**: `merge` preserves existing keys from `prescreen.py rank`. Never overwrites `prescreen_ranking` or `kept_for_scoring`.
2. **Fallback safety**: If Step 5b was skipped, `merge` creates fallback `prescreen_ranking` and `kept_for_scoring` from kept.json.
3. **Validation gate**: Always run `validate_llm_scores.py` after `merge` and before `scorer.py`. It checks all 4 required keys exist.
4. **No hand-editing**: Agent should NEVER directly write to llm_scores.json, kept.json, or any cache file. All writes go through scripts.

## Common Failure Modes

| Failure | Cause | Fix |
|---------|-------|-----|
| scorer gives 0 for purpose/fit | `merge` not run, or stdin was empty | Re-run `score_llm.py merge` with valid JSON |
| validate fails: missing prescreen_ranking | Step 5b `prescreen.py rank` not run | Run `prescreen.py rank` first |
| validate fails: missing kept_for_scoring | Step 5b output overwritten | Re-run `prescreen.py rank`, then `score_llm.py merge` |
| JSON parse error | LLM output was not valid JSON | Ensure LLM responds with valid JSON array |
