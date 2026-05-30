# Execution Plans (ExecPlans)

This document describes the requirements for an execution plan ("ExecPlan") — a design
document that a coding agent can follow to deliver a working feature or system change.

Treat the reader as a complete beginner to this repository: they have only the current
working tree and the single ExecPlan file you provide. There is no memory of prior plans
and no external context.

## How to use ExecPlans

**When authoring** an ExecPlan, follow this file to the letter. If it is not in your
context, re-read the entire `docs/PLANS.md` before proceeding. Start from the skeleton
at the bottom and flesh it out as you research.

**When implementing** an ExecPlan, do not prompt the user for "next steps" — simply
proceed to the next phase. Keep all living-document sections up to date. Resolve
ambiguities autonomously and commit frequently.

**When discussing** an ExecPlan, record decisions in the Decision Log so it is
unambiguously clear why any change to the specification was made.

## File location and naming

- Active plans live in `docs/exec-plans/active/`
- Completed plans are moved to `docs/exec-plans/completed/`
- File name format: `MMDD-short-name.md` (e.g. `0530-excel-import.md`)
- `MMDD` is the month and day the plan was created (4 digits)
- `short-name` is a brief English description using hyphens
- If two plans are created on the same day, they are distinguished by `short-name`

## Lifecycle

1. New task → create `docs/exec-plans/active/MMDD-name.md` using the skeleton below
2. Work in progress → record decisions, update living-document sections
3. Done → fill in Outcomes & Retrospective
4. Move the file from `active/` to `completed/`

## Non-negotiable requirements

- Every ExecPlan must be fully self-contained: it includes all knowledge and instructions
  needed for a novice to succeed.
- Every ExecPlan is a living document. Update it as discoveries occur and as design
  decisions are finalized.
- Every ExecPlan must produce a demonstrably working behavior, not merely code changes.
- Define every term of art in plain language or do not use it.

## Guidelines

- Purpose and intent come first. Begin by explaining why the work matters from a user's
  perspective: what someone can do after this change that they could not do before.
- Anchor the plan with observable outcomes. Phrase acceptance as behavior a human can
  verify ("after starting the server, navigating to /health returns HTTP 200") rather
  than internal attributes ("added a HealthCheck struct").
- Specify repository context explicitly. Name files with full repository-relative paths,
  name functions and modules precisely.
- Write in plain prose. Prefer sentences over lists.

## Phases

Break the work into phases. Each phase must be completable in a single agent
chat session (target: roughly 50% of the context window). Aim for 3-7 phases
per plan — not too granular.

Introduce each phase with a brief paragraph: scope, what will exist at the end,
and how to verify. Each phase must produce a meaningful, independently testable
result.

The user will execute phases one by one, starting a new chat for each phase
with "execute phase N".

## Skeleton of an ExecPlan

```md
# MMDD — Short, action-oriented description

Living document. Maintain per docs/PLANS.md.

## Purpose

Explain in a few sentences what someone gains after this change and how they can see
it working. State the user-visible behavior you will enable.

## Phases

### Phase 1 — Name

Describe the scope of this phase: what files to create or change, what to implement,
and what should work at the end. Each phase should be self-contained enough that an
agent can execute it in a single chat session.

### Phase 2 — Name

...

## Validation

Describe how to verify the final result. State exact commands to run and expected output.
If tests are involved, name them and describe what passes after the change.

## Decision Log

- Decision: ...
  Rationale: ...
  Date: ...

## Surprises & Discoveries

Document unexpected behaviors, bugs, or insights discovered during implementation.

- Observation: ...
  Evidence: ...

## Outcomes & Retrospective

Summarize what was achieved, what remains, and lessons learned. Compare the result
against the original purpose. Fill this in at completion.
```
