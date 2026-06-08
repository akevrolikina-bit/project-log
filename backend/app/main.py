import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s - %(message)s")

from app.api import checks, health, invest, reports, uploads
from app.config import settings
from app.database import Base, engine
from app.models import (  # noqa: F401 — ensure models are registered
    BuhCompanyMapping,
    CheckResult,
    InvestAllocation,
    InvestEmployeeSelection,
    Upload,
    WorklogEntry,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(checks.router)
app.include_router(reports.router)
app.include_router(invest.router)
