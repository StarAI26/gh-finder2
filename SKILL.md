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
Step 4: 校验 query.json → 运行 python src/validate.py query
Step 5: 调用 sub-skills/gh-fetch → 读 query.json，API 调用 + README
Step 6: 校验 fetched.json → python src/validate.py fetch
Step 7: 调用 sub-skills/gh-score → 读 README 判断相关性 + 排名
Step 8: 校验 scored.json → 输出最终结果
```

## Step-by-Step Execution

### Step 1: gh-intents

Run the `gh-intents` sub-skill to extract search parameters from the user's request.

- Output: `cache/intent.json`
- See [sub-skills/gh-intents/SKILL.md](sub-skills/gh-intents/SKILL.md) for the full specification

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

> **⚠️ Pitfall**: SKILL.md 原文档写的是 `validate.py query`，但实际脚本只接受 `intents | fetch | score`。用 `python3` 而非 `python`。
>
> **⚠️ Pitfall: query.json 中 semantic/complexity 查询在 GitHub Search API 上极度不精准**。API 做 substring match + stars 排序，不是语义搜索。`"github project recommendation tool"` 会匹配医院推荐系统、电影推荐项目等无关结果；`"skill scoring ranking system"` 匹配 ML feature engineering 的 "skill score" notebook。Semantic 查询引入大量噪音，拖慢 fetcher（每个无关项目都要抓 README），且降低评分质量。
>
> **⚠️ Pitfall: fetcher 串行抓取 README，大 README 拖垮整体**。`dmgrok/agent_skills_directory` 的 README 有 158KB（自动生成 skill 目录索引），传输 + base64 解码耗时远超正常 README。99 个项目串行抓 = 必然超时。应限制无关项目数量，或并发抓取。
>
> **⚠️ Pitfall: fetcher 无增量写入，中途超时 = 全部丢失**。必须全部抓完才写 `fetched.json`，网络超时导致工作白费。

**校验规则**：
- `intent.summary` 不能为空
- `queries` 数组 3-8 个元素
- 每个 query 对象必须有 `query`、`reason`、`type` 字段
- `type` 必须是 `"exact"` / `"websearch"` / `"semantic"` / `"complexity"` 之一
- exact ≤3，websearch ≤3，semantic ≤3，complexity ≤2
- 每个 query ≤3 个词
- `reason` 必须具体，不能是通用描述

**不合格处理**：指出具体失败原因，要求重做。

### Step 5: gh-fetch
### Step 5: gh-fetch (Stage 1 - Search)

Run the Python fetcher to get repo info (no READMEs yet):
```bash
python3 sub-skills/gh-fetch/src/fetcher.py
```

- Input: `cache/query.json` (NOT `intent.json` — the fetcher reads the merged queries)
- Output: `cache/fetched.json` (contains description/metrics, `readme` is empty)

> **⚠️ Pitfall: GITHUB_TOKEN not set**. Without token, GitHub API limits to 60 req/h. The fetcher was patched to work without token (graceful degradation). For >20 repos, set `GITHUB_TOKEN` or expect 403 rate limits during README fetch.

### Step 5b: LLM Pre-screen

1. LLM reads descriptions from `cache/fetched.json`
2. Ranks by relevance to intent
3. Keeps top 50% + seeds
4. Writes `cache/kept.json` (list of `full_name` strings)

### Step 5c: gh-fetch (Stage 2 - READMEs)

Run fetcher again to download only kept READMEs:
```bash
python3 sub-skills/gh-fetch/src/fetcher.py --readmes-only --kept-list cache/kept.json
```

- Updates `cache/fetched.json` in-place with READMEs for kept repos only.

### Step 6: Validate fetched.json

```bash
python src/validate.py fetch
```

**校验规则**：
- 文件存在且是合法 JSON
- 是包含 `seed_repo_names`（数组）和 `repos`（数组）的对象
- `repos` 至少 1 个元素
- 每个 repo 必须有所有必填字段（见 gh-fetch SKILL.md）
- 无重复 `full_name`
- 每个 seed 必须在 `repos` 中存在

**不合格处理**：
- 文件不存在或字段缺失 → 重新运行 `python sub-skills/gh-fetch/src/fetcher.py`
- 数组为空 → 检查 `GITHUB_TOKEN` 后重试
- 个别 repo 缺字段 → 可能是 parse bug，报告具体问题

### Step 7: gh-score

#### Step 7a: LLM pre-screen + ranking

1. Read `cache/fetched.json` — all repos + seed identification
2. Rank ALL repos by description relevance to intent (pre-screen)
3. Keep = top 50% by description ∪ `seed_repo_names`
4. For each kept repo, read `description` + `readme`, produce two rankings:
   - **purpose ranking**: most relevant to least relevant to user's intent
   - **fit ranking**: best fit to worst fit for user's specific scenario
5. Save to `cache/llm_scores.json`:

```json
{
  "prescreen_ranking": [
    { "full_name": "mwilliamson/python-mammoth", "rank": 1, "reason": "..." }
  ],
  "kept_for_scoring": ["mwilliamson/python-mammoth", "pandoc/pandoc", "..."],
  "purpose_ranking": [
    { "full_name": "mwilliamson/python-mammoth", "rank": 1, "reason": "..." }
  ],
  "fit_ranking": [
    { "full_name": "mwilliamson/python-mammoth", "rank": 1, "reason": "..." }
  ]
}
```

- See [sub-skills/gh-score/SKILL.md](sub-skills/gh-score/SKILL.md) for the full specification

#### Step 7b: Python scoring

```bash
python sub-skills/gh-score/src/scorer.py
```

- Reads `cache/fetched.json` + `cache/llm_scores.json`
- Converts rankings to percentile scores
- Runs 6 deterministic scorers: community(10) + trust(15) + quality(10) + momentum(5) + infrastructure(10) + purpose(30) + fit(20) = 100
- Output: `cache/scored.json`

### Step 8: Validate + Output

```bash
python src/validate.py score
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

