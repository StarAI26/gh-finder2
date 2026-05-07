---
name: gh-intents
category: meta
version: 13.0
description: Guide users to uncover true intent beyond surface requests via first-principles. / 引导用户跳出表象需求，通过第一性原理还原真实意图。
metadata:
  hermes:
    tags: [needs-discovery, intent-refinement, first-principles, clarify-requirements, true-needs]
---

# Needs Scout

> "We reason from first principles, not by analogy."

First-principles thinking is a tool to find better solutions — never a weapon to interrogate the user.
（使用第一性原理是思考工具，用来找到更优解，绝不是质问用户的武器。）

## When to Trigger

This skill is **primarily designed as the pre-search refinement step for `gh-finder2`**, but its questioning framework applies to any ambiguous request.

- **Trigger when**: User request is vague, mentions a means rather than a goal, or lacks key context (e.g., "找个好用的画图工具", "推荐个 CLI").
- **Skip when**: User already provided clear query + constraints + scope. Extract parameters directly — do NOT ask questions.
- **gh-finder2 integration**: In `gh-finder2`, offer this when intent is ambiguous. **Do NOT force a yes/no prompt on every search request.** If the user's request is already specific, proceed directly to search.

## Questioning Flow

Users ask for a *means*, not the end goal. Translate nouns into verbs, adjectives into constraints.
（用户要的是"手段"。把名词翻译成动词，形容词翻译成约束。）

### Step 1: Diagnose — is it clear?

Scan the user's request for these signals:

| Signal | Action |
|--------|--------|
| Clear query + tech/domain + constraints | Extract parameters, skip to Output |
| Only a vague noun ("找个XX") | Ask Step 2 |
| Mixed clarity (goal clear, scope missing) | Ask about the missing dimension only |

### Step 2: Core scenario (always first, if needed)

Start with the highest-level question. One question, conversational tone.

**Template**: "这个工具你打算用在什么场景？比如：[2-3 likely scenarios based on the request]"

- Give 2-3 options ordered by likelihood (your best guess first)
- Core dimensions = positive selection ("选你想要的")
- Let the user reject or add their own

### Step 3: Constraints + Exclusions (as needed)

After the core scenario is clear, ask about specifics. Use elimination for fine-grained items.

**Constraints template**: "有偏好的技术栈或运行环境吗？比如：[2-3 options]"

**Exclusions template**: "有没有确定不需要的？比如：[2-3 common exclusions]"

- Fine-grained items = elimination ("排除你不要的，剩下的默认需要")
- If user skips, that dimension doesn't matter — move on

### Step 4: Reconstruct — hardest step + better alternatives

Think: what's the hardest step to implement the user's intent? Show your analysis in the question, then let user pick:

**Hardest step template**: "[流程拆解 + 判断最难步骤]。你最在意哪些？[2-4 个选项]"

**Better alternative template**: "你提到的[用户说的]，其实[alternative]可能更合适，因为[1-sentence reason]。要看吗？"

One sentence max. Don't lecture.

### Rules for All Rounds

- **One question per round** — never stack questions.
- **Skip expressed preferences** — if user already said "要 Python 的", don't ask about language.
- **Options are your hypothesis** — order by likelihood. User selecting "Other" means your framing missed; re-think the next question.
- **When enough info**: offer "够了，开始搜索" as an option. Let the user confirm — don't stop unilaterally.

## Dialogue Examples

### Example 1: Vague request → refinement

**User**: "找个好用的画图工具"

**Round 1**:
> 这个画图工具你主要用在什么场景？
> 1. 生成流程图/架构图（比如 mermaid、draw.io 类）
> 2. 像素艺术/精灵图生成（比如 sprite-gen 类）
> 3. 数据可视化图表（比如 matplotlib 类）

**User**: 2

**Round 2**:
> 有偏好的输出格式吗？
> 1. SVG + CSS 动画（适合前端集成）
> 2. PNG 静态图
> 3. 都行，质量好最重要

**User**: 1

→ Extract thinking:
- 用户选了"像素艺术/精灵图" → 核心需求：pixel art / sprite generation
- 选了"SVG + CSS 动画" → 约束：输出 SVG，适合前端集成
- semantic query: "pixel art sprite generator"（意图方向）
- semantic query: "svg css animation generator"（约束方向）
- complexity query: "svg sprite sheet"（最难：多帧动画转单文件）

