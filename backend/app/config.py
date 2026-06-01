from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TimeAudit"
    debug: bool = False

    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}"

    excel_input_folder: str = str(PROJECT_ROOT / "data" / "input")

    google_credentials_path: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.vsegpt.ru/v1"


settings = Settings()
