"""API endpoints for running checks and retrieving results."""

from __future__ import annotations

import logging
import threading
import traceback
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database import SessionLocal, get_db
from app.models.check_result import CheckResult
from app.models.upload import Upload
from app.models.worklog import WorklogEntry
from app.schemas.check import CheckResultResponse, CheckSummaryItem
from app.services.calendar import get_expected_hours
from app.services.checker import run_checks
from app.services.employee_country import get_country

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["checks"])


def _user_facing_check_error(exc: BaseException) -> str:
    """Turn a technical exception into a short message the user can act on."""
    if isinstance(exc, PermissionError):
        return (
            "Не получилось прочитать файл со списком разрешённых задач. "
            "Закройте его в Excel, если он открыт, и нажмите проверку ещё раз."
        )
    if isinstance(exc, FileNotFoundError):
        return (
            "Не найден файл со списком разрешённых задач. "
            "Положите его в папку data/input и повторите проверку."
        )
    text = str(exc).lower()
    if "database is locked" in text or "database locked" in text:
        return (
            "База данных была занята. Подождите несколько секунд "
            "и нажмите проверку ещё раз."
        )
    return "Проверка завершилась с ошибкой на сервере. Попробуйте ещё раз."


def _remember_check_error(upload_id: int) -> None:
    """Write the last check traceback to disk for debugging."""
    log_path: Path = DATA_DIR / "last_check_error.txt"
    log_path.write_text(
        f"upload_id={upload_id}\n{traceback.format_exc()}",
        encoding="utf-8",
    )


def reset_interrupted_checks() -> None:
    """Mark in-progress checks as failed after a server restart.

    Checks run in a background thread. If the process reloads (for example
    because a Python file changed), that thread is killed and the upload
    would otherwise stay stuck on ``checking`` forever.
    """
    db = SessionLocal()
    try:
        stuck = db.query(Upload).filter(Upload.status == "checking").all()
        if not stuck:
            return
        for upload in stuck:
            upload.status = "error"
            upload.error_message = (
                "Проверка прервалась. Нажмите проверку ещё раз."
            )
        db.commit()
        logger.info("Reset %d interrupted check(s)", len(stuck))
    except Exception:
        logger.exception("Could not reset interrupted checks")
        db.rollback()
    finally:
        db.close()


def _run_checks_in_background(upload_id: int) -> None:
    """Execute checks in a background thread with its own DB session."""
    db = SessionLocal()
    try:
        run_checks(upload_id, db)
    except Exception as exc:
        logger.exception("Background check failed for upload %d", upload_id)
        try:
            _remember_check_error(upload_id)
        except Exception:
            logger.exception("Could not write last_check_error.txt")
        db.rollback()
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if upload:
            upload.status = "error"
            upload.error_message = _user_facing_check_error(exc)
            db.commit()
    finally:
        db.close()


@router.post("/{upload_id}/check")
def execute_checks(upload_id: int, db: Session = Depends(get_db)):
    """Start checks in the background and return immediately."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    upload.status = "checking"
    upload.error_message = None
    db.commit()

    thread = threading.Thread(
        target=_run_checks_in_background,
        args=(upload_id,),
        daemon=True,
    )
    thread.start()

    return {"status": "checking", "upload_id": upload_id}


@router.get("/{upload_id}/results", response_model=list[CheckSummaryItem])
def get_results(
    upload_id: int,
    username: str | None = None,
    db: Session = Depends(get_db),
):
    """Return check results grouped by employee."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    q = db.query(CheckResult).filter(CheckResult.upload_id == upload_id)
    if username:
        q = q.filter(CheckResult.username == username)
    check_rows = q.all()

    wl_query = db.query(WorklogEntry).filter(WorklogEntry.upload_id == upload_id)
    if username:
        wl_query = wl_query.filter(WorklogEntry.username == username)
    worklogs = wl_query.all()

    hours_per_user: dict[str, float] = defaultdict(float)
    months_per_user: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for wl in worklogs:
        hours_per_user[wl.username] += wl.hours
        months_per_user[wl.username].add((wl.started.year, wl.started.month))

    issues_by_user: dict[str, list[CheckResult]] = defaultdict(list)
    for cr in check_rows:
        issues_by_user[cr.username].append(cr)

    all_usernames = set(hours_per_user.keys()) | set(issues_by_user.keys())

    summaries: list[CheckSummaryItem] = []
    for uname in sorted(all_usernames):
        user_issues = issues_by_user.get(uname, [])
        total_h = hours_per_user.get(uname, 0.0)

        months = months_per_user.get(uname, set())
        user_country = get_country(uname)
        expected_h: float | None = None
        if months:
            expected_h = 0.0
            for y, m in months:
                try:
                    expected_h += get_expected_hours(user_country, y, m)
                except ValueError:
                    pass

        has_error = any(i.severity == "error" for i in user_issues)
        has_warning = any(i.severity == "warning" for i in user_issues)
        if has_error:
            status = "error"
        elif has_warning:
            status = "warning"
        else:
            status = "ok"

        summaries.append(
            CheckSummaryItem(
                username=uname,
                total_hours=round(total_h, 2),
                expected_hours=round(expected_h, 2) if expected_h is not None else None,
                status=status,
                issues=[
                    CheckResultResponse.model_validate(i) for i in user_issues
                ],
            )
        )

    return summaries
