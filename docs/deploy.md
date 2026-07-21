# Deployment — Single Windows Executable (TimeAudit.exe)

TimeAudit ships as a single Windows file, `TimeAudit.exe`. A user double-clicks
it, the app starts, and the default browser opens automatically. No Python, no
Node.js, and no separate server are required.

## For end users (running the app)

1. Copy `TimeAudit.exe` to any folder on a Windows PC (Desktop is fine).
2. Double-click `TimeAudit.exe`.
3. A small black console window appears with a message like
   `Open in your browser: http://127.0.0.1:8001/`. The browser opens by itself.
4. Use the app in the browser.
5. To stop the app, close the black console window.

Notes:

- The first launch creates a `data` folder next to `TimeAudit.exe`. It contains
  the database (`app.db`) and uploaded files. Keep this folder if you want to
  preserve history; delete it to start clean.
- To move the app to another computer, copy `TimeAudit.exe` (optionally with the
  `data` folder to keep history). Nothing needs to be installed.
- The first start may take a few seconds while Windows unpacks the app.
- Windows SmartScreen or antivirus may warn about an unknown app the first time
  (normal for freshly built executables). Choose "Run anyway" / add an exception.
- Internet access is only needed for the optional AI comment review step and the
  Google Docs integration; the rest of the app works fully offline.

## For the maintainer (building a new .exe)

Prerequisites (one-time setup):

```powershell
npm run setup        # creates backend\.venv and installs frontend deps
```

The reference workbook `data/input/Issues CHANGE (2).xlsx` and the file
`backend/.env` (with API keys) must be present before building — they are packed
into the executable. Note that both are git-ignored, so keep local copies.

Build in one command from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

This will:

1. Build the frontend as a static site (`frontend/out`).
2. Package everything into `dist/TimeAudit.exe` with PyInstaller.

The finished file is `dist\TimeAudit.exe` (about 70 MB).

### How it is put together

- `frontend/next.config.ts` — `output: "export"` produces a static site in
  `frontend/out`. The dev proxy (`rewrites`) is kept only for development.
- `backend/app/main.py` — serves `frontend/out` at `/` and the API under `/api`
  from a single port.
- `backend/app/config.py` — resolves paths for both a normal run and a packaged
  run: read-only resources come from the bundle, writable `data/` sits next to
  the `.exe`.
- `backend/run.py` — the entry point: starts uvicorn and opens the browser.
- `TimeAudit.spec` — the PyInstaller recipe (which files and hidden imports to
  bundle).
- `build.ps1` — runs the two build steps above.

### Security note (embedded keys)

The API keys in `backend/.env` are compiled into `TimeAudit.exe`. They can, in
principle, be extracted from the file. Share the executable only with trusted
colleagues, give the keys the minimum permissions needed, and rotate/revoke them
if the file leaks.

### Troubleshooting

- "TimeAudit.exe is currently running" during build: close any running instance
  (close its console window), then run `build.ps1` again.
- Build fails complaining about a missing `Issues CHANGE (2).xlsx` or `.env`:
  make sure both files exist in the paths listed above.
