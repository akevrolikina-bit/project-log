# 0601 — Comment quality and relevance checks

Living document. Maintain per docs/PLANS.md.

## Purpose

After this plan is complete, the automated check pipeline includes two new check
types for worklog comments: a rule-based quality check that catches empty, default,
or too-short comments, and an AI-powered relevance check that evaluates whether each
comment matches the task it is logged against.  The user sees these results in the
existing check-results UI with the same color-coded traffic-light system.

## Phases

### Phase 1 — Rule-based comment quality checks (no AI)

Add a new service `backend/app/services/comment_rules.py` with function
`check_comment_quality(comment, key, title)` that detects:
- Empty or whitespace-only comments (severity: error)
- Default Jira comments like "Working on issue XXX" (severity: warning)
- Comments shorter than 10 meaningful characters (severity: warning)
- Comments that are exact copies of the task title (severity: warning)

Integrate into `backend/app/services/checker.py` as check #3 (after hours mismatch).
Results are stored as `CheckResult` with `check_type="comment_quality"`.

Update `frontend/src/components/check-results.tsx` to display the new check type
label "Качество комментария".

Verification: upload the May sample file, run checks.  Employees with empty or
default Jira comments appear in the results with comment_quality issues.

### Phase 2 — AI-powered comment relevance checks (OpenAI GPT-4o-mini)

Add `openai` to `backend/requirements.txt`.  Create service
`backend/app/services/comment_reviewer.py` with function `review_comments()` that
sends batches of worklog entries (task context + comment) to GPT-4o-mini and
receives a traffic-light verdict (green/yellow/red) with a short explanation.

The service skips entries already flagged by comment_quality rules to avoid
redundant API calls.  When `OPENAI_API_KEY` is not configured, the AI check
is silently skipped.

Integrate into `checker.py` as check #4 (after comment_quality).  Results are
stored with `check_type="comment_relevance"`.

Update `frontend/src/components/check-results.tsx` to display the label
"Соответствие комментария задаче".

Add `OPENAI_API_KEY` to `backend/.env.example` and `openai_api_key` to
`backend/app/config.py` Settings.

Verification: set `OPENAI_API_KEY` in `.env`, upload the sample file, run checks.
AI verdicts appear in the results for each employee.

### Phase 3 — Documentation and plan lifecycle

Move the completed `0530-excel-import.md` from `active/` to `completed/`.
Create this ExecPlan file `0601-comment-checks.md` in `active/`.

## Validation

The complete check pipeline now runs four checks in sequence:
1. Permitted tasks
2. Hours mismatch (vs production calendar)
3. Comment quality (rule-based)
4. Comment relevance (AI, optional — only when API key is set)

Start backend (`uvicorn app.main:app --reload`), start frontend (`npm run dev`),
upload the May sample file, click "Запустить проверку".  The results table shows
all four check types with appropriate severity levels and expandable details.

Without `OPENAI_API_KEY`, checks 1-3 still run normally; check 4 is skipped.

## Decision Log

- Decision: Use OpenAI GPT-4o-mini for AI comment review.
  Rationale: Cheapest available model (~$0.15/1M input tokens), fast, good Russian
  language understanding.  For ~1700 entries the cost is under $0.10.
  Date: 2026-06-01

- Decision: Batch comments in groups of 15 per API request.
  Rationale: Balances token efficiency with response quality.  Larger batches risk
  truncated responses; smaller batches increase API call count.
  Date: 2026-06-01

- Decision: Skip AI review for entries already flagged by rule-based checks.
  Rationale: Avoids spending tokens on comments we already know are problematic
  (empty, default Jira text, etc.).
  Date: 2026-06-01

- Decision: Gracefully skip AI check when OPENAI_API_KEY is not set.
  Rationale: The app should work without an API key — rule-based checks still
  provide value.  AI is an optional enhancement.
  Date: 2026-06-01

## Surprises & Discoveries

_None yet._

## Outcomes & Retrospective

### Phase 1 — COMPLETED (2026-06-01)

Files created:
- `backend/app/services/comment_rules.py` — rule-based comment quality checker
  with 4 rules (empty, default Jira, too short, title copy)

Files modified:
- `backend/app/services/checker.py` — added comment_quality check block (#3)
- `frontend/src/components/check-results.tsx` — added labels for comment_quality
  and comment_relevance check types

### Phase 2 — COMPLETED (2026-06-01)

Files created:
- `backend/app/services/comment_reviewer.py` — AI comment reviewer using
  OpenAI GPT-4o-mini with batching (15 per request), structured JSON output

Files modified:
- `backend/app/services/checker.py` — added AI comment_relevance check block (#4),
  imported comment_reviewer
- `backend/requirements.txt` — added `openai>=2.38.0`
- `backend/.env.example` — added `OPENAI_API_KEY`
- `backend/app/config.py` — added `openai_api_key` setting

### Phase 3 — COMPLETED (2026-06-01)

- Moved `docs/exec-plans/active/0530-excel-import.md` to `completed/`
- Created `docs/exec-plans/active/0601-comment-checks.md` (this file)
