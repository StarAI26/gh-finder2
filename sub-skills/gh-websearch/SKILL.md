---
name: gh-websearch
category: meta
version: 1.0
description: Use WebSearch to discover latest GitHub projects for the user's intent, extract well-known project names as exact query seeds. / 用 WebSearch 发现用户意图对应的最新 GitHub 项目，提取知名项目名作为 exact query 种子。
metadata:
  hermes:
    tags: [web-search, project-discovery, exact-queries, knowledge-gap]
---

# gh-websearch: Discover Latest Projects via WebSearch

> "The LLM's training data is frozen. WebSearch is not."

## When to Run

Between `gh-intents` and `gh-fetch`. Only when the intent involves searching for GitHub projects in an active/evolving domain.

> **⚠️ Pitfall: Use the LLM platform's built-in websearch tool, NOT custom HTTP scraping.** DuckDuckGo HTML scraping is a last-resort fallback when no built-in search is available. Always prefer the platform's native search capability.
>
> **⚠️ Pitfall: Hermes built-in web_search requires FIRECRAWL_API_KEY.** If the key is commented out in `.env` (default), `web_search_tool()` returns "Web tools are not configured." Set `FIRECRAWL_API_KEY` in `.env` to enable, or use alternative search providers.

## Workflow

```
1. Read cache/intent.json (produced by gh-intents)
   ↓
2. Construct WebSearch query from intent.summary + constraints
   ↓
3. Analyze results: extract project names, filter by known orgs/stars/recency
   ↓
4. Merge: intent.json queries + discovered exact → cache/query.json
```

## Search Strategy

### Step 1: Read intent + construct search query

Read `cache/intent.json`. Use the summary and constraints to build a WebSearch query:

**Template**: `"github [domain] [key terms] best/popular"`

Examples:
- "word 转 markdown" → `"github python docx to markdown converter best"`
- "画图工具" → `"github drawing diagram tool popular"`
- "API mock 工具" → `"github api mock testing tool popular"`

Add a year if the domain is fast-moving: `"2024 2025"`.

### Step 2: Analyze results

From the WebSearch results:
- **Extract full_name** from any GitHub URLs (e.g., `github.com/microsoft/markitdown` → `microsoft/markitdown`)
- **Filter by known signals**:
  - Microsoft / Google / Meta / AWS org repos → keep (big org backing)
  - Mentions of "popular", "well-known", "recommended" → keep
  - Articles from dev.to, Medium, Reddit, HN discussing the project → keep
  - Low-star hobby projects with no discussion → skip unless unique angle
- **Deduplicate** by org/repo name

### Step 3: Merge → cache/query.json

Copy all queries from `cache/intent.json`, then append discovered project names:

```json
{
  "intent": { ... },
  "queries": [
    { "query": "python-docx", "reason": "De facto standard for reading docx", "type": "websearch" },
    { "query": "markitdown", "reason": "Microsoft universal doc converter, discovered via WebSearch", "type": "websearch" },
    { "query": "docx to markdown", "reason": "Core intent: format conversion", "type": "semantic" }
  ]
}
```

**Rules**:
- Discovered names become `"type": "websearch"` queries
- Each must have a concrete reason mentioning the source (e.g., "discovered via WebSearch: Microsoft official project")
- Limit to 2 discovered names (don't flood with guesses)

## Example

**Input**: `cache/intent.json` with summary: "Convert Word/DOCX to Markdown"

**WebSearch**: `"github python docx to markdown converter 2025"`

**Results found**:
- microsoft/markitdown (Microsoft official, mentioned in multiple articles)
- CYRUS-STUDIO/docx2markdown (Chinese blog post, niche)
- ChatCRM/docx2md (low visibility, skip)

**Output**: Add `"markitdown"` to exact queries.
