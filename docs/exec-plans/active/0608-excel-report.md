# 0608 — Generate Excel report with per-employee sheets and summary

Living document. Maintain per docs/PLANS.md.

## Purpose

After this plan is complete, the user can click a "Download Report" button in the
web UI after running checks, and receive an Excel file (.xlsx) with a dedicated
sheet for each employee (showing their worklogs and flagged issues) plus two
summary sheets: one with an overview of all employees and their statuses, and one
with time distribution by projects and regions.  This is the primary deliverable
of the MVP described in `docs/product.md`: "Generate Excel (separate sheet per
employee)" and "Summary report by projects and regions (for management)".

## Current State

The application already supports:
- Uploading a Jira worklog export (`backend/app/api/uploads.py`)
- Parsing it into `WorklogEntry` rows stored in SQLite
  (`backend/app/services/excel_parser.py`, `backend/app/models/worklog.py`)
- Running six automated checks: permitted tasks, hours mismatch, comment quality,
  comment relevance (AI), time limits, general rules
  (`backend/app/services/checker.py`)
- Storing check results as `CheckResult` rows
  (`backend/app/models/check_result.py`)
- Displaying results in the frontend with expandable per-employee rows
  (`frontend/src/components/check-results.tsx`)

The `openpyxl` library (v3.1.5) is already in `backend/requirements.txt`.
No new dependencies are required.

## Data Available for the Report

Each `WorklogEntry` has: project, task_type, key, title, started (datetime),
username, hours (float), comment (text).

Each `CheckResult` has: username, check_type (e.g. "permitted_task",
"hours_mismatch", "comment_quality", "comment_relevance", "time_limit",
"general_rules"), severity ("error" or "warning"), message, details (JSON string).

Employee-to-country mapping is in `backend/config/employee_countries.json`.
Production calendar norms are in `backend/app/services/calendar.py`.

## Report Structure

The generated Excel file will contain the following sheets:

### Sheet "Сводка" (Summary)

A table with one row per employee, sorted alphabetically:

| Column | Content |
|--------|---------|
| Сотрудник | Full name |
| Страна | Country code (RU/KZ/BY) |
| Факт, ч | Total logged hours |
| Норма, ч | Expected hours from production calendar |
| Разница | actual − expected |
| Статус | OK / Внимание / Ошибка |
| Замечания | Count of check result issues |

Below the table: totals row with sum of hours.

### Sheet "Распределение" (Distribution)

A pivot table showing hours by project (rows) and employee (columns).
The rightmost column is "Итого" (total per project).  The bottom row is
"Итого" (total per employee).  An additional section below groups employees
by country and shows totals by region.

### Per-employee sheets (one per person)

Sheet name is the employee's last name (truncated to 31 chars — Excel limit).

Each sheet contains:
1. **Header area** (rows 1-3): employee full name, country, period (min–max dates
   from their worklogs).
2. **Hours summary** (rows 5-7): actual hours, expected hours, difference.
   Difference is color-coded: red if negative, orange if positive, green if zero.
3. **Issues section** (starting row 9): a table of all `CheckResult` rows for this
   employee.  Columns: Тип проверки, Серьёзность, Описание.  Row background is
   tinted red for errors, yellow for warnings.  If there are no issues, a single
   row says "Нет замечаний" in green.
4. **Worklogs table** (below issues, separated by one blank row): all worklog
   entries for this employee sorted by date.  Columns: Дата, Проект, Задача,
   Название, Часы, Комментарий.  Rows flagged by permitted-task check are
   highlighted in light red.

### Styling

Follow the design tokens from `docs/brandbook.html`:
- Header font: bold, size 14, color `#111827` (--text-primary)
- Table header: background `#F9FAFB` (--bg-secondary), font bold size 10,
  color `#4B5563` (--text-secondary)
- Status colors: success `#059669`, warning `#D97706`, error `#DC2626`
- Status light fills: success `#ECFDF5`, warning `#FFFBEB`, error `#FEF2F2`
- Borders: thin, color `#E5E7EB` (--border)
- Font: Calibri (Excel-native equivalent of Inter)
- Monospace data (hours, keys): use Consolas
- Freeze panes: freeze the header row in all tables

## Phases

### Phase 1 — Backend: Excel generation service (per-employee sheets) ✅

Create `backend/app/services/excel_report.py` with a function
`generate_report(upload_id: int, db: Session) -> bytes` that builds an openpyxl
Workbook and returns the serialized .xlsx bytes.

In this phase, implement only the per-employee sheets (one sheet per employee).
Each sheet contains the header area, hours summary, issues section, and worklogs
table as described in the Report Structure section above.

The function must:
1. Load all `WorklogEntry` rows for the upload.
2. Load all `CheckResult` rows for the upload.
3. Load employee-country mapping via `get_country()` from
   `backend/app/services/employee_country.py`.
4. Load expected hours via `get_expected_hours()` from
   `backend/app/services/calendar.py`.
5. Group worklogs and check results by username.
6. For each employee, create a sheet named after their last name.
7. Populate the sheet with header, hours summary, issues, and worklogs.
8. Apply styling as described in the Styling section.
9. Set column widths to reasonable defaults.
10. Freeze panes below the header of each table.

Define reusable openpyxl `NamedStyle` objects for header, table header, data cells,
status cells (ok/warning/error), and monospace cells.

