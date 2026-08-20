import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


# BUNDLE_DIR — where read-only resources shipped with the app live
# (the frontend static build, the reference Excel, the bundled .env).
# DATA_DIR — where writable data lives (SQLite database, user input files).
#
# In a normal source run both are derived from the project root. In a
# PyInstaller build, read-only resources are extracted to a temporary folder
# (sys._MEIPASS), while writable data is placed in a "data" folder next to the
# executable so it persists between runs and is easy to find and copy.
if _is_frozen():
    BUNDLE_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    DATA_DIR = Path(sys.executable).resolve().parent / "data"
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent.parent
    DATA_DIR = BUNDLE_DIR / "data"

# Kept for backwards compatibility with existing imports.
PROJECT_ROOT = BUNDLE_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "input").mkdir(parents=True, exist_ok=True)

# Static frontend produced by `next build` (output: "export").
FRONTEND_DIR = BUNDLE_DIR / "frontend" / "out"

# Environment file: backend/.env alongside the resources.
_ENV_FILE = BUNDLE_DIR / "backend" / ".env"

# Reference permitted-tasks workbook shipped with the app (read-only).
_DEFAULT_PERMITTED_TASKS = BUNDLE_DIR / "data" / "input" / "Issues CHANGE (3).xlsx"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TimeAudit"
    debug: bool = False

    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"

    excel_input_folder: str = str(DATA_DIR / "input")

    permitted_tasks_path: str = str(_DEFAULT_PERMITTED_TASKS)

    google_credentials_path: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.vsegpt.ru/v1"


settings = Settings()
