from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=settings.debug,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Apply lightweight SQLite schema patches after create_all."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='invest_fte_plans'")
        ).fetchall()
        if rows:
            columns = conn.execute(text("PRAGMA table_info(invest_fte_plans)")).fetchall()
            col_names = {col[1] for col in columns}
            if "username" not in col_names:
                conn.execute(
                    text(
                        "ALTER TABLE invest_fte_plans "
                        "ADD COLUMN username VARCHAR NOT NULL DEFAULT ''"
                    )
                )
                # Drop legacy global rows that have no employee binding.
                conn.execute(text("DELETE FROM invest_fte_plans WHERE username = ''"))
                conn.commit()

        upload_rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='uploads'")
        ).fetchall()
        if upload_rows:
            upload_columns = conn.execute(text("PRAGMA table_info(uploads)")).fetchall()
            upload_col_names = {col[1] for col in upload_columns}
            if "error_message" not in upload_col_names:
                conn.execute(text("ALTER TABLE uploads ADD COLUMN error_message VARCHAR"))
                conn.commit()
