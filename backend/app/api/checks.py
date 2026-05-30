"""API endpoints for running checks and retrieving results."""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.check_result import CheckResult
from app.models.upload import Upload
from app.models.worklog import WorklogEntry
from app.schemas.check import CheckResultResponse, CheckSummaryItem
from app.services.calendar import get_expected_hours
from app.services.checker import run_checks
from app.services.employee_country import get_country

router = APIRouter(prefix="/api/uploads", tags=["checks"])


@router.post("/{upload_id}/check", response_model=list[CheckResultResponse])
def execute_checks(upload_id: int, db: Session = Depends(get_db)):
    """Run all checks for the upload. Replaces previous results."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    try:
        results = run_checks(upload_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return results


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
