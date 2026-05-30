# 0530 — Excel Import and Basic Checks

Living document. Maintain per docs/PLANS.md.

## Purpose

After this plan is complete, the user can upload a Jira time-sheet export file
(.xls, HTML-based) through the web UI, see all worklog entries in a table, run
automated checks (permitted tasks + production calendar for RU/KZ/BY), and view
the results with color-coded status per employee.

This is the core data pipeline of the application: file in, structured data out,
checks applied, results displayed.

## Input File Format

The Jira export is an HTML table saved with `.xls` extension. It cannot be read
by openpyxl or xlrd — it requires an HTML parser (pandas `read_html` with lxml).

A sample file is at `data/input/Time Sheet Report 2026.05.xls` (~1679 rows).

Columns (8 total):

    Project           — project name, e.g. "Административная работа"
    Type              — task type, e.g. "Согласование договора", "Прочее"
    Key               — Jira issue key, e.g. "ADM-62648"
    Title             — issue title (free text, Russian)
    Started           — date+time, format "DD.MM.YYYY HH:MM"
    Username          — employee full name in Russian, e.g. "Фомина Екатерина"
    Time Spent (Hours) — decimal hours, e.g. 0.067, 0.183, 8.0
    Comment           — worklog comment (free text, may be just "Working on issue XXX")

HTML cells for Project and Key contain `<a href="...">` links to Jira. The parser
must extract the text content, ignoring the links.

## Phases

### Phase 1 — Backend: Excel parser service

Create a service that reads the HTML-based .xls file and returns structured data.

Files to create:
- `backend/app/schemas/worklog.py` — Pydantic model `WorklogEntry` with fields:
  project (str), task_type (str), key (str), title (str), started (datetime),
  username (str), hours (float), comment (str).
- `backend/app/services/excel_parser.py` — function `parse_worklog_file(file_path_or_bytes)`
  that uses `pandas.read_html()` with lxml engine, cleans HTML artifacts from cell
  values, parses dates from "DD.MM.YYYY HH:MM" format, converts hours to float,
  and returns a list of `WorklogEntry`. Must handle both file path (str) and
  file-like object / bytes (for API upload).
- `backend/tests/test_excel_parser.py` — tests using the sample file at
  `data/input/Time Sheet Report 2026.05.xls`. Verify: correct number of rows parsed,
  date parsing works, hours are numeric, all 8 columns are present, no HTML tags
  in text fields.

Update `backend/requirements.txt` to add `lxml` if not already there.

Verification: run `python -m pytest backend/tests/test_excel_parser.py` from project
root — all tests pass. Alternatively run `python -c "from app.services.excel_parser
import parse_worklog_file; entries = parse_worklog_file(r'data/input/Time Sheet Report
2026.05.xls'); print(len(entries), entries[0])"` from `backend/` directory — prints
the count and the first parsed entry.

### Phase 2 — Backend: upload API and database models

Create database models and API endpoints for file upload and worklog storage.

Files to create:
- `backend/app/models/upload.py` — SQLAlchemy model `Upload`: id (int, PK),
  filename (str), uploaded_at (datetime), row_count (int), status (str: "parsed"
  or "checked").
- `backend/app/models/worklog.py` — SQLAlchemy model `WorklogEntry`: id (int, PK),
  upload_id (FK to Upload), project (str), task_type (str), key (str), title (str),
  started (datetime), username (str), hours (float), comment (str).
- `backend/app/models/__init__.py` — import all models so Base.metadata knows them.
- `backend/app/schemas/upload.py` — Pydantic response models for Upload.
- `backend/app/api/uploads.py` — FastAPI router with:
  - `POST /api/uploads` — accepts multipart file upload, calls excel_parser, saves
    Upload + WorklogEntry rows to SQLite, returns Upload with row_count.
  - `GET /api/uploads` — returns list of all uploads (id, filename, date, row_count).
  - `GET /api/uploads/{id}/worklogs` — returns all WorklogEntry rows for an upload,
    with optional query parameter `?username=...` for filtering.

Update `backend/app/main.py`:
- Import Base from database.py and all models.
- Add `Base.metadata.create_all(bind=engine)` on startup so SQLite tables are
  created automatically.
- Register the uploads router.

Verification: start the backend with `uvicorn app.main:app --reload` from
`backend/` directory. Upload the sample file via curl or the Swagger UI at
`http://localhost:8000/docs`:

    curl -X POST http://localhost:8000/api/uploads -F "file=@data/input/Time Sheet Report 2026.05.xls"

