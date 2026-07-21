# Jira Time Log Checker — Technology Stack

## Overview

Python backend (API) + React frontend (UI). Two separate services in a single repository.
In the first phase, everything runs locally (on the developer's machine).

## Backend (Python)

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Framework | FastAPI |
| Excel import (worklog parsing) | pandas + openpyxl |
| Google Docs integration | google-api-python-client |
| Excel generation | openpyxl |
| AI (Phase 2) | openai |
| Authentication | FastAPI + JWT |
| ORM | SQLAlchemy |

## Frontend (TypeScript)

| Component | Technology |
|-----------|-----------|
| Language | TypeScript |
| Framework | Next.js (App Router) |
| UI library | shadcn/ui |
| Styling | Tailwind CSS |

## Database

| Component | Technology |
|-----------|-----------|
| DBMS | SQLite (via SQLAlchemy) |
| File | Single file `data/app.db` in the project folder |
| Stores | Users, team settings, review results, history |

## Running (Phase 1 — Local)

| Component | How to run |
|-----------|-----------|
| Backend | `uvicorn main:app` — API on localhost:8000 |
| Frontend | `npm run dev` — UI on localhost:3000 |
| Database | SQLite file, created automatically |
| Excel files | Saved to a local project folder |

## Hosting (Phase 1 — Not required)

No cloud hosting is needed in the first phase. Everything runs locally.
When the app is ready for deployment, the backend can be moved to Railway, the frontend to Vercel, and the database to PostgreSQL.

## Packaged Distribution (Single Windows .exe)

For sharing the app with non-technical colleagues, it is packaged into a single
Windows executable (`dist/TimeAudit.exe`) using PyInstaller. See `docs/deploy.md`
for full instructions. Key facts:

| Aspect | How it works |
|--------|--------------|
| One file | `TimeAudit.exe` — double-click to launch; the browser opens automatically |
| Frontend | Built as a static export (`next build` with `output: "export"` -> `frontend/out`) and served by the Python backend on a single local port |
| Single origin | Backend serves both the UI (at `/`) and the API (under `/api`), so no dev proxy is needed in the build |
| Writable data | A `data/` folder is created next to the `.exe` (SQLite database + user files) |
| Bundled resources | Static frontend, the reference workbook, `config/employee_countries.json`, and `backend/.env` (embedded API keys) are packed inside the `.exe` |
| Build entry point | `backend/run.py` starts uvicorn and opens the browser |
| Build config | `TimeAudit.spec` (PyInstaller) and `build.ps1` (one-command build) |
| Portability | Copy `TimeAudit.exe` to any Windows PC and run — no Python, Node, or install required |

## Data Storage

| What | Where | Notes |
|------|-------|-------|
| Rules and task list | Google Docs | Edited by leads manually, fetched automatically by the app |
| Worklog data (Excel) | Imported from Excel file (uploaded via UI or read from input folder) | Standard Jira worklog export |
| Settings (employees, calendars, teams) | SQLite (local) | Persistent between sessions |
| Users and authentication | SQLite (local) | Standard |
| Review history | SQLite (local) | For accessing past results |
| Generated Excel files | Folder on disk | Generated on demand, downloaded from the app |

## Repository Structure

```
project-log/
├── backend/          ← Python (FastAPI)
├── frontend/         ← TypeScript (Next.js)
├── data/             ← SQLite + generated Excel files
└── docs/             ← Documentation
```

## Technology Choice Rationale

- **Python** — best support for key integrations (Google Docs, Excel, AI)
- **pandas** — powerful tabular data processing, ideal for parsing and analyzing Excel worklog exports
- **FastAPI** — modern, lightweight, with auto-generated API documentation
- **React/Next.js** — largest UI component ecosystem, best agent support
- **SQLite** — database in a single file, no server installation required. Easy to migrate to PostgreSQL when moving to the cloud
- **SQLAlchemy** — standard Python ORM, supports both SQLite and PostgreSQL
- **Everything local at launch** — faster to start, no subscriptions or server setup needed