> **⚠️ SKILL.md vs script mismatch**: `validate.py query` → `validate.py intents`。用 `python3` 而非 `python`。
>
> **⚠️ Fetcher 串行抓取 README，大 README 拖垮整体**：`dmgrok/agent_skills_directory` 的 README 有 158KB（自动生成 skill 目录索引），传输 + base64 解码耗时远超正常 README。应限制无关项目数量，或并发抓取。
>
> **⚠️ Fetcher 无增量写入，中途超时 = 全部丢失**：必须全部抓完才写 `fetched.json`，网络超时导致工作白费。
>
> **⚠️ SSL `UNEXPECTED_EOF_WHILE_READING` errors on GitHub API**：Container Python 3.13.5 有时在 GitHub API 调用时遇到 SSL EOF 错误。这些是瞬态的 — catch `ssl.SSLError` 并重试，不要 abort。
>
> **⚠️ 所有 fetch 参数必须放在 config/scoring.json**：`PER_PAGE`、`MIN_STARS`、`REQUEST_GAP`、各类查询的 top N 限制等都不能硬编码在 fetcher.py 中。统一通过 `config.fetch` 读取，确保可配置性。
>
> **⚠️ Semantic/complexity queries on GitHub API are noisy**: API 做 substring match + stars 排序，不是语义搜索。`"github project recommendation"` 匹配医院推荐系统；`"skill scoring ranking"` 匹配 ML notebook。Semantic 查询引入噪音，拖慢 fetcher。优先使用 `websearch` 类型的精准项目名。详见 [references/github-api-query-design.md](references/github-api-query-design.md)。

## Error Recovery

> **⚠️ 先分析再执行**: 遇到问题卡住时，先搞明白根本原因，不要盲目重试。用户明确要求"先搞明白问题"再动手。
>
> **⚠️ 所有参数必须在 config 中**: fetch 相关参数（per_page、类型限制、重试次数等）必须在 `config/scoring.json` 中配置，禁止硬编码。

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
