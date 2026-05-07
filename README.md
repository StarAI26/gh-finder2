# gh-finder2: Intent-Driven GitHub Project Discovery

Intent-driven GitHub project discovery with supervised multi-agent scoring. Tell it what you're looking for in natural language — it runs an 8-step pipeline to find, rank, and score the best matching projects.

## Features

- **Natural language input** — describe what you need, it constructs search queries
- **WebSearch discovery** — supplements GitHub Search with web-found projects
- **Two-stage fetching** — metadata first, READMEs only for shortlisted repos (~50% API savings)
- **LLM ranking** — LLM provides relative order, not subjective scores
- **Python scoring** — 7 dimensions (purpose, fit, trust, community, quality, infrastructure, momentum)
- **Configurable weights** — tweak scoring dimensions in `config.toml`

## Install

This is a [Hermes Agent](https://hermes-agent.nousresearch.com) skill. Install it by cloning into your skills directory:

```bash
# Default skills location
git clone <repo-url> ~/.hermes/skills/gh-finder2
```

Or symlink an existing checkout:

```bash
ln -s /path/to/gh-finder2 ~/.hermes/skills/gh-finder2
```

No Python dependencies required — uses stdlib only (`tomllib`, `urllib`, `json`).

## Requirements

| Item | Required | Notes |
|------|----------|-------|
| `GITHUB_TOKEN` | ⚠️ Optional | Without it: 60 req/h (may be incomplete). With it: 5000 req/h. Set via `export GITHUB_TOKEN=ghp_xxx` |
| Python 3.11+ | ✅ Yes | For `tomllib` (TOML config parser) |
| Hermes Agent | ✅ Yes | The skill is designed to run within Hermes |
| DASHSCOPE_API_KEY | ⚠️ Optional | Only if using Qwen/Alibaba LLM for ranking |
| FIRECRAWL_API_KEY | ⚠️ Optional | Only if using Firecrawl for WebSearch |

## Quick Start

```
# Just tell the agent what you want to find:
"帮我找 Python 的异步 HTTP 客户端库"
"Find lightweight Go web frameworks"
"推荐一个把 Markdown 转 PDF 的 Rust 工具"
```

The agent runs the 8-step pipeline automatically:

1. Extract intent → search queries
2. WebSearch discovery
3. Merge queries
4. Validate + check token
5. Fetch repo metadata
5b. LLM ranks by description → shortlist
6. Validate fetched data
7a. Download READMEs + LLM ranks
7b. Python scores + weights
8. Output final results

## Configuration

Edit [`config.toml`](config.toml) to adjust:

- **`[fetch]`** — API limits, request gaps, min stars
- **`[scoring]`** — pre-screen keep ratio
- **`[weights]`** — scoring dimension weights (sum = 100)
- **`[thresholds]`** — quality gates
- **`[paths]`** — output file paths (usually leave as-is)

## License

MIT
