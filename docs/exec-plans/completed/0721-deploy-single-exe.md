# 0721 — Package TimeAudit as a single Windows executable

Living document. Maintained per docs/PLANS.md.

## Purpose

Let a non-technical user run TimeAudit by double-clicking one file
(`TimeAudit.exe`) that opens the app in the browser, carry it to other Windows
PCs by copying that file, and avoid buying or paying for any separate server.
Before this change the app required two processes (Python backend on port 8001
and the Next.js dev server on port 3000) and a full developer setup. After this
change everything runs from a single self-contained executable.

## Phases

### Phase 1 — One process serves both the frontend and the API

Turn the app into a single process on one port.

- `frontend/next.config.ts`: enable static export (`output: "export"`, produces
  `frontend/out`); keep the `/api` dev proxy (`rewrites`) only in development,
  because rewrites are unsupported in static export.
- `backend/app/main.py`: mount `frontend/out` at `/` with `StaticFiles(html=True)`
  after the API routers. API stays under `/api`, so there is no conflict. The
  mount is added only when the build exists, so a source-only dev run still works.
- `backend/app/config.py`: introduce `BUNDLE_DIR` (read-only resources) and
  `DATA_DIR` (writable data). In a normal run both derive from the project root;
  in a frozen build, resources come from `sys._MEIPASS` and `data/` sits next to
  the executable. Route the database, input folder, and the reference workbook
  through these.
- `backend/app/services/permitted_tasks.py`: read the reference workbook path
  from `settings.permitted_tasks_path` instead of a hard-coded relative path.

### Phase 2 — Package into one .exe (PyInstaller)

- `backend/run.py`: entry point that picks a local port (prefers 8001), starts
  uvicorn, and opens the browser once the server is ready.
- `TimeAudit.spec`: PyInstaller recipe. Bundles `frontend/out`, `backend/.env`,
  the reference workbook, and `config/employee_countries.json`; adds hidden
  imports for `uvicorn` and the `app` package. One-file, console app.

### Phase 3 — Portability, build script, and docs

- `build.ps1`: one-command build (frontend static export + PyInstaller).
- `docs/deploy.md`: user and maintainer instructions.
- `docs/tech.md`: add a "Packaged Distribution" section.

## Validation

Verified end-to-end on Windows:

- `powershell -ExecutionPolicy Bypass -File build.ps1` produces
  `dist/TimeAudit.exe` (~69 MB).
- Double-clicking the exe starts the server, prints the URL banner, and opens
  the browser; `GET /` returns the TimeAudit UI (HTTP 200) and static assets
  load.
- `GET /health` returns `{"status":"ok"}`; `GET /api/uploads` returns JSON.
- Full flow through the exe: upload `Time Sheet Report 2026.05.xls` -> run checks
  -> results include per-employee `total_hours` and `expected_hours` (production
  calendar) -> `GET /api/uploads/{id}/report` returns a valid `.xlsx`
  (HTTP 200, "PK" signature). This confirms the bundled reference workbook,
  `config/employee_countries.json`, and the production calendar all work inside
  the exe.
- Portability: copying only `TimeAudit.exe` into a clean folder and running it
  serves the app and creates its own `data/` folder — no source, Python, or Node
  required.

## Decision Log

- Decision: Ship as a single one-file Windows `.exe`.
  Rationale: The user wanted the simplest possible experience for a
  non-technical audience — double-click to run, copy to move, no server, no
  installs.
  Date: 2026-07-21

- Decision: Serve the statically-exported frontend directly from FastAPI.
  Rationale: The frontend is fully client-side (only relative `/api` fetches),
  so it can be a static SPA served from the same origin, eliminating the second
  process and the dev proxy in production.
  Date: 2026-07-21

- Decision: Store writable data in a `data/` folder next to the executable.
  Rationale: Persists between runs, is easy for a non-technical user to find and
  copy, and keeps read-only bundled resources separate from user data.
  Date: 2026-07-21

- Decision: Embed API keys (`backend/.env`) inside the executable.
  Rationale: The user chose zero configuration on other machines over key
  secrecy. Documented the trade-off (keys are extractable) in `docs/deploy.md`.
  Date: 2026-07-21

## Surprises & Discoveries

- Observation: The check flow also depends on `config/employee_countries.json`,
  loaded via a path relative to the source tree, which was missing from the
  first build and caused a `FileNotFoundError` inside the exe.
  Evidence: Traceback in the exe console during `run_checks` ->
  `employee_country._load`. Fixed by bundling the file to `config/` in the spec.

- Observation: A running one-file exe keeps a lock on `dist/TimeAudit.exe`
  (the bootloader spawns a child process), so a rebuild fails with
  `PermissionError` unless the app is closed first.
  Evidence: PyInstaller `os.remove(self.name)` failed while two `TimeAudit`
  processes were alive. `build.ps1` now checks for and refuses to build while
  `TimeAudit.exe` is running.

- Observation: The AI comment-review step needs internet; without it, checks
  still complete (per-batch errors are caught) but take longer due to retries.
  Evidence: `getaddrinfo failed` for `api.vsegpt.ru` in the sandbox; checks
  finished and status became `checked` after all batches, then the report
  downloaded successfully.

## Outcomes & Retrospective

Achieved the original purpose: `dist/TimeAudit.exe` is a single, portable,
server-free Windows app that a non-technical user can double-click and use, and
copy to other PCs without any installation. The core review workflow
(upload -> checks -> Excel report) works entirely inside the executable and
offline; only the optional AI review and Google Docs features need internet.

Remaining/optional follow-ups: add a custom application icon; consider a
hidden/windowed launcher instead of the console window; if secret-embedding
becomes a concern, switch to reading `backend/.env` from next to the exe instead
of bundling it.
