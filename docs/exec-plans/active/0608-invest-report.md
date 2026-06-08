# 0608 — Investment direction allocation and reporting

Living document. Maintain per docs/PLANS.md.

## Purpose

After this plan is complete, the user can — after running checks on a worklog
upload — select which employees need investment direction analysis, fill in
manual allocations through the web UI (percentages for shared tasks, project
assignments for ambiguous tasks), and download an Excel report with a dedicated
"Инвест-направления" sheet that summarises hours allocated to investment
projects (primarily MENA).

This replaces a fully manual process where the user cross-references multiple
spreadsheets to determine how many hours each employee spent on investment
projects.

## Current State

The rules file `data/input/Issues CHANGE (2).xlsx` (sheet "LOG") already
contains columns A-H used by the permitted-task checker.  Two new columns have
been added by the user:

- **Column I** ("Инвест направление"): investment direction name, e.g.
  `"MENA"` or `"MENA / другой"`.
- **Column J** ("Распределение для инвест"): allocation method — empty,
  `"руками, задавая процент"`, `"руками"`, or
  `"по BUH company из дополнительной выгрузки"`.

Additionally, the user uploads CSV exports from GBS JIRA through the web UI
each time (these files are always new for each review period).  Each CSV
contains a `Custom field (BUH Company)` column, used to resolve which
investment project a task belongs to.

The current parser `backend/app/services/permitted_tasks.py` reads columns A-H
only; columns I-J are ignored.  No invest-related logic exists yet.

## Allocation Types

Tasks with invest data fall into four categories:

### Type 1 — Fully automatic (I="MENA", J=empty)

18 task keys, all UAE and Saudi Arabia tasks.  100% of logged hours go to MENA
automatically.  No user input needed.

Example keys: BUH-73282, BUH-73284, BUH-105068, BUH-73328.

### Type 2 — Manual percentage (I="MENA / другой", J="руками, задавая процент")

~35 task keys.  These are shared tasks (team management, training, HR, mail,
etc.) where the user manually decides what percentage of each employee's hours
on that task goes to an investment project.

Example keys: BUH-73000 (Управление командой), BUH-73280, BUH-73138.

### Type 3 — Manual project assignment (I="MENA / другой", J="руками")

2 project+type rules: `BUH / Прочее`, `HR / Civil law contract`.  The user
manually assigns which investment project the entire log entry belongs to.

### Type 4 — BUH company from CSV (I="MENA / другой", J="по BUH company из дополнительной выгрузки")

3 project+type rules:
- `BUH / Подготовка актов и счетов`
- `Административная работа / Прочее`
- `Административная работа / Согласование договора`

The user uploads CSV exports (UTF-8-BOM) through the web UI during the invest
allocation workflow.  These files are always new for each review period.  Each
row has an `Issue key` and `Custom field (BUH Company)`.  The system matches
worklog entries by issue key and resolves the invest project from the BUH
Company value:

- `DBFZ - Databorn FZ LLC` → MENA
- `DBSA - Databorn Company Limited LLC` → MENA
- `DBAD - Databorn FZ LLC Abu Dhabi` → MENA

If a worklog key is not found in the CSV files, or the BUH Company does not
match any of the above, the entry is shown as "requires manual assignment" and
the user assigns the invest project through the UI (same as Type 3).

Note: `FM / Task` was previously listed in the rules file with a "по BUH
company" allocation, but the user has confirmed that FM tasks do not participate
in invest allocation.  The user will remove this row from the rules file before
Phase 1.

## User Workflow

1. Upload worklog file, run checks (existing flow, unchanged).
2. Select which employees need invest allocation (new UI section).
3. Upload BUH company CSV files (one or more) for the current period.
4. Fill in manual allocations in the UI:
   - Set percentages for shared tasks (Type 2).
   - Assign invest project for ambiguous tasks (Types 3 + unmatched Type 4).
5. Download Excel report — it now contains an "Инвест-направления" sheet with
   all auto-calculated and manually-entered allocations.

## Phases

### Phase 1 — Backend: parse invest metadata and BUH company CSV

