import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s - %(message)s")

from app.api import checks, health, invest, reports, uploads
from app.config import FRONTEND_DIR, settings
from app.database import Base, engine, run_migrations
from app.models import (  # noqa: F401 — ensure models are registered
    BuhCompanyMapping,
    CheckResult,
    InvestAllocation,
    InvestEmployeeSelection,
    InvestFtePlan,
    Upload,
    WorklogEntry,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
    checks.reset_interrupted_checks()
    yield


app = FastAPI(
    title=settings.app_name,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(checks.router)
app.include_router(reports.router)
app.include_router(invest.router)

# Serve the statically-exported frontend (produced by `next build` with
# output: "export") from the same origin as the API. API routes live under
# /api, so mounting the static site at "/" does not conflict with them. This
# mount is only added when the build exists, so a source-only dev run (using
# the separate Next.js dev server) still works.
if FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