Verification: from `backend/` directory, start the backend (`uvicorn app.main:app
--reload`), upload the sample file via Swagger, run checks, then call the service
directly in a Python shell:

```python
from app.database import SessionLocal
from app.services.excel_report import generate_report

db = SessionLocal()
data = generate_report(1, db)
with open("test_report.xlsx", "wb") as f:
    f.write(data)
db.close()
```

Open `test_report.xlsx` in Excel — it should have one sheet per employee with
styled headers, worklogs, and issues.

### Phase 2 — Backend: Summary sheets + API endpoint ✅

Add two more sheets to the report workbook:
1. "Сводка" — summary table with all employees (name, country, hours, norm,
   diff, status, issue count).  Insert it as the first sheet in the workbook.
2. "Распределение" — pivot table of hours by project × employee, plus
   region totals.  Insert it as the second sheet.

Create `backend/app/api/reports.py` — a FastAPI router with one endpoint:

`GET /api/uploads/{upload_id}/report` — generates the Excel report and returns
it as a downloadable file with Content-Type
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and
Content-Disposition header `attachment; filename="TimeAudit_Report_{upload_id}.xlsx"`.

The endpoint must verify that the upload exists and has status "checked".
If checks have not been run, return HTTP 409 with a descriptive message.

Register the new router in `backend/app/main.py`.

Verification: after uploading the sample file and running checks, open Swagger UI
at `http://localhost:8000/docs` and call `GET /api/uploads/1/report`.  The browser
should download an Excel file.  Opening it should show three types of sheets:
"Сводка" (first), "Распределение" (second), then individual employee sheets.

### Phase 3 — Frontend: download button and integration ✅

Add a "Скачать отчёт" download button to the main page.  The button appears only
after checks have been completed (upload status is "checked").

Modify `frontend/src/app/page.tsx`:
- Add the download button next to the existing "Запустить проверку" button
  (in the same status bar section).
- The button uses the secondary button style from the brandbook (gray background,
  border, like the "Download Excel" button shown in `docs/brandbook.html`).
- On click, it opens `/api/uploads/{upload_id}/report` in a new tab / triggers
  a file download.  No need for a separate API call — the browser handles the
  download directly from the GET endpoint.

Add a helper function `getReportUrl(uploadId: number): string` to
`frontend/src/lib/api.ts` that returns the report URL.

Verification: start both backend and frontend.  Upload the sample file, run
checks, then click the "Скачать отчёт" button.  The browser should download
an Excel file named `TimeAudit_Report_1.xlsx`.  Open it and verify:
- "Сводка" sheet with all employees and their statuses
- "Распределение" sheet with project distribution
- One sheet per employee with header, hours, issues, worklogs
- All styling applied: colors, fonts, borders, frozen panes

## Validation

End-to-end verification after all three phases:

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000`
4. Upload `data/input/Time Sheet Report 2026.05.xls`
5. Click "Запустить проверку" — wait for checks to complete
6. Click "Скачать отчёт" — browser downloads `TimeAudit_Report_X.xlsx`
7. Open the Excel file and verify:
   - Sheet "Сводка": all employees listed with correct hours, norms, diffs, statuses
   - Sheet "Распределение": pivot table of hours by project × employee
   - Per-employee sheets: correct header, hours summary, issues, worklogs
   - Styling matches the brandbook: colors, fonts, borders
   - Frozen header rows in all tables
   - Column widths are readable without manual resizing

The API endpoint also works independently via Swagger at
`http://localhost:8000/docs` → `GET /api/uploads/{id}/report`.

## Decision Log

- Decision: Use openpyxl (already in requirements.txt) for Excel generation.
  Rationale: It is already a project dependency, supports .xlsx format natively,
  and provides full styling capabilities (fonts, fills, borders, named styles).
  Date: 2026-06-08

- Decision: Return the report as in-memory bytes via StreamingResponse, not
  save to disk.
  Rationale: Avoids file management (cleanup, disk space).  The report is
  generated on demand and streamed directly to the client.  Files are small
  (under 1 MB for 20 employees × 1700 worklogs).
  Date: 2026-06-08

- Decision: Sheet names use employee last name (first word of full name),
  truncated to 31 characters.
  Rationale: Excel limits sheet names to 31 characters.  Using the last name
  keeps sheets readable.  If two employees share a last name, append first
  initial (e.g. "Иванов А", "Иванов М").
  Date: 2026-06-08

- Decision: Place "Сводка" and "Распределение" as the first two sheets.
  Rationale: Management wants the summary first.  Individual employee sheets
  follow in alphabetical order.
  Date: 2026-06-08

## Surprises & Discoveries

- The first test run of `generate_report` showed "Нет замечаний" for all employees
  because it was called before the background check thread had finished.  Running it
  after checks complete produces correct results (22 check results across 9 employees).
  Date: 2026-06-08

- openpyxl `Workbook.save()` accepts a `BytesIO` stream directly — no need for temp
  files.  `buf = BytesIO(); wb.save(buf); return buf.getvalue()` works cleanly.
  Date: 2026-06-08

- Excel only supports one `freeze_panes` per sheet.  The code sets it below the
  worklog table header (the largest table), overriding the earlier issues-table freeze.
  Date: 2026-06-08

## Outcomes & Retrospective

_To be filled upon completion._
