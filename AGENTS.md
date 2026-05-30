# Jira Time Log Checker

A web application for reviewing team time-logging compliance based on Excel worklog exports from Jira.

## Project Navigation

- **Product (goals, features, workflow):** `docs/product.md`
- **Technology stack:** `docs/tech.md`
- **Visual style (design system):** `docs/brandbook.html`

## Working Rules

- Communication language with the user: Russian
- All documentation and code comments must be written in English.
- The user is not a technical specialist. Explain simply and clearly.
- Do not execute destructive commands without confirmation.
- Do not work with files outside the project root.
- Before using third-party libraries — study their documentation.
- When working on the frontend and visual elements — always study `docs/brandbook.html` and follow it.

## Planning

- Planning system: `docs/PLANS.md`
- Active plans: `docs/exec-plans/active/`
- Completed plans: `docs/exec-plans/completed/`
- Tech debt tracker: `docs/exec-plans/tech-debt.md`

### When to create a plan

- **Simple tasks** (change text, recolor a button, fix a typo, add a comment) —
  execute immediately, no plan needed.
- **Complex tasks** (new feature, significant refactor, multi-file changes,
  integration with external service) — create an ExecPlan before writing code.
- **Explicit instruction** — if the user asks to "make a plan" or "create a plan",
  always create an ExecPlan regardless of complexity.

### How to structure phases

- Break the plan into phases. Each phase must be completable in a single chat
  session (roughly 50% of the context window).
- Aim for 3-7 phases per plan. Do not split work into 20+ micro-steps.
- Each phase should produce a meaningful, independently testable result.
- The user will start a new chat for each phase with an instruction like
  "execute phase N". The agent must read the ExecPlan, locate the phase,
  and execute it fully.

## Conventions

- `AGENTS.md` and `CLAUDE.md` are intentional duplicates (same content, different AI tools read them). Always update both when changing one.

## Growth Principle

This file and the `docs/` folder are the single source of truth for the project.
Documentation is supplemented as the project evolves: new decisions → new entries.
Do not add anything prematurely — only what has already been decided and confirmed.