Response should be JSON with upload id and row_count ~1679.
Then `GET http://localhost:8000/api/uploads/1/worklogs` returns the parsed rows.

### Phase 3 — Frontend: file upload UI and worklog table

Create the upload page and data display following `docs/brandbook.html`.

Install additional shadcn components: Table, Card, Input, Badge, Skeleton (for
loading states).

Files to create or modify:
- `frontend/src/app/page.tsx` — replace the placeholder with the upload page layout:
  a card with drag-and-drop area / file picker button, and below it a data table
  showing worklog entries after upload.
- `frontend/src/components/upload-zone.tsx` — drag-and-drop + file input component.
  Sends the file to `POST /api/uploads` via fetch (proxied through next.config.ts).
- `frontend/src/components/worklog-table.tsx` — table component: columns for
  Username, Date (formatted), Project, Key, Title, Hours, Comment. Sortable by
  username. Filter dropdown by employee name.
- `frontend/src/lib/api.ts` — API helper functions: uploadFile(), getUploads(),
  getWorklogs(uploadId, username?).

Verification: start both backend and frontend. Open `http://localhost:3000`.
Upload the sample file via the UI. The table should display ~1679 rows with
correct data. Filtering by employee should narrow the table.

### Phase 4 — Backend: checks (permitted tasks + production calendar)

Create the automated checking services.

Files to create:
- `backend/app/services/checker.py` — function `run_checks(upload_id, db)` that:
  1. Loads all WorklogEntry rows for the upload.
  2. For each entry, checks if the project/key is in the permitted list.
  3. For each employee, sums hours per month and compares to expected hours
     based on working days in that month (from the calendar service).
  4. Returns a list of CheckResult objects.
- `backend/app/services/calendar.py` — production calendar for RU, KZ, BY.
  Function `get_working_days(country, year, month)` returns the count of working
  days. For Phase 1 use hardcoded 2026 calendars (holidays for each country).
  Function `get_expected_hours(country, year, month)` = working_days * 8.
- `backend/app/services/permitted_tasks.py` — for Phase 1, load the permitted
  task list from a local JSON config file `backend/config/permitted_tasks.json`.
  Format: a list of objects with "project" and optional "key" fields. If only
  "project" is specified, all keys under that project are permitted.
- `backend/app/models/check_result.py` — SQLAlchemy model `CheckResult`: id,
  upload_id (FK), username (str), check_type (str: "permitted_task" or
  "hours_mismatch"), severity (str: "error" or "warning"), message (str),
  details (str, JSON).
- `backend/app/schemas/check.py` — Pydantic models for check results.
- `backend/app/api/checks.py` — FastAPI router:
  - `POST /api/uploads/{id}/check` — runs all checks, saves results, updates
    Upload status to "checked".
  - `GET /api/uploads/{id}/results` — returns check results, optionally filtered
    by `?username=...`.
- `backend/config/permitted_tasks.json` — initial permitted task list. Populate
  with a few sample projects from the sample file (e.g. "ADM" as permitted).

Update `backend/app/main.py` to register the checks router.

Verification: after uploading the sample file, run the checks via Swagger UI:

    POST http://localhost:8000/api/uploads/1/check

Then fetch results:

    GET http://localhost:8000/api/uploads/1/results

The response should contain check results: some employees may have hours mismatches,
some entries may reference non-permitted tasks.

### Phase 5 — Frontend: check results display and final integration

Create the results UI and connect the full pipeline.

Files to create or modify:
- `frontend/src/components/check-results.tsx` — component showing check results
  per employee. Each employee row: name, total hours, expected hours, status
  (OK / warning / error). Expandable to see individual issues. Color-coded:
  green = OK, yellow = warning, red = error. Follow `docs/brandbook.html` colors.
- `frontend/src/components/check-button.tsx` — "Run Checks" button that calls
  `POST /api/uploads/{id}/check` and then refreshes results.
- `frontend/src/app/page.tsx` — update the main page to show the full flow:
  upload area at the top, worklog table in the middle, check results at the bottom.
  The check results section appears after checks are run.
- `frontend/src/lib/api.ts` — add functions: runChecks(uploadId), getResults(uploadId).

Verification: open `http://localhost:3000`, upload the sample file, see the data
table, click "Run Checks", and see color-coded results appear below. Employees
with issues should be highlighted in red/yellow; employees with correct hours and
only permitted tasks should be green.

## Validation

