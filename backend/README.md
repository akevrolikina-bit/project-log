# Backend — TimeAudit API

Python 3.12+ / FastAPI / SQLAlchemy / SQLite

## Quick Start

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env template
copy .env.example .env

# Run the server
uvicorn app.main:app --reload
```

The API will be available at **http://localhost:8000**.

- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
