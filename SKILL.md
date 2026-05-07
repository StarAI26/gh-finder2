---
name: gh-finder2
category: devops
version: 1.0
description: Intent-driven GitHub project discovery with supervised multi-skill flow.
metadata:
  hermes:
    tags: [find-projects, recommend-tools, search-github, intent-driven]
---

# gh-finder2: Intent-Driven GitHub Project Discovery

## Workflow

```
Step 1: 调用 sub-skills/gh-intents → 提取搜索参数，保存至 cache/intent.json
Step 2: 调用 sub-skills/gh-websearch → WebSearch 补充发现知名项目
Step 3: 合并 intent.json + websearch 结果 → cache/query.json（单一查询入口）
Step 4: 校验 query.json → python3 src/validate.py intents
Step 5: 调用 sub-skills/gh-fetch → metadata only (no READMEs)
Step 5b: python3 sub-skills/gh-score/src/rank_description.py prepare → LLM ranks → rank → kept.json + llm_scores.json
Step 6: 校验 fetched.json → python3 src/validate.py fetch
Step 7a: python3 sub-skills/gh-score/src/fetch_readmes.py → download READMEs for kept repos only
         python3 sub-skills/gh-score/src/rank_readme.py prepare → LLM orders → merge → llm_scores.json
Step 7a-v: python3 sub-skills/gh-score/src/validate_scores.py → verify 4 keys complete
Step 7b: python3 sub-skills/gh-score/src/scorer.py → cache/scored.json
Step 8: 校验 scored.json → python3 src/validate.py score → 输出最终结果
```

> **⚠️ Pitfall: DO NOT skip steps.** Steps 1→8 must execute in order. Common mistake: jumping straight to Step 5 (fetch) after Step 1, skipping WebSearch discovery (Step 2), merge (Step 3), and validation (Step 4). The workflow is a pipeline — each step produces artifacts the next depends on. If user says "跑", run ALL steps in sequence.
>
> **⚠️ Pipeline pattern for LLM stages (5b + 7a)**: Both follow `prepare` → LLM input → `merge/rank` pattern. The scripts handle all JSON writing — Agent never hand-edits cache files. See [references/llm-pipeline-pattern.md](references/llm-pipeline-pattern.md).

## Step-by-Step Execution

### Step 1: gh-intents

Run the `gh-intents` sub-skill to extract search parameters from the user's request.

- Output: `cache/intent.json`
- See [sub-skills/gh-intents/SKILL.md](sub-skills/gh-intents/SKILL.md) for the full specification

## Configuration

All parameters live in `config.toml` (project root). Python 3.11+ `tomllib` reads it — zero dependencies, supports `#` comments.

```toml
[fetch]       # GitHub API: per_page, type limits, rate control, min_stars, retries
[scoring]     # prescreen_keep_ratio (0.5 = keep top 50%), trust_timeout_sec
[weights]     # 7 scoring dimensions (sum = 100): purpose(30), fit(20), trust(15), community(10), quality(10), infrastructure(10), momentum(5)
[thresholds]  # Normalization caps for stars/forks/watchers, trust check limits
[paths]       # Cache file paths relative to project root
```

Read via `Config.load()` in `src/common.py`. All scripts use this single entry point.

### Step 2: gh-websearch

Run the `gh-websearch` sub-skill to discover latest projects via WebSearch.

- Input: `cache/intent.json`
- WebSearch query template: `"github [domain] [key terms] best/popular 2024 2025"`
- Filter by: big org backing (Microsoft/Google/Meta/AWS), technical articles, community mentions
- Skip: low-star hobby projects with no discussion
- Limit: max 2 discovered names

> **⚠️ Pitfall: Do NOT use DuckDuckGo/Google HTML scraping as a substitute for built-in websearch.** If the LLM platform provides a native websearch tool, use it. Custom HTML scraping (DuckDuckGo HTML interface) is a fallback only when no built-in search is available and the user has consented.

### Step 3: Merge → query.json

Merge gh-intents queries with gh-websearch discoveries into a single file:

```json
{
  "intent": { "summary": "...", "constraints": "...", "insights": "" },
  "queries": [
    { "query": "python-docx", "reason": "...", "type": "websearch" },
    { "query": "markitdown", "reason": "Microsoft universal doc converter, discovered via WebSearch", "type": "websearch" },
    { "query": "docx to markdown", "reason": "...", "type": "semantic" }
  ]
}
```

### Step 4: Validate intent.json

```bash
python3 src/validate.py intents
```

**校验规则**：
- `intent.summary` 不能为空
- `queries` 数组 3-8 个元素
- 每个 query 对象必须有 `query`、`reason`、`type` 字段
- `type` 必须是 `"exact"` / `"websearch"` / `"semantic"` / `"complexity"` 之一
- exact ≤3，websearch ≤3，semantic ≤3，complexity ≤2
- 每个 query ≤3 个词
- `reason` 必须具体，不能是通用描述

**不合格处理**：指出具体失败原因，要求重做。

### Step 5: gh-fetch (Stage 1 - Search)

Run the Python fetcher to get repo info (no READMEs yet):
```bash
python3 sub-skills/gh-fetch/src/fetcher.py
```

- Input: `cache/query.json` (NOT `intent.json` — the fetcher reads the merged queries)
- Output: `cache/fetched.json` (contains description/metrics, `readme` is empty)

