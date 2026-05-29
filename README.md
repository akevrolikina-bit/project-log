# TimeAudit — Jira Time Log Checker

A web application that automates monthly time-logging review for teams using Jira.

## Project Structure

```
project-log/
├── backend/     ← Python API (FastAPI + SQLAlchemy + SQLite)
├── frontend/    ← Web UI (Next.js + TypeScript + Tailwind + shadcn/ui)
├── data/        ← Database and generated Excel files (gitignored)
└── docs/        ← Documentation
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

API: **http://localhost:8000** | Docs: **http://localhost:8000/docs**

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

UI: **http://localhost:3000**

## Documentation

- [Product strategy](docs/product.md)
- [Technology stack](docs/tech.md)
- [Design system](docs/brandbook.html)