This phase adds the ability to read invest-related data from the rules file and
CSV exports.  No UI changes, no database changes.

**1a. Extend the permitted-tasks parser.**

In `backend/app/services/permitted_tasks.py`:

- Add two fields to the `KeyRule` dataclass: `invest_direction: str = ""`
  and `invest_allocation: str = ""`.  Do the same for `ProjectTypeRule`.
- In `load_permitted_tasks()`, read column I (index 8) as `invest_direction`
  and column J (index 9) as `invest_allocation`.
- Normalize `invest_allocation` to one of four constants defined in the same
  module: `INVEST_AUTO = "auto"` (when column J is empty but column I is
  filled), `INVEST_MANUAL_PERCENT = "manual_percent"`, `INVEST_MANUAL_PROJECT
  = "manual_project"`, `INVEST_BUH_COMPANY = "buh_company"`.  Store the raw
  value if it does not match.
- Add a method to `PermittedTasksRegistry`:
  `get_invest_info(key: str, project: str, task_type: str) -> tuple[str, str] | None`.
  Returns `(invest_direction, invest_allocation)` or `None` if the task has no
  invest data.  Lookup order is the same as `check()`: key rule first, then
  project+type rule.

**1b. Create BUH company CSV parser.**

New file `backend/app/services/buh_company.py`.  The CSV files are uploaded by
the user each time (they are always new for each review period), so the parser
works with in-memory file content, not with files on disk.

- `parse_buh_csv(file_content: bytes) -> dict[str, str]` — parses a single
  CSV file (UTF-8-BOM encoding) and returns a dict mapping `Issue key` to the
  value of `Custom field (BUH Company)`.  Locates columns by header name (not
  by index) since different exports may have different column counts.
- `merge_buh_companies(files: list[bytes]) -> dict[str, str]` — parses
  multiple CSV files and merges the results.  If the same key appears in
  multiple files, the last file wins.
- `MENA_BUH_COMPANIES`: a set of BUH Company values that map to MENA
  (`{"DBFZ - Databorn FZ LLC", "DBSA - Databorn Company Limited LLC",
  "DBAD - Databorn FZ LLC Abu Dhabi"}`).
- `resolve_invest_project(buh_company: str) -> str | None` — returns `"MENA"`
  if `buh_company` is in `MENA_BUH_COMPANIES`, `None` otherwise.

**Verification.** Start the backend, then in a Python shell:

```python
from app.services.permitted_tasks import load_permitted_tasks
from app.services.buh_company import parse_buh_csv, resolve_invest_project

reg = load_permitted_tasks()
# Type 1 — auto MENA
assert reg.get_invest_info("BUH-73282", "BUH", "Task") == ("MENA", "auto")
# Type 2 — manual percent
assert reg.get_invest_info("BUH-73000", "BUH", "Task")[1] == "manual_percent"
# No invest data
assert reg.get_invest_info("BUH-72946", "BUH", "Task") is None

# Test CSV parsing with a sample file
with open("../data/input/GBС JIRA 2026-06-08T20_33_49+0300.csv", "rb") as f:
    buh = parse_buh_csv(f.read())
assert "BUH-119430" in buh
assert resolve_invest_project(buh["BUH-119430"]) == "MENA"
print("All checks passed")
```

### Phase 2 — Frontend + Backend: employee selection and manual allocation UI

This phase adds the full user-facing workflow for invest allocation.  After
checks complete, the user picks employees, reviews auto-determined allocations,
fills in manual ones, and saves.  All data is persisted in the database so the
Excel report (Phase 3) can use it.

**2a. Database models.**

New file `backend/app/models/invest_allocation.py` with two models:

`InvestEmployeeSelection` stores which employees the user selected for invest
analysis:
- `id` (Integer, PK, autoincrement)
- `upload_id` (Integer, FK → uploads, not null)
- `username` (String, not null) — employee full name

