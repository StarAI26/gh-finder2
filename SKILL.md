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
Step 4: 校验 query.json → 运行 python3 src/validate.py intents
Step 5: 调用 sub-skills/gh-fetch → 读 query.json，API 调用（Stage 1: metadata only）
Step 5b: LLM Pre-screen → 按 description 排序，保留 top 50% + seeds → cache/kept.json
Step 5c: gh-fetch Stage 2 → python3 fetcher.py --readmes-only --kept-list cache/kept.json
Step 6: 校验 fetched.json → python3 src/validate.py fetch
Step 7: 调用 sub-skills/gh-score → LLM 完整打分 + Python 评分
Step 8: 校验 scored.json → 输出最终结果
```

> **⚠️ Pitfall: DO NOT skip steps.** Steps 1→8 must execute in order. Common mistake: jumping straight to Step 5 (fetch) after Step 1, skipping WebSearch discovery (Step 2), merge (Step 3), and validation (Step 4). The workflow is a pipeline — each step produces artifacts the next depends on. If user says "跑", run ALL steps in sequence.

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

### Step 5b: LLM Pre-screen (standardized)

```bash
# 1. Prepare repo descriptions for LLM ranking
python3 src/prescreen.py prepare

# 2. LLM ranks repos by relevance to intent.summary
#    Respond with: full_name:relevance_score(1-100):reason (one per line)
#    OR JSON array: [{"full_name": "...", "rank": 1, "reason": "..."}]

# 3. Feed ranking back to script → writes kept.json + llm_scores.json
python3 src/prescreen.py rank
```

> **⚠️ Pitfall: Do NOT hand-write kept.json or llm_scores.json.** Always use `prescreen.py prepare` + `prescreen.py rank` pipeline. The script validates format, applies `prescreen_keep_ratio` from config, merges seeds, and writes both `kept.json` and `llm_scores.json` atomically.

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

#### Step 7a: LLM ranking (standardized)

After Step 5b already wrote `prescreen_ranking` and `kept_for_scoring`, LLM must now add `purpose_ranking` and `fit_ranking` to `llm_scores.json`:

```bash
# 1. Read READMEs of kept repos from fetched.json
# 2. LLM produces two rankings:
#    - purpose_ranking: relevance to user's intent
#    - fit_ranking: fit for user's specific scenario
# 3. Update llm_scores.json manually, then validate:
python3 src/validate_llm_scores.py
```

> **⚠️ Pitfall: `llm_scores.json` MUST include ALL four keys**: `prescreen_ranking`, `kept_for_scoring`, `purpose_ranking`, `fit_ranking`. If `purpose_ranking` or `fit_ranking` are missing, scorer.py gives them 0 score, making even relevant repos rank poorly. Every kept repo must appear in both purpose and fit rankings. Use `validate_llm_scores.py` before running scorer.py — it will catch missing fields automatically.

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

> **⚠️ 修改代码后必须先展示 diff/关键改动，确认逻辑正确再执行**。不要改完直接跑，用户需要看到改了什么、为什么这样改。
>
> **⚠️ DO NOT hand-write cache files.** Steps 5b (prescreen) and 7a (llm_scores) must use standardized scripts: `python3 src/prescreen.py prepare` + `python3 src/prescreen.py rank` for pre-screening, and `python3 src/validate_llm_scores.py` for LLM scoring validation. Manual JSON editing leads to missing fields (purpose/fit rankings → scorer gives 0) and format errors.
>
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
>
> **⚠️ Exact query first result may not match the query name**: GitHub Search API sorts by stars, not relevance. Query `playwright` → first result was `browser-use/browser-use` (92K⭐), not `microsoft/playwright` (88K⭐). The seed repo detection logic uses `query.lower() in first_name.lower()` validation — if it fails, the expected project won't be seeded. Consider adding the expected repo to seed_repos manually when exact query validation fails.
>
> **⚠️ `parse_repo` parameter `fetch_readme` shadows the `fetch_readme()` function**: When adding a `fetch_readme: bool = True` parameter to `parse_repo()`, the parameter name shadows the module-level `fetch_readme()` function, causing `NameError: name 'fetch_readme' is not defined` or calling the bool. Rename parameter to `with_readme` to avoid shadowing.

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
