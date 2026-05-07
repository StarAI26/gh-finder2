# gh-finder2

**Find GitHub projects by intent, not just keywords.**

An 8-step discovery pipeline that takes a natural-language description, constructs search queries, then uses **LLM ranking + Python scoring** to surface projects that actually match your needs — not just the ones with the most stars.

## Why

GitHub Search ranks by stars. Searching "lightweight headless browser" returns a 94K-star test framework because it has the keyword. gh-finder2 understands your intent, ranks by relevance, and scores across 7 dimensions.

## Install

**Requirements:** Python 3.11+, GITHUB_TOKEN (recommended). No `pip install` — stdlib only.

**Important:** Clone the entire repository — the pipeline relies on `sub-skills/`, `src/`, and `config.toml`.

```bash
git clone https://github.com/<you>/gh-finder2.git
cd gh-finder2
export GITHUB_TOKEN=ghp_your_token_here
```

**With AI Agents:**
- **Claude Code:** `claude --skill-path /path/to/SKILL.md`
- **Hermes Agent:** `ln -s $(pwd) ~/.hermes/skills/gh-finder2`
- **Others:** copy to your agent's skills folder or point to `SKILL.md`

## Usage

Tell your agent what you're looking for:

```
"帮我找 Python 的异步 HTTP 客户端库"
"Find lightweight Go web frameworks"
"推荐一个把 Markdown 转 PDF 的 Rust 工具"
```

## How It Works

1. **Intent** → extracts search queries from natural language
2. **WebSearch** → supplements GitHub Search with web-found projects
3. **Fetch** → GitHub API metadata
4. **Rank** → LLM ranks by description and README
5. **Score** → Python computes 7 dimensions → final weighted composite

Scoring dimensions: purpose (30) · fit (20) · trust (15) · community (10) · quality (10) · infrastructure (10) · momentum (5)

## Config

Edit `config.toml` to adjust weights, API limits, and thresholds.

## License

MIT