`InvestAllocation` stores manual allocations entered by the user:
- `id` (Integer, PK, autoincrement)
- `upload_id` (Integer, FK → uploads, not null)
- `username` (String, not null) — employee full name
- `task_key` (String, not null) — Jira issue key
- `invest_project` (String, not null) — e.g. "MENA"
- `percentage` (Float, not null) — 0–100 for Type 2; 100 for Types 3/4
- `allocation_type` (String, not null) — "manual_percent", "manual_project",
  or "buh_company_manual"

`BuhCompanyMapping` stores parsed CSV data (uploaded each time by the user):
- `id` (Integer, PK, autoincrement)
- `upload_id` (Integer, FK → uploads, not null)
- `task_key` (String, not null) — Jira issue key from CSV
- `buh_company` (String, not null) — raw BUH Company value
- `invest_project` (String, nullable) — resolved project ("MENA" or null)

All three models are imported in `backend/app/models/__init__.py` so that
`Base.metadata.create_all()` picks them up.

**2b. API endpoints.**

New file `backend/app/api/invest.py` with a FastAPI router (prefix
`/api/uploads`):

- `GET /{upload_id}/invest/employees` — returns a list of all employees from
  this upload, each with: `username`, `total_hours`, `has_invest_tasks` (bool).
  Also includes `selected: bool` indicating if the employee was previously
  selected.

- `PUT /{upload_id}/invest/employees` — accepts `{"usernames": ["...", ...]}`
  and saves the selection (replaces any previous selection for this upload).

- `POST /{upload_id}/invest/buh-csv` — accepts one or more CSV files
  (multipart form upload).  Parses them using `parse_buh_csv()` /
  `merge_buh_companies()`, stores the parsed key→company mapping in the
  database (new model `BuhCompanyMapping` with fields: `upload_id`, `task_key`,
  `buh_company`, `invest_project`).  Returns the count of matched/unmatched
  keys.

- `GET /{upload_id}/invest` — returns the full invest picture for selected
  employees:
  - `auto_entries`: list of {username, task_key, title, hours, invest_project}
    for Type 1 tasks.
  - `buh_entries`: list of {username, task_key, title, hours, buh_company,
    invest_project (or null)} for Type 4 tasks.
  - `manual_percent_entries`: list of {username, task_key, title, hours,
    invest_project (or null), percentage (or null)} for Type 2 tasks.
  - `manual_project_entries`: list of {username, task_key, title, hours,
    invest_project (or null)} for Type 3 + unmatched Type 4 tasks.
  - `saved_allocations`: list of saved `InvestAllocation` rows.
  - `invest_projects`: list of known invest project names (from column I
    values, e.g. ["MENA"]).

- `PUT /{upload_id}/invest` — accepts a list of allocation objects
  [{username, task_key, invest_project, percentage, allocation_type}] and saves
  them (replaces previous allocations for this upload).

Register the router in `backend/app/main.py`.

**2c. Frontend component.**

New file `frontend/src/components/invest-panel.tsx`.  This is a panel that
appears on the main page after checks are completed (status = "checked").
It contains three steps:

Step 1 — Employee selection and CSV upload.  A card with two parts:

(a) A drop zone for BUH company CSV files (same style as the main upload
zone).  The user drags one or more CSV files; they are uploaded via
`POST /{upload_id}/invest/buh-csv`.  A success message shows how many keys
were matched.  This step is optional — if no Type 4 tasks exist for the
selected employees, the drop zone is hidden.

(b) A list of all employees with checkboxes.  Each row shows: name, total
hours, and a badge showing whether they have invest-eligible tasks.
A "Далее" button saves the selection and advances to Step 2.

Step 2 — Manual allocations.  For each selected employee, a collapsible card
with:
- A read-only summary of auto-determined allocations (Type 1 hours, BUH
  company matches).
- An editable table for Type 2 tasks: columns are task key, title, hours,
  percentage input (number field, 0–100), invest project (default MENA).
- An editable table for Type 3 and unmatched Type 4 tasks: columns are task
  key, title, hours, invest project dropdown.
- A "Сохранить" button that PUTs all allocations for this upload.

