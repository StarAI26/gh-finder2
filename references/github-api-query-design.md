# GitHub API Query Design Principles

## Why Semantic Queries Fail on GitHub Search API

GitHub Search API does **substring match + stars sort**, not semantic search.

### Problem Examples

| Semantic Query | What GitHub Returns |
|---------------|-------------------|
| `"github project recommendation"` | Hospital recommendation systems, movie recommenders, car accident prediction notebooks |
| `"skill scoring ranking"` | ML feature engineering "skill score" notebooks, game ranking systems |
| `"agent skill discovery"` | Generic "skill" projects with zero agent relevance |

### Root Cause

The API matches any repo containing ALL keywords as substrings, then sorts by stars. There's no semantic understanding of "agent skill" vs "ML feature skill" vs "game skill".

### Design Principles

1. **Prefer exact project names** — If WebSearch or LLM knowledge discovered specific repos (e.g. `dmgrok/agent_skills_directory`), use them directly as `type: "websearch"` queries.

2. **Limit semantic query count** — Keep semantic queries to 1-2 max, and make them as specific as possible with domain-relevant keywords.

3. **Use `stars:>N` filter in query strings** — When using semantic queries, add star thresholds to filter out low-quality noise results.

4. **Validate results before scoring** — If semantic queries return obviously irrelevant projects, the fetcher should log warnings and the scorer should penalize them.

## Query Type Definitions

| Type | Purpose | Example | GitHub API Behavior | Top N (default) |
|------|---------|---------|-------------------|-----------------|
| `exact` | User explicitly specified project name | `"python-docx"`, `"mammoth"` | Usually returns 1 result (the exact repo) | 1 |
| `websearch` | Project name discovered via WebSearch | `"markitdown"`, `"pandoc"` | Usually returns 1 result | 1 |
| `semantic` | Describes user intent/functionality | `"docx to markdown"` | Returns top-N repos containing ALL keywords, sorted by stars | 5 |
| `complexity` | Targets the hardest implementation step | `"docx table markdown"` | Same as semantic, but conceptually different purpose | 3 |

### Exact vs Websearch Distinction

- **`exact`**: User knows the project name and explicitly asks for it. No WebSearch needed.
- **`websearch`**: Agent discovered the project name through WebSearch. Must mention source in `reason` field.

Both types have the same validation rule: first result's `full_name` must contain the query string. Both get Top N = 1 because they're precise matches.

### Config-Driven Limits

All fetch parameters are in `config/scoring.json` under the `fetch` key:

```json
{
  "fetch": {
    "per_page": 30,
    "exact_limit": 1,
    "websearch_limit": 1,
    "semantic_limit": 5,
    "complexity_limit": 3,
    "request_gap_with_token": 0.1,
    "request_gap_without_token": 1.0,
    "min_stars": 2,
    "max_retries": 3
  }
}
```

These are **NOT** hardcoded in fetcher.py — they must be read via `config.fetch.get("key", default)`.