The complete end-to-end flow after all 5 phases:

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000`
4. Upload `data/input/Time Sheet Report 2026.05.xls`
5. See ~1679 worklog entries in the table
6. Filter by employee name — table narrows correctly
7. Click "Run Checks"
8. See results: hours comparison per employee, flagged non-permitted tasks
9. Color-coded status: green (OK), yellow (warning), red (error)

Backend API should also work independently via Swagger at `http://localhost:8000/docs`.

## Decision Log

- Decision: Use pandas.read_html() with lxml to parse the HTML-based .xls files.
  Rationale: The Jira export is HTML masquerading as .xls. openpyxl and xlrd both
  fail on this format. pandas.read_html() handles it correctly and is already in
  our requirements.txt.
  Date: 2026-05-30

- Decision: Use hardcoded 2026 production calendars instead of an external API.
  Rationale: For Phase 1 (local deployment), a hardcoded calendar is simpler and
  has no external dependencies. Can be replaced with an API or database-driven
  calendar later.
  Date: 2026-05-30

- Decision: Use a local JSON file for permitted tasks instead of Google Docs.
  Rationale: Google Docs integration is a separate piece of work. For this plan,
  a local config file lets us build and test the checking logic independently.
  Date: 2026-05-30

- Decision: lxml is required as an additional dependency.
  Rationale: pandas.read_html() needs either lxml or html5lib as a parser backend.
  lxml is faster and more reliable for this use case.
  Date: 2026-05-30

## Surprises & Discoveries

- Observation: Jira exports .xls files that are actually HTML tables, not real
  Excel binary format. Both xlrd and openpyxl fail with "Expected BOF record;
  found b'<html><h'".
  Evidence: Attempting to open the sample file with xlrd raises
  `XLRDError: Unsupported format, or corrupt file`.

- Observation: The HTML uses nested tables — an outer layout table wraps the
  data table. `pd.read_html()` returns both; we must pick the one whose columns
  match the expected header.
  Date: 2026-05-30

- Observation: Jira uses `<td>` (not `<th>`) for the header row, so
  `pd.read_html()` assigns integer column names. The parser promotes the first
  data row to column headers when the expected names are found there.
  Date: 2026-05-30

- Observation: The table has a "Total" footer row with empty cells that become
  NaN. Rows with NaN in the "Started" column are dropped before parsing.
  Date: 2026-05-30

- Observation: Some Jira issue titles contain literal `>` characters (e.g.
  "ADM-69362>DBKZ 2026:…"). HTML-tag detection must check for `<tag>` patterns,
  not individual `<`/`>` chars.
  Date: 2026-05-30

## Outcomes & Retrospective

### Phase 1 — COMPLETED (2026-05-30)

Files created:
- `backend/app/schemas/worklog.py` — Pydantic model with 8 fields
- `backend/app/services/excel_parser.py` — parser using `pd.read_html(flavor="lxml")`
- `backend/tests/__init__.py`
- `backend/tests/test_excel_parser.py` — 8 tests, all passing

Files modified:
- `backend/requirements.txt` — added `lxml==5.4.0`

Verification: `python -m pytest backend/tests/test_excel_parser.py -v` — 8 passed.
Sample file parses to 1679 worklog entries.

### Phase 2 — COMPLETED (2026-05-30)

Files created:
- `backend/app/models/upload.py` — SQLAlchemy model `Upload` (id, filename, uploaded_at, row_count, status)
- `backend/app/models/worklog.py` — SQLAlchemy model `WorklogEntry` (8 data fields + id + upload_id FK)
- `backend/app/models/__init__.py` — imports both models for Base.metadata registration
- `backend/app/schemas/upload.py` — Pydantic response models (UploadResponse, UploadListItem)
- `backend/app/api/uploads.py` — FastAPI router: POST /api/uploads, GET /api/uploads, GET /api/uploads/{id}/worklogs

Files modified:
- `backend/app/main.py` — added lifespan (create_all), registered uploads router
- `backend/app/schemas/worklog.py` — added `model_config = {"from_attributes": True}` for ORM compatibility
- `backend/requirements.txt` — added `python-multipart==0.0.20`

Verification:
- `POST /api/uploads` with sample file → 200, row_count=1679, status="parsed"
- `GET /api/uploads` → list with 1 upload
- `GET /api/uploads/1/worklogs` → 1679 entries
- `GET /api/uploads/1/worklogs?username=Фомина Екатерина` → 274 filtered entries
- All 8 Phase 1 tests still pass
