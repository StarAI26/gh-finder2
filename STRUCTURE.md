# gh-finder2 File Structure

Intent-driven GitHub project discovery pipeline with supervised multi-agent scoring.

```
gh-finder2/
├── SKILL.md                    # Master workflow: 8-step pipeline entry point
├── STRUCTURE.md                # This file
├── config.toml                 # Centralized config (fetch, scoring, weights, thresholds, paths)
│
├── src/                        # Top-level pipeline glue + validation
│   ├── common.py               # Config loader (tomllib) + shared path resolution
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
│   │       └── fetcher.py      #     GitHub Search API queries → metadata only (no READMEs)
│   │
│   └── gh-score/               # Steps 5b + 7a + 7b: LLM ranking + Python scoring
│       ├── SKILL.md
│       └── src/
│           ├── base.py         #     BaseScorer class (all scorers inherit from this)
│           ├── registry.py     #     Scorers registry + weight lookup
│           ├── scorer.py       #     Entry point: runs all scorers, aggregates scores
│           ├── fetch_readmes.py    # Step 7a: Download READMEs for kept repos only
│           ├── rank_description.py # Step 5b: LLM ranks repos by description → kept.json
│           ├── rank_readme.py      # Step 7a: LLM ranks kept repos by README → llm_scores.json
│           ├── validate_scores.py  # Step 7a pre-check: ensures llm_scores.json completeness
│           └── scorers/        #     Individual scoring modules
│               ├── __init__.py
│               ├── community.py    # Stars, forks, watchers percentile
│               ├── infrastructure.py # CI/CD, tests, docs presence
│               ├── momentum.py     # Recent activity (pushes, releases)
│               ├── quality.py      # Language ratio, code quality signals
│               └── trust.py        # License, org/user, trust checks
│
├── references/                 # Cross-cutting reference docs
│   ├── github-api-query-design.md  # Query construction best practices
│   └── llm-pipeline-pattern.md     # prepare → LLM → merge/rank pattern
│
└── cache/                      # Runtime artifacts (git-ignored)
    ├── intent.json             # Step 1 output: user intent + queries
    ├── query.json              # Step 3 output: merged queries (intent + websearch)
    ├── fetched.json            # Step 5 output: repo metadata + READMEs (empty until Step 7a)
    ├── kept.json               # Step 5b output: pre-screened repo names
    ├── llm_scores.json         # Step 7a output: LLM rankings (4 keys)
    └── scored.json             # Step 7b output: final scored repos
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

| Script | Location | Reason |
|--------|----------|--------|
| `common.py` | `src/` | Shared by fetcher, scorer, validate — cross-cutting |
| `validate.py` | `src/` | Called from SKILL.md root steps |
| `cache.py`, `fetcher.py` | `sub-skills/gh-fetch/src/` | gh-fetch's responsibility |
| `rank_description.py`, `rank_readme.py`, `fetch_readmes.py`, `validate_scores.py` | `sub-skills/gh-score/src/` | gh-score's responsibility (LLM ranking + scoring) |
| `scorer.py` + `scorers/*` | `sub-skills/gh-score/src/` | gh-score's responsibility |

## Data Flow

```
intent.json ──→ query.json ──→ fetched.json ──→ kept.json ──→ llm_scores.json ──→ scored.json
 (Step 1)        (Step 3)        (Step 5)         (Step 5b)       (Step 7a)          (Step 7b)
                                      ↓
                                READMEs filled
                                 (Step 7a fetch)
```

- `fetched.json` created in Step 5 with empty `readme` fields
- `kept.json` produced in Step 5b (description-based pre-screen)
- READMEs downloaded in Step 7a **only for kept repos**
- `llm_scores.json` completed in Step 7a (purpose + fit rankings)
- `scored.json` produced in Step 7b (final weighted scores)

Each file is produced by a specific stage and consumed by the next. `validate.py` and `validate_scores.py` check intermediate outputs between stages.
