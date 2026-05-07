---
name: gh-score
category: devops
version: 1.0
description: Score and rank fetched GitHub repos using Python + LLM. / 用 Python 确定性规则 + LLM 判断对项目打分排名。
metadata:
  hermes:
    tags: [scoring, ranking, relevance, readme-analysis]
---

# gh-score: Score + Rank GitHub Repos

> "Python measures signals. LLM judges fit."

## Workflow

```
gh-score is invoked
  ↓
1. Read fetched.json + intent.json
  ↓
2. Rank ALL repos by description → keep top 50% + seed repos
  ↓
3. For each kept repo, read its README → rank by purpose, rank by fit
  ↓
4. Save rankings to cache/llm_scores.json
  ↓
5. Python converts rankings to percentile scores + runs its 6 scorers → merges → outputs cache/scored.json
```

**You (the LLM) do steps 1-4.** Python handles step 5.

---

## Step 1: Read input

Two files:

### `cache/intent.json` — what the user wants

```json
{
  "intent": {
    "summary": "Convert Word/DOCX documents to Markdown format",
    "constraints": "Python preferred, no online/SaaS tools",
    "insights": ""
  },
  "queries": [ ... ]
}
```

### `cache/fetched.json` — all repos to evaluate

A JSON object with seed identification and a flat repo array:

```json
{
  "seed_repo_names": ["mwilliamson/python-mammoth", "jgm/pandoc"],
  "repos": [
    {
      "full_name": "mwilliamson/python-mammoth",
      "description": "Converts Word .docx files to HTML and markdown",
      "metrics": { ... },
      "activity": { ... },
      "releases": { ... },
      "readme": "# mammoth\n\nConverts Word documents to Markdown..."
    }
  ]
}
```

**Seed repos** (`seed_repo_names`): These are unconditionally kept for scoring. They come from:
- The first result of every GitHub Search API query
- Standard-type queries (de facto standard project names)

**You do NOT identify seeds yourself** — they are provided by gh-fetch. Use `kept_for_scoring` = top 50% by description ∪ `seed_repo_names`.

---

## Step 2: Pre-screen + rank (description only)

Read **only `description`** for every repo in `fetched.json`. Rank all repos by how well their description matches the user's intent.

Then keep two groups:

**Top 50%**: The highest-ranked repos by description relevance. The bottom 50% are eliminated — don't read their READMEs.

**Seed repos**: Read `seed_repo_names` from `cache/fetched.json`. These are provided by gh-fetch (first result of each query + standard-type queries). Unconditionally keep them even if their description didn't rank in the top 50%.

The repos that proceed to step 3 = top 50% ∪ seed repos.

---

## Step 3: Detail ranking (README + description)

For each **kept** repo (from step 2), read its `description` + `readme`. Produce two separate rankings:

### Purpose ranking

Rank all kept repos from **most relevant to least relevant** to the user's intent.

Question: **Which project's core function best matches what the user wants?**

- The #1 project does exactly what the user needs, no ambiguity
- The #N project barely relates to the user's need

You don't need to give scores. Just rank them: #1, #2, #3, ... N.

### Fit ranking

Rank all kept repos from **best fit to worst fit** for the user's specific scenario.

Question: **Given the user's constraints and context, which project is the best overall fit?**

Consider: complexity (over-engineered vs under-baked), scope (standalone tool vs library), target user, language preference.

Again, just rank them: #1, #2, #3, ... N.

**You output two ordered lists. Python converts them to scores.**

---

## Step 4: Output

Save your rankings to `cache/llm_scores.json`:

```json
{
  "prescreen_ranking": [
    {"full_name": "mwilliamson/python-mammoth", "rank": 1, "reason": "Converts Word .docx to markdown, exactly matches intent"},
    {"full_name": "pandoc/pandoc", "rank": 2, "reason": "Universal converter, handles docx→md"},
    {"full_name": "Zettlr/Zettlr", "rank": 45, "reason": "Note-taking app, not directly relevant"}
  ],
  "kept_for_scoring": ["mwilliamson/python-mammoth", "pandoc/pandoc", "jgm/pandoc", "..."],
  "purpose_ranking": [
    {"full_name": "mwilliamson/python-mammoth", "rank": 1, "reason": "README: 'Converts Word documents to Markdown' — exact match"},
    {"full_name": "pandoc/pandoc", "rank": 2, "reason": "Does docx→md but also 50 other formats"},
    {"full_name": "python-openxml/python-docx", "rank": 3, "reason": "Can read docx but doesn't convert to md out of the box"}
  ],
  "fit_ranking": [
    {"full_name": "mwilliamson/python-mammoth", "rank": 1, "reason": "Simple Python library, clean API, exactly the right scope"},
    {"full_name": "pandoc/pandoc", "rank": 2, "reason": "Powerful but overkill — user just wants docx→md"},
    {"full_name": "python-openxml/python-docx", "rank": 3, "reason": "Good library but requires user to write conversion logic"}
  ]
}
```

- `prescreen_ranking`: **every repo**, ranked by description relevance
- `kept_for_scoring`: top 50% by description ∪ `seed_repo_names` from `fetched.json`
- `purpose_ranking`: **kept repos only**, ranked #1 to #N
- `fit_ranking`: **kept repos only**, ranked #1 to #N

---

## Step 5: Python merge (automatic)

Python takes your rankings and converts them to scores:

**Percentile mapping**: For a repo ranked #R out of N kept repos:
- Percentile = (N - R + 1) / N × 100
- This maps #1 → 100, middle → 50, last → ~0

**Purpose score** (weight: 30) = percentile from your purpose_ranking.

**Fit score** (weight: 20) = percentile from your fit_ranking.

Then Python runs its 6 deterministic scorers: community(10) + trust(15) + quality(10) + momentum(5) + infrastructure(10) + search_fit(0) = 50 total, merges everything → weighted composite → sorts → outputs `cache/scored.json`.

Unkept repos get purpose=0, fit=0 — they can't win.