Step 3 — Summary.  After saving, show a summary: total invest hours per
project across all selected employees.  The existing "Скачать отчёт" download
button now produces a report that includes the invest sheet.

Add API helper functions in `frontend/src/lib/api.ts`:
- `getInvestEmployees(uploadId)`, `saveInvestEmployees(uploadId, usernames)`
- `uploadBuhCsv(uploadId, files)` — uploads CSV files to the new endpoint
- `getInvestData(uploadId)`, `saveInvestAllocations(uploadId, allocations)`

Update `frontend/src/app/page.tsx` to render `<InvestPanel>` after
`<CheckResults>` when upload status is "checked".

Follow `docs/brandbook.html` for all visual styling.

**Verification.** Start both servers.  Upload the sample worklog, run checks.
The invest panel should appear.  Select 2–3 employees, verify that auto MENA
tasks and BUH company matches are shown read-only.  Enter percentages and
project assignments for manual tasks.  Click save, reload the page — the data
should persist.

### Phase 3 — Excel: add "Инвест-направления" sheet

This phase adds a new sheet to the existing Excel report that uses the saved
invest allocations from Phase 2.

In `backend/app/services/excel_report.py`, after creating the existing sheets
("Сводка", "Распределение", "Ошибки", "Недобор часов"), create a new sheet
"Инвест-направления" and insert it as the 3rd sheet (index 2).

The sheet contains four sections:

**Section 1 — Summary table** at the top.  Columns: Инвест-проект, Авто (ч),
По BUH company (ч), Ручное распределение (ч), Итого (ч).  One row per invest
project (e.g. MENA), plus a totals row.  Only includes data for selected
employees.

**Section 2 — Auto-allocated entries** (Type 1).  A table of all worklog
entries on pure MENA tasks for selected employees.  Columns: Сотрудник, Ключ,
Название задачи, Часы, Инвест-проект.  Sorted by employee, then by date.
Subtotal row at the bottom.

**Section 3 — BUH company entries** (Type 4).  A table of worklog entries
resolved via CSV.  Columns: Сотрудник, Ключ, Название задачи, Часы,
BUH Company, Инвест-проект.  Rows with a resolved project get a green
background fill.  Rows manually assigned via the UI get a blue fill.  Rows
with no assignment get a yellow fill and "Не задано" text.  Subtotal row.

**Section 4 — Manual allocations** (Types 2, 3).  Columns: Сотрудник, Ключ,
Название задачи, Часы, Процент, Инвест-часы, Инвест-проект.  "Инвест-часы"
is calculated as hours × percentage / 100.  Rows with saved allocations show
the values; rows without show yellow "Не задано".  Subtotal row.

Styling follows `docs/brandbook.html` tokens — same approach as existing
sheets (Calibri font, brandbook colors, thin borders, frozen header row per
table).

The report endpoint `GET /api/uploads/{upload_id}/report` does not change — it
already calls `generate_report()` which will now produce the extra sheet.

**Verification.** Upload the sample worklog, run checks, select employees in
the invest panel, fill in some manual allocations, and download the report.
Open the Excel file and verify:
- The "Инвест-направления" sheet is present as the 3rd sheet.
- Section 1 shows correct totals.
- Section 2 lists only auto MENA tasks for selected employees.
- Section 3 shows BUH company matches with correct color coding.
- Section 4 shows manual allocations with calculated invest hours.
- Styling matches the other sheets (fonts, colors, borders, freeze panes).

## Validation

End-to-end verification after all three phases:

1. Start backend: `cd backend && uvicorn app.main:app --reload --port 8001`
2. Start frontend: `cd frontend && npm run dev`
3. Ensure the user has removed FM/Task from invest rules in the xlsx file.
4. Open `http://localhost:3000`.
5. Upload `data/input/Time Sheet Report 2026.05.xls`.
6. Click "Запустить проверку" — wait for completion.
7. In the invest panel, upload BUH company CSV files (drag and drop).
8. Select employees for analysis, click "Далее".
9. Review auto-determined MENA tasks (read-only).
10. Enter percentages for shared tasks, assign projects for ambiguous tasks.
11. Click "Сохранить".
12. Click "Скачать отчёт" — browser downloads `TimeAudit_Report_X.xlsx`.
13. Open Excel and verify the "Инвест-направления" sheet contains correct
    data across all four sections.

