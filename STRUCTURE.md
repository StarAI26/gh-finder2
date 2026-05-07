# gh-finder2 File Structure

Intent-driven GitHub project discovery pipeline with supervised multi-agent scoring.

```
gh-finder2/
├── SKILL.md                    # Master workflow: 8-step pipeline entry point
├── STRUCTURE.md                # This file
├── config.toml                 # Centralized config (fetch, scoring, weights, thresholds, paths)
│
├── src/                        # Top-level pipeline glue + validation
│   ├── common.py               # Config loader + shared path resolution
│   └── validate.py             # Stage validator: intents | fetch | score
│
├── sub-skills/                 # Reusable sub-skills — each is a self-contained module
│   ├── gh-intents/             # Step 1: Extract user intent → queries
│   │   └── SKILL.md
│   │
│   ├── gh-websearch/           # Step 2: Web search for project discovery
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── hermes-web-search-config.md
│   │
│   ├── gh-fetch/               # Step 5: Two-stage repo fetching
│   │   ├── SKILL.md
│   │   └── src/
│   │       ├── cache.py        #     Search API cache (avoids re-fetching same query)
│   │       └── fetcher.py      #     Main fetcher: metadata → pre-screen → README download
│   │
│   └── gh-score/               # Steps 5b + 7a + 7b: LLM ranking + Python scoring
│       ├── SKILL.md
│       └── src/
│           ├── base.py         #     BaseScorer class
│           ├── registry.py     #     Scorers registry + weight lookup
│           ├── scorer.py       #     Entry point: runs all scorers, aggregates scores
│           ├── rank_description.py  # Step 5b: LLM ranks repos by description → kept.json
│           ├── rank_readme.py       # Step 7a: LLM ranks kept repos by README → llm_scores.json
│           ├── validate_scores.py   # Step 7a pre-check: ensures llm_scores.json completeness
│           └── scorers/        #     Individual scoring modules
│               ├── __init__.py
│               ├── community.py
│               ├── infrastructure.py
│               ├── momentum.py
│               ├── quality.py
│               └── trust.py
│
├── references/                 # Cross-cutting reference docs
│   ├── github-api-query-design.md  # Query construction best practices
│   └── llm-pipeline-pattern.md     # prepare → LLM → merge/rank pattern
│
└── cache/                      # Runtime artifacts (git-ignored)
    ├── intent.json             # Step 1 output
    ├── query.json              # Step 3 output
    ├── fetched.json            # Step 5 output
    ├── kept.json               # Step 5b output
    ├── llm_scores.json         # Step 7a output
    └── scored.json             # Step 7b output
```

## Directory Conventions

| Directory | Purpose |
|-----------|---------|
| `src/` | Top-level pipeline glue. Only scripts called directly from SKILL.md root steps. |
| `sub-skills/*/src/` | Self-contained module scripts. Only scripts used within that sub-skill. |
| `references/` | Non-executable docs: API design, query strategies, patterns. |
| `cache/` | Runtime artifacts. Never committed — regenerated each run. |
| `config.toml` | Single config file at project root. TOML format with `#` comments. |

## Script Ownership Rule

**Who uses it, owns it.** Scripts live where their consumers live:
- `common.py` in `src/` — imported by multiple sub-skills (fetcher, scorer, validate)
- `validate.py` in `src/` — called from SKILL.md root steps
- `rank_description.py`, `rank_readme.py`, `validate_scores.py` in `sub-skills/gh-score/src/` — gh-score's responsibility
- `fetcher.py`, `cache.py` in `sub-skills/gh-fetch/src/` — gh-fetch's responsibility
- `scorer.py` + `scorers/*` in `sub-skills/gh-score/src/` — gh-score's responsibility

## Data Flow

```
intent.json ──→ query.json ──→ fetched.json ──→ kept.json ──→ llm_scores.json ──→ scored.json
 (Step 1)        (Step 3)        (Step 5)         (Step 5b)       (Step 7a)          (Step 7b)
```

Each file is produced by a specific stage and consumed by the next. `validate.py` checks intermediate outputs between stages.
