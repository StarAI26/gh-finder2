# Hermes Web Search Configuration

## Built-in `web_search` Tool

Hermes Agent provides a `web_search` tool via `web_tools.py`, but it **requires an external API provider** — there's no free built-in search engine.

### Supported Providers

| Provider | Env Var | Status |
|----------|---------|--------|
| Firecrawl | `FIRECRAWL_API_KEY` | Default backend |
| Tavily | `TAVILY_API_KEY` | Alternative |
| Exa | `EXA_API_KEY` | Alternative |

### Configuration in `.env`

```bash
# Firecrawl (default)
FIRECRAWL_API_KEY=your-key-here
FIRECRAWL_API_URL=  # Optional: self-hosted instance

# Or Tavily
TAVILY_API_KEY=your-key-here
TAVILY_BASE_URL=https://api.tavily.com  # Optional

# Or Exa
EXA_API_KEY=your-key-here
```

### Testing

```python
from web_tools import web_search_tool
result = web_search_tool("github agent skill discovery", limit=5)
```

### Qwen/DashScope `enable_search`

Qwen models on DashScope support `"enable_search": true` in the API payload, which triggers server-side web search. However, this is **not** exposed through Hermes' tool system — it's a model-level parameter. To use it, you'd need to modify the LLM call directly (not recommended for skill workflows).

### Fallback

If no web search API key is configured, use DuckDuckGo HTML scraping as last resort (`html.duckduckgo.com/html/?q=...`), but warn the user that results may be incomplete and the approach is fragile.