### Step 5b: LLM Pre-screen (standardized)

```bash
# 1. Prepare repo descriptions for LLM ranking
python3 sub-skills/gh-score/src/rank_description.py prepare

# 2. LLM ranks repos by relevance to intent.summary
#    Format: JSON array of [{"full_name": "...", "rank": 1, "reason": "..."}]

# 3. Feed ranking back to script → writes kept.json + llm_scores.json
python3 sub-skills/gh-score/src/rank_description.py rank
```

### Step 6: Validate fetched.json

```bash
python3 src/validate.py fetch
```

**校验规则**：
- 文件存在且是合法 JSON
- 是包含 `seed_repo_names`（数组）和 `repos`（数组）的对象
- `repos` 至少 1 个元素
- 每个 repo 必须有所有必填字段（见 gh-fetch SKILL.md）
- 无重复 `full_name`
- 每个 seed 必须在 `repos` 中存在

**不合格处理**：
- 文件不存在或字段缺失 → 重新运行 `python3 sub-skills/gh-fetch/src/fetcher.py`
- 数组为空 → 检查 `GITHUB_TOKEN` 后重试
- 个别 repo 缺字段 → 可能是 parse bug，报告具体问题

### Step 7: gh-score

#### Step 7a: LLM ranking (standardized)

First, download READMEs only for kept repos. Then LLM ranks based on README content.

```bash
# 1. Download READMEs for kept repos only
python3 sub-skills/gh-score/src/fetch_readmes.py

# 2. Prepare kept repos + READMEs for LLM ranking
python3 sub-skills/gh-score/src/rank_readme.py prepare

# 3. LLM provides TWO ORDERED LISTS (no scores):
#    Format: {"purpose_order": [...], "fit_order": [...], "reasons": {...}}

# 4. Feed orderings back to script → appends to llm_scores.json
python3 sub-skills/gh-score/src/rank_readme.py merge

# 5. Validate completeness
python3 sub-skills/gh-score/src/validate_scores.py
```

- See [sub-skills/gh-score/SKILL.md](sub-skills/gh-score/SKILL.md) for the full specification

#### Step 7b: Python scoring

```bash
python3 sub-skills/gh-score/src/scorer.py
```

- Reads `cache/fetched.json` + `cache/llm_scores.json`
- Converts rankings to percentile scores
- Runs 6 deterministic scorers: community(10) + trust(15) + quality(10) + momentum(5) + infrastructure(10) + purpose(30) + fit(20) = 100
- Output: `cache/scored.json`

### Step 8: Validate + Output

```bash
python3 src/validate.py score
```

**校验规则**：
- `cache/scored.json` 存在且是合法 JSON 数组
- 按 `composite_score` 降序排列
- 每个 repo 必须有 `full_name`、`composite_score`、`score_breakdown`、`is_seed`、`kept_by_llm`、`evidence`
- 每个 breakdown 维度值在 0-100 范围内
- `composite_score` 在 0-100 范围内

**输出最终结果**：

```
Top GitHub Projects for: [intent.summary]

#1 owner/repo (score: 85.2)
   URL: https://github.com/owner/repo
   Evidence: [first line of README]
   Breakdown: purpose=100, fit=90, community=75, trust=80, quality=70, momentum=60, infrastructure=50

#2 owner/repo (score: 78.1)
   ...
```

## Pitfalls

> **⚠️ LLM only ranks, Python scores**: `rank_description.py rank` and `rank_readme.py merge` accept ordered lists only — no numeric scores. LLM outputs `[repo-a, repo-b, ...]`, scripts assign rank by position, scorer.py converts to percentile. Never let LLM assign 0-100 scores — position in list IS the ranking signal.
>
> **⚠️ GITHUB_TOKEN not set** → 60 req/h limit. For >20 repos, expect 403 during README fetch.
>
> **⚠️ Semantic/complexity queries on GitHub API are noisy**: API does substring match + stars sort, NOT semantic search. `"github project recommendation"` matches hospital recommendation systems. Prefer `websearch` type with exact project names.
>
> **⚠️ Exact query first result may not match**: API sorts by stars, not relevance. Query `playwright` → first result was `browser-use` (92K⭐), not `microsoft/playwright` (88K⭐). Seed detection may fail — add expected repos manually if needed.
>
> **⚠️ SSL `UNEXPECTED_EOF_WHILE_READING` errors**: Transient — catch `ssl.SSLError` and retry, don't abort.

## Error Recovery

| Step | Failure | Recovery |
|------|---------|----------|
| gh-intents | 用户拒绝所有选项 | 用默认参数生成 queries |
| gh-websearch | WebSearch 无结果 | 跳过，只用 intent.json 的 queries |
| query validation | 校验失败 | 指出具体问题，重做 |
| gh-fetch | 403 rate limit | 等待后重试，或直接 skip |
| gh-fetch | README 为空 | 继续，后续 scoring 时惩罚 |
| fetched validation | 字段缺失 | 重跑 fetcher |
| gh-score | LLM 输出格式错 | 指出问题，重新排名 |
| scored validation | evidence 不在 README 中 | 重做 scoring |

## Execution Philosophy

- **先分析再执行**: 遇到问题卡住时，先搞明白根本原因，不要盲目重试。用户偏好先理解问题再动手。
- See [references/github-api-query-design.md](references/github-api-query-design.md) for query design principles and why semantic queries fail on GitHub API.
