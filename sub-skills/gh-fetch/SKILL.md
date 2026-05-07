---
name: gh-fetch
category: devops
version: 0.1
description: Fetch GitHub repos via Search API with caching, return structured JSON. / 通过 GitHub Search API 抓取项目，带缓存，返回结构化 JSON。
metadata:
  hermes:
    tags: [github-api, fetch-repos, cache, structured-data]
---

# gh-fetch: GitHub API Fetch + Cache

> "Python does the fetching, LLM does the validation."

## Role

Fetch repos from GitHub Search API based on queries from `cache/query.json`, grab metadata (description, stars, forks, releases), save structured results to cache. This is **pure infrastructure** — no judgment, no scoring.

**README downloading is NOT fetcher's job.** READMEs are fetched later by `gh-score/src/fetch_readmes.py` in Step 7a, only for repos that pass the description-based pre-screen.

## Input

Read `cache/query.json` (produced by merging gh-intents + gh-websearch):
```json
{
  "intent": { "summary": "...", "constraints": "...", "insights": "..." },
  "queries": [
    { "query": "python-docx", "reason": "De facto standard for reading docx", "type": "exact" },
    { "query": "docx to markdown", "reason": "Core intent: format conversion", "type": "semantic" },
    { "query": "docx table markdown", "reason": "Hardest step: preserving tables", "type": "complexity" }
  ]
}
```

## Execution

Run the Python fetcher:
```bash
python3 sub-skills/gh-fetch/src/fetcher.py
```

The script reads `cache/query.json`, executes each query against the GitHub Search API, fetches metadata (description, stars, forks, releases), and writes results to `cache/fetched.json`. The `readme` field is set to empty string for all repos.

**README downloading moved to gh-score.** READMEs are fetched later by `gh-score/src/fetch_readmes.py` in Step 7a, only for repos that pass the description-based pre-screen. This saves ~50% of API calls.

### Python Script Behavior (src/fetcher.py)

- Reads queries from `cache/query.json` (each has `query`, `reason`, `type`: `"exact"`/`"websearch"`/`"semantic"`/`"complexity"`)
- For each query, calls `GET /search/repositories?q=<query>&sort=stars&order=desc&per_page=30`
- `GITHUB_TOKEN` env var is optional — without it, unauthenticated API (60 req/h, auto-adjusted 1.0s gap)
- Deduplicates repos by `full_name`
- Per-type result limits: read from `config.fetch` (`exact_limit`, `websearch_limit`, `semantic_limit`, `complexity_limit`)
- **`readme` field is always empty** — README download is handled by `gh-score/src/fetch_readmes.py`
- Fetches releases info for each repo
- Progress logs to stderr only
- Retries with exponential backoff on 5xx/SSL errors

## Output: cache/fetched.json

A JSON object containing seed repo identification and a flat array of repo objects. File contains only JSON — no extra text.

```json
{
  "seed_repo_names": [
    "python-openxml/python-docx",
    "mwilliamson/python-mammoth"
  ],
  "repos": [
    {
      "full_name": "python-openxml/python-docx",
      "html_url": "https://github.com/python-openxml/python-docx",
      "description": "Create and modify Word documents with Python",
      "search_score": 85.5,
      "owner": {
        "login": "python-openxml",
        "type": "Organization"
      },
      "metrics": {
        "stars": 3500,
        "forks": 800,
        "watchers": 200,
        "open_issues": 120,
        "language": "Python",
        "is_archived": false,
        "is_fork": false,
        "license_key": "BSD-3-Clause",
        "topics": ["python", "docx", "word"]
      },
      "activity": {
        "pushed_at": "2024-11-15T10:30:00Z",
        "created_at": "2014-03-20T08:00:00Z",
        "updated_at": "2024-12-01T05:00:00Z",
        "days_since_last_push": 170,
        "default_branch": "main"
      },
      "releases": {
        "has_releases": true,
        "total_releases": 15,
        "latest_release": "1.4.0",
        "published_at": "2024-10-20T12:00:00Z",
        "days_since_last_release": 40
      },
      "readme": "# python-docx\n\nFull README content here..."
    }
  ]
}
```

### Seed Repo Identification

Seed repos are **unconditionally kept** for scoring, even if their description ranked poorly.

**Rule**: First result of every query is a seed. Seed count = query count.

**Validation for `type: "exact"` and `type: "websearch"` queries**: For exact/websearch queries (de facto standard project names), the first result's `full_name` must contain the query string.
- `"pandoc"` → `"jgm/pandoc"` — matches, becomes seed
- `"python-docx"` → `"some-fork/unrelated-lib"` — doesn't match, WARN logged, NOT a seed
- 0 results — query yields nothing, skip

`type: "semantic"` and `type: "complexity"` queries have no validation — their first result is directly a seed.

### Field Requirements