## Decision Log

- Decision: DBAD (Databorn FZ LLC Abu Dhabi) maps to MENA.
  Rationale: Confirmed by user — it is the same group as DBFZ and DBSA.
  Date: 2026-06-08

- Decision: FM/Task is excluded from invest allocation.
  Rationale: User confirmed that FM tasks do not participate in invest
  allocation.  The user will remove the FM/Task row from the rules file.
  Date: 2026-06-08

- Decision: Worklog keys not found in BUH company CSV files are treated as
  "requires manual assignment" rather than "not invest".
  Rationale: The CSV exports may be incomplete.  The user prefers to manually
  assign projects for unmatched keys.
  Date: 2026-06-08

- Decision: Phase 2 (UI) comes before Phase 3 (Excel sheet).
  Rationale: The user fills in manual allocations first, then downloads the
  report.  The Excel sheet reads saved allocations from the database.
  Date: 2026-06-08

- Decision: Before filling allocations, the user selects which employees need
  invest analysis.
  Rationale: Not all employees are relevant for invest allocation.  The user
  wants control over who is included.
  Date: 2026-06-08

## Surprises & Discoveries

- The CSV files use UTF-8-BOM encoding and have a Cyrillic "С" in the
  filename prefix ("GBС" not "GBS").  The glob pattern must account for this.
  Date: 2026-06-08

- Different CSV files have different numbers of columns (19 vs 25) because
  the "Labels" field is split into multiple columns in some exports.  The
  parser should locate `Custom field (BUH Company)` and `Issue key` by
  header name, not by column index.
  Date: 2026-06-08

- Of 125 worklog keys matching BUH company rules, only 71 are found in the
  provided CSV files.  54 keys (mostly ADM-* and FM-*) are missing.
  Date: 2026-06-08

- All BUH Company values in the sample CSV files map to MENA companies
  (DBFZ: 343 rows, DBSA: 57 rows, DBAD: 24 rows).  No non-MENA companies
  were observed in the sample data.
  Date: 2026-06-08

## Outcomes & Retrospective

### Phase 1 — COMPLETED (2026-06-08)

Files created:
- `backend/app/services/buh_company.py` — BUH company CSV parser with MENA
  company resolution

Files modified:
- `backend/app/services/permitted_tasks.py` — added invest_direction and
  invest_allocation fields to KeyRule/ProjectTypeRule, INVEST_* constants,
  get_invest_info() method, _normalize_invest_allocation()

### Phase 2 — COMPLETED (2026-06-08)

Files created:
- `backend/app/models/invest_allocation.py` — InvestEmployeeSelection,
  InvestAllocation, BuhCompanyMapping models
- `backend/app/api/invest.py` — FastAPI router with 5 endpoints for invest
  workflow (employee listing/selection, BUH CSV upload, invest data
  retrieval, allocation save)
- `frontend/src/components/invest-panel.tsx` — 3-step invest allocation UI

Files modified:
- `backend/app/models/__init__.py` — imported invest models
- `backend/app/main.py` — registered invest router
- `frontend/src/lib/api.ts` — added invest API helpers
- `frontend/src/app/page.tsx` — rendered InvestPanel after CheckResults

### Phase 3 — COMPLETED (2026-06-08)

Files modified:
- `backend/app/services/excel_report.py` — added "Инвест-направления" sheet
  as the 3rd sheet (index 2) with 4 sections: summary table, auto-allocated
  entries (Type 1), BUH company entries (Type 4) with color-coded rows
  (green=CSV resolved, blue=manually assigned, yellow=not assigned), and
  manual allocations (Types 2/3) with calculated invest hours.  Added imports
  for invest models, permitted_tasks constants, and dataclass.  Updated
  generate_report() to create the invest sheet between "Распределение" and
  "Ошибки".
