# gh-finder2 Configuration Guide

## Format: TOML

`config.toml` at project root. Python 3.11+ `tomllib` (stdlib, zero deps).

## Structure

```toml
[fetch]       # GitHub API parameters
[scoring]     # Pre-screen ratio, timeouts
[weights]     # 7 scoring dimensions (sum = 100)
[thresholds]  # Normalization caps
[paths]       # Cache file paths
```

## Key Fields

### [fetch]
| Field | Default | Purpose |
|-------|---------|---------|
| `per_page` | 30 | GitHub Search API results per query |
| `exact_limit` | 5 | Max results for exact-type queries |
| `websearch_limit` | 5 | Max results for websearch-type queries |
| `semantic_limit` | 5 | Max results for semantic-type queries |
| `complexity_limit` | 3 | Max results for complexity-type queries |
| `request_gap_with_token` | 0.1 | Delay between API calls (with token) |
| `request_gap_without_token` | 1.0 | Delay between API calls (without token) |
| `min_stars` | 2 | Minimum stars for repo inclusion |
| `max_retries` | 3 | Max retries for transient errors |

### [scoring]
| Field | Default | Purpose |
|-------|---------|---------|
| `prescreen_keep_ratio` | 0.5 | Keep top 50% by description + seeds |
| `trust_timeout_sec` | 10 | Timeout for trust API checks |

### [weights] (sum must = 100)
| Dimension | Weight | Source |
|-----------|--------|--------|
| `purpose` | 30 | LLM ranking → percentile |
| `fit` | 20 | LLM ranking → percentile |
| `trust` | 15 | License, org/user, trust checks |
| `community` | 10 | Stars, forks, watchers percentile |
| `quality` | 10 | Language ratio, code quality |
| `infrastructure` | 10 | CI/CD, tests, docs |
| `momentum` | 5 | Recent activity |

## Migration Note

Previously `config/scoring.json` (JSON, nested in config/ folder). Migrated to `config.toml` (TOML, project root) to support `#` comments and flatter structure.
