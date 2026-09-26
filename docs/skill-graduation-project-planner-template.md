# Skill 範本：graduation-project-planner

目前 Codex 無法在此工作區建立 `.codex/` 目錄，因此先將 Skill 範本記錄於本檔案。

當 `.codex/` 可寫入後，建議建立：

```text
.codex/skills/graduation-project-planner/
├── SKILL.md
└── agents/
    └── openai.yaml
```

## `SKILL.md`

```markdown
---
name: graduation-project-planner
description: Guide Codex through undergraduate graduation project planning, scope control, requirement clarification, decision logging, risk tracking, and implementation planning. Use when the user is designing, evaluating, narrowing, documenting, or implementing a senior graduation project and wants Codex to proceed step by step in Traditional Chinese.
---

# Graduation Project Planner

Use Traditional Chinese by default.

## Workflow

1. Read `AGENTS.md`.
2. Read relevant files in `docs/`.
3. Identify the current stage:
   - background clarification
   - topic ideation
   - topic evaluation
   - requirement definition
   - technical planning
   - implementation
   - report or presentation preparation
4. Ask only the next necessary question when information is missing.
5. Record important decisions in `docs/decisions.md`.
6. Record risks in `docs/risks.md`.
7. Keep recommendations scoped to a graduation project that can realistically be completed.

## Evaluation Criteria

When evaluating a project idea, consider:

- completion feasibility
- technical difficulty
- learning cost
- demo value
- report value
- data availability
- deployment difficulty
- risk of over-scoping

## Output Style

- Use concise Traditional Chinese.
- Give tradeoffs before recommendations.
- Make clear what is a fact, assumption, or recommendation.
- Let the user make final decisions.
```

## `agents/openai.yaml`

```yaml
interface:
  display_name: "Graduation Project Planner"
  short_description: "規劃畢業專題並控制範圍"
  default_prompt: "Use $graduation-project-planner to help me plan and document my graduation project step by step."
```