| Field | Required | Notes |
|-------|----------|-------|
| `full_name` | Yes | `owner/repo` format |
| `html_url` | Yes | Full GitHub URL |
| `description` | Yes | Can be empty string if GitHub returns null |
| `search_score` | Yes | GitHub Search API's built-in relevance score (float, 0-100) |
| `owner.login` | Yes | Username or org name |
| `owner.type` | Yes | `"User"`, `"Organization"`, or `"Enterprise"` |
| `metrics.stars` | Yes | Integer ≥ 0 |
| `metrics.forks` | Yes | Integer ≥ 0 |
| `metrics.watchers` | Yes | Integer ≥ 0 — needed by community scorer |
| `metrics.open_issues` | Yes | Integer ≥ 0 — needed by quality scorer (issue/star ratio) |
| `metrics.language` | Yes | String or `null` |
| `metrics.is_archived` | Yes | Boolean |
| `metrics.is_fork` | Yes | Boolean |
| `metrics.license_key` | Yes | String or `null` |
| `metrics.topics` | Yes | Array of strings, can be empty |
| `activity.pushed_at` | Yes | ISO 8601 string or `null` |
| `activity.created_at` | Yes | ISO 8601 string or `null` |
| `activity.updated_at` | Yes | ISO 8601 string or `null` — large gap vs `pushed_at` suggests "starred but unmaintained" |
| `activity.days_since_last_push` | Yes | Integer or `null`, computed from `pushed_at` |
| `activity.default_branch` | Yes | String, e.g. `"main"` or `"master"` |
| `releases.has_releases` | Yes | Boolean |
| `releases.total_releases` | Yes | Integer ≥ 0 |
| `releases.latest_release` | Yes | Version string (e.g. `"1.4.0"`) or `null` if no releases |
| `releases.published_at` | Yes | ISO 8601 string or `null` |
| `releases.days_since_last_release` | Yes | Integer or `null` — "no formal releases" is a quality signal |
| `readme` | Yes | Empty string at this stage. Filled in Step 7a by `gh-score/src/fetch_readmes.py` |

## Validation Rules (Main Skill Checks)

After fetch completes, the main skill validates `cache/fetched.json`:

1. **File exists and is valid JSON** — not empty, not malformed
2. **Is an object with `seed_repo_names` (array) and `repos` (array)** — new format
3. **`repos` array has ≥ 1 element** — if empty, the fetch failed or queries returned nothing
4. **Every repo has all required fields** — check:
   - `full_name`, `html_url`, `description`, `search_score`
   - `owner.login`, `owner.type`
   - `metrics.stars` (int ≥ 0), `metrics.forks`, `metrics.watchers`, `metrics.open_issues`
   - `activity.pushed_at`, `activity.created_at`, `activity.updated_at`, `activity.days_since_last_push`
   - `releases.has_releases`, `releases.total_releases`
5. **No duplicates** — each `full_name` appears only once in `repos`
6. **README field present** — always empty string at this stage (filled in Step 7a by gh-score)
7. **`seed_repo_names` entries exist in `repos`** — every seed must be a valid repo in the array

If validation fails:
- If file is missing or invalid JSON → re-run `python3 sub-skills/gh-fetch/src/fetcher.py`
- If `repos` array is empty → check `GITHUB_TOKEN` is set, then re-run
- If individual repos are missing fields → re-run (likely a parse bug in fetcher.py)

## Error Handling

- **`GITHUB_TOKEN` not set** → fetcher continues with unauthenticated API (60 req/h limit, REQUEST_GAP auto-adjusted to 1.0s). Will hit 403 after ~30 requests.
- **403 rate limit** → wait and retry (up to 3 times), then exit with warning
- **Query returns 0 results** → log to stderr, continue to next query (do not abort)
- **Releases fetch fails for a repo** → set all `releases.*` to defaults (`false`, `0`, `null`, `null`, `null`), continue (do not abort)
- **Network error** → retry with exponential backoff (up to 3 retries per request)

## Out of Scope (NOT fetcher's job)

- **Trust / Code Search API** → done by `gh-score` stage (only on top candidates)
- **Relevance scoring** → LLM reads READMEs in `gh-score`
- **Semantic extraction** → LLM does this in `gh-score`
- **Query refinement** → Agent-driven decision, not automatic

## Pitfalls

> **⚠️ ALL fetch parameters must be in config, not hardcoded.** `per_page`, type limits (`websearch_limit`, `semantic_limit`, `complexity_limit`), `min_stars`, `request_gap`, `max_retries` — all live in `config.toml` under `[fetch]` section. The fetcher reads via `config.fetch.get(key, default)`. Hardcoding parameters prevents users from tuning behavior.
>
> **⚠️ Semantic/complexity queries on GitHub Search API are noisy**: API does substring match + stars sort, not semantic search. `"github project recommendation tool"` matches hospital/movie recommendation projects. `"skill scoring ranking system"` matches ML feature engineering notebooks. These queries inject noise, slow down fetching (every irrelevant repo needs README fetch), and degrade scoring quality. Prefer exact project names from WebSearch.
>
> **⚠️ Fetcher is metadata-only, no READMEs**: `fetcher.py` sets `readme` to empty string for all repos. READMEs are fetched later by `gh-score/src/fetch_readmes.py` in Step 7a, only for repos that pass the description pre-screen. This saves ~50% of API calls.
>
> **⚠️ SSL `UNEXPECTED_EOF_WHILE_READING` errors on GitHub API**: Container Python 3.13.5 sometimes hits SSL EOF errors on GitHub API calls. These are transient — catch `ssl.SSLError` and retry, don't abort.
>
> **⚠️ Fetcher reads `cache/query.json` NOT `cache/intent.json`**: The merged query file is the input. Running fetcher with only `intent.json` will fail because `config.path("query")` resolves to `cache/query.json`.
>
> **⚠️ Exact/websearch query first result may not match the query string**: GitHub Search API sorts by stars, not exact match. Query `"playwright"` may return `"browser-use/browser-use"` (92k stars) before `"microsoft/playwright"` (88k stars). This is expected behavior — the seed validation WARN is correct, don't treat it as a fetcher bug.
