# Step 8 Output Format Examples

## Required Structure per Repo

```markdown
## 🥇 #1 owner/repo (score: 97.7)

**URL**: https://github.com/owner/repo
**Description**: [original description from GitHub]

**项目介绍**：
[Agent's own summary: what this project is, what problem it solves, technical highlights, use cases.
Do NOT copy description or README — write based on understanding.]

**为什么匹配你的意图**：
[Explain why this fits the user's specific scenario.
Must state: **直接价值** (direct match) or **间接价值** (partial match / solves a sub-problem).
If the project has defects (poor docs, stale maintenance), mention them here.]

**关键指标**：⭐ 30,079 | Zig | 今天活跃 | topics: `browser`, `headless`, `cdp`
**评分**：purpose=100, fit=100, trust=100, quality=100, infra=100, momentum=100, community=77.1
```

## Real Example (2026-05-07 run)

Intent: "Find headless browsers that run well in Docker/container environments"

### Direct Value Examples

**lightpanda-io/browser** (97.7) — Built from scratch in Zig for AI/automation, single binary, no Chromium deps.
**browserless/browserless** (94.2) — Docker-first headless Chrome service, description literally says "Deploy headless browsers in Docker."

### Indirect Value Examples

**ChromeDevTools/chrome-devtools-mcp** (74.5) — Not a headless browser, but solves "let AI agents control browsers" — part of the user's problem chain.
**microlinkhq/browserless** (74.8) — Headless Chrome as API service, lighter than browserless/browserless, useful if user needs REST API not direct control.

## Output Rules

1. Only output **Top 5-10**, never all
2. "项目介绍" must be in Agent's own words
3. "为什么匹配你的意图" must state direct or indirect value
4. Defects of high-scoring projects must be mentioned
5. Even low-match repos should explore potential indirect value
