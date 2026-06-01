"""Core checking logic: permitted tasks + hours vs production calendar."""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.check_result import CheckResult
from app.models.upload import Upload
from app.models.worklog import WorklogEntry
from app.services.calendar import get_expected_hours
from app.services.employee_country import get_country
from app.services.permitted_tasks import load_permitted_tasks


def run_checks(
    upload_id: int,
    db: Session,
) -> list[CheckResult]:
    """Run all automated checks for the given upload and persist results.

    Steps
    -----
    1. Load worklog entries for the upload.
    2. For each entry, check against the permitted-task registry
       (key rule → project+type rule → unknown).  Apply per-user exclusions.
    3. Aggregate hours per employee per month and compare to the
       production-calendar expectation.
    4. Save ``CheckResult`` rows and update upload status.
    """
    upload: Upload | None = db.query(Upload).filter(Upload.id == upload_id).first()
    if upload is None:
        raise ValueError(f"Upload {upload_id} not found")

    worklogs: list[WorklogEntry] = (
        db.query(WorklogEntry)
        .filter(WorklogEntry.upload_id == upload_id)
        .all()
    )
    if not worklogs:
        raise ValueError(f"No worklog entries for upload {upload_id}")

    db.query(CheckResult).filter(CheckResult.upload_id == upload_id).delete()

    registry = load_permitted_tasks()
    results: list[CheckResult] = []

    # ---- 1. Permitted-task check -------------------------------------------
    blocked_by_user: dict[str, list[dict]] = defaultdict(list)

    for wl in worklogs:
        verdict = registry.check(
            key=wl.key,
            project=wl.project,
            task_type=wl.task_type,
            username=wl.username,
        )
        if verdict.permitted:
            continue

        blocked_by_user[wl.username].append({
            "key": wl.key,
            "hours": wl.hours,
            "title": wl.title,
            "reason": verdict.reason,
            "rule_type": verdict.rule_type,
        })

    for username, items in blocked_by_user.items():
        total_h = sum(i["hours"] for i in items)
        keys = sorted({i["key"] for i in items})
        results.append(
            CheckResult(
                upload_id=upload_id,
                username=username,
                check_type="permitted_task",
                severity="error",
                message=(
                    f"Списание на запрещённые задачи: {', '.join(keys[:5])}"
                    f"{' и ещё ' + str(len(keys) - 5) if len(keys) > 5 else ''} "
                    f"({total_h:.1f} ч)"
                ),
                details=json.dumps(items, ensure_ascii=False),
            )
        )

    # ---- 2. Hours mismatch check ------------------------------------------
    hours_per_user_month: dict[str, dict[tuple[int, int], float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for wl in worklogs:
        ym = (wl.started.year, wl.started.month)
        hours_per_user_month[wl.username][ym] += wl.hours

    for username, months in hours_per_user_month.items():
        user_country = get_country(username)

        for (year, month), actual_hours in sorted(months.items()):
            try:
                expected = get_expected_hours(user_country, year, month)
            except ValueError:
                continue

            diff = actual_hours - expected
            if abs(diff) < 0.5:
                continue

            if diff < 0:
                message = (
                    f"Недобор часов за {month:02d}.{year} ({user_country}): "
                    f"списано {actual_hours:.1f} ч, норма {expected:.0f} ч "
                    f"(дельта {diff:+.1f} ч)"
                )
            else:
                message = (
                    f"Перебор часов за {month:02d}.{year} ({user_country}): "
                    f"списано {actual_hours:.1f} ч, норма {expected:.0f} ч "
                    f"(дельта {diff:+.1f} ч)"
                )

            severity = "error" if diff < 0 else "warning"

            results.append(
                CheckResult(
                    upload_id=upload_id,
                    username=username,
                    check_type="hours_mismatch",
                    severity=severity,
                    message=message,
                    details=json.dumps(
                        {
                            "year": year,
                            "month": month,
                            "country": user_country,
                            "actual_hours": round(actual_hours, 2),
                            "expected_hours": expected,
                            "diff": round(diff, 2),
                        }
                    ),
                )
            )

    # ---- Persist -----------------------------------------------------------
    for r in results:
        db.add(r)

    upload.status = "checked"
    db.commit()

    return results