### Example 2: Hardest step check

**User**: "word 转 markdown 的 Python 项目"

**Round 1** (反面教材):
> 有偏好的格式或运行环境吗？
> 1. Python 本地脚本，不要在线服务
> 2. Web 前端集成
> 3. 都行

→ 错：用户目的是转换格式，不是选运行环境。语言/环境是可以被满足的约束，不是过程里的最难步骤。

**Round 1** (正确):
> word 转 markdown 拆开来看：
> - 文字段落容易，基本是粗体/列表/标题的对应
> - 表格比较麻烦，Markdown 不支持合并单元格，只能降级成 HTML
> - 图片好处理，提取后加引用就行
> - 公式最难，Word 的 MathML 转 LaTeX 经常丢失
> 你最在意哪些？
> 1. 表格完整保留
> 2. 公式准确转换
> 3. 图片提取+引用
> 4. 文字/排版准确

**User**: 1

→ Extract thinking:
- 用户选了"表格完整保留" → 拆解最难步骤：合并单元格（Markdown 原生不支持，必须降级成 HTML）
- exact queries: "python-docx"（读 docx 标准库）、"mammoth"（docx→md 知名项目）
- websearch queries: "markitdown"（Microsoft 通用文档转 md）、"pandoc"（通用转换器）
- semantic queries: "docx to markdown"（核心意图）、"word document parser"（更广的 docx 解析项目发现）
- complexity query: "docx table markdown"（最难步骤：表格结构转 markdown）

## When to Stop

- User selects "够了，开始搜索" → generate Search Result, proceed.
- User skips a round → that dimension doesn't matter, don't push.
- User gives a complete answer in one round → skip remaining rounds.

## Output: Search Result

After the conversation (or direct extraction), output this structured JSON:

```json
{
  "intent": {
    "summary": "The user's real core need, distilled from the conversation",
    "constraints": "Language, environment, exclusions, etc. Empty string if none",
    "insights": "Important context the user didn't mention but you discovered. Empty string if none"
  },
  "queries": [
    { "query": "python-docx", "reason": "De facto standard for reading docx in Python", "type": "exact" },
    { "query": "mammoth", "reason": "Well-known docx-to-markdown library", "type": "exact" },
    { "query": "markitdown", "reason": "Microsoft universal document-to-markdown converter, discovered via WebSearch", "type": "websearch" },
    { "query": "pandoc", "reason": "Universal document converter, discovered via WebSearch", "type": "websearch" },
    { "query": "docx to markdown", "reason": "Core intent: format conversion", "type": "semantic" },
    { "query": "word document parser", "reason": "Broader discovery: Word parsing libs", "type": "semantic" },
    { "query": "docx table markdown", "reason": "Hardest step: preserving tables in conversion", "type": "complexity" }
  ]
}
```

**Query type**:
- `"exact"`: The query is a known de facto standard project name specified by the user (e.g., `"python-docx"`, `"mammoth"`). GitHub API 返回的首条结果将作为种子项目。
- `"websearch"`: The query is a project name discovered via WebSearch (e.g., `"markitdown"`, `"pandoc"`). GitHub API 返回的首条结果将作为种子项目。
- `"semantic"`: The query describes the user's intent/functionally (e.g., `"docx to markdown"`). GitHub API 返回的首条结果将作为种子项目。
- `"complexity"`: The query targets the **hardest step** of implementing the user's intent. Think: if the user's goal were "把大象装冰箱" (open door → stuff elephant → close door), which step is the bottleneck? Search that. GitHub API 返回的首条结果将作为种子项目。

**Save**: Write the JSON to `cache/intent.json` (relative to gh-finder2 root, overwrite, file contains only JSON — no extra text).

**Query Rules**:
- `queries` array: 5-8 queries total. 2-3 exact + 1-2 websearch + 2-3 semantic + 1-2 complexity.
- Each query ≤3 words.
- De facto standard project names **must appear as standalone queries** with `"type": "exact"` (e.g., `"python-docx"`), never combined with other keywords. GitHub API uses AND logic — `"python-docx markdown"` misses the project itself.
- WebSearch discovered names use `"type": "websearch"` with reason mentioning source.
- Exclusions baked into broad queries only (e.g., `"docx parser -online"`), never on exact/websearch entity names.
