"""Core checking logic: permitted tasks + hours vs production calendar + comments."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.check_result import CheckResult
from app.models.upload import Upload
from app.models.worklog import WorklogEntry
from app.services.calendar import get_expected_hours, get_working_days
from app.services.comment_reviewer import (
    WorklogForReview,
    is_available as ai_review_available,
    review_comments,
)
from app.services.comment_rules import check_comment_quality
from app.services.employee_country import get_country
from app.services.permitted_tasks import COMMENT_RULE_LENIENT, load_permitted_tasks


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
    logger.info("run_checks: upload=%d, %d worklogs", upload_id, len(worklogs))

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

    logger.info("step 1 (permitted tasks) done, %d issues", len(results))

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

    logger.info("step 2 (hours mismatch) done, %d issues total", len(results))

    # ---- 3. Comment quality check -------------------------------------------
    comment_issues_by_user: dict[str, list[dict]] = defaultdict(list)

    for wl in worklogs:
        comment_rule = registry.get_comment_rule(wl.key, wl.project, wl.task_type)
        issues = check_comment_quality(
            comment=wl.comment or "",
            key=wl.key,
            title=wl.title,
            comment_rule=comment_rule,
        )
        for issue in issues:
            comment_issues_by_user[wl.username].append({
                "key": wl.key,
                "hours": wl.hours,
                "comment": (wl.comment or "")[:120],
                "severity": issue.severity,
                "reason": issue.reason,
            })

    for username, items in comment_issues_by_user.items():
        error_count = sum(1 for i in items if i["severity"] == "error")
        warning_count = sum(1 for i in items if i["severity"] == "warning")
        worst_severity = "error" if error_count > 0 else "warning"
        total_issues = error_count + warning_count

        results.append(
            CheckResult(
                upload_id=upload_id,
                username=username,
                check_type="comment_quality",
                severity=worst_severity,
                message=f"Проблемы с комментариями: {total_issues} ошибок",
                details=json.dumps(items, ensure_ascii=False),
            )
        )

    logger.info("step 3 (comment quality) done, %d issues total", len(results))

    # ---- 4. AI comment relevance check --------------------------------------
    if ai_review_available():
        entries_for_review: list[WorklogForReview] = []
        wl_index_map: dict[int, WorklogEntry] = {}

        for i, wl in enumerate(worklogs):
            comment = (wl.comment or "").strip()
            if not comment:
                continue
            cr = registry.get_comment_rule(wl.key, wl.project, wl.task_type)
            if cr == COMMENT_RULE_LENIENT:
                continue
            has_quality_issue = any(
                check_comment_quality(comment, wl.key, wl.title, comment_rule=cr)
            )
            if has_quality_issue:
                continue
            entries_for_review.append(
                WorklogForReview(
                    index=i,
                    project=wl.project,
                    task_type=wl.task_type,
                    key=wl.key,
                    title=wl.title,
                    comment=comment[:300],
                    username=wl.username,
                    hours=wl.hours,
                )
            )
            wl_index_map[i] = wl

        if entries_for_review:
            verdicts = review_comments(entries_for_review)

            ai_issues_by_user: dict[str, list[dict]] = defaultdict(list)
            for v in verdicts:
                if v.verdict == "green":
                    continue
                wl = wl_index_map.get(v.index)
                if wl is None:
                    continue
                ai_issues_by_user[wl.username].append({
                    "key": wl.key,
                    "hours": wl.hours,
                    "comment": (wl.comment or "")[:120],
                    "verdict": v.verdict,
                    "explanation": v.explanation,
                })

            for username, items in ai_issues_by_user.items():
                red_count = sum(1 for i in items if i["verdict"] == "red")
                yellow_count = sum(1 for i in items if i["verdict"] == "yellow")
                worst = "error" if red_count > 0 else "warning"

                parts: list[str] = []
                if red_count:
                    parts.append(f"{red_count} не соответствуют задаче")
                if yellow_count:
                    parts.append(f"{yellow_count} сомнительных")

                results.append(
                    CheckResult(
                        upload_id=upload_id,
                        username=username,
                        check_type="comment_relevance",
                        severity=worst,
                        message=(
                            f"ИИ-проверка комментариев: {', '.join(parts)}"
                        ),
                        details=json.dumps(items, ensure_ascii=False),
                    )
                )

    logger.info("step 4 (AI review) done, %d issues total", len(results))

    # ---- 5. Time limit check for BUH-72900 & BUH-115258 --------------------
    time_limit_keys = registry.time_limited_keys
    if time_limit_keys:
        # hours per user per month on time-limited keys
        tl_hours: dict[str, dict[tuple[int, int], float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for wl in worklogs:
            if wl.key in time_limit_keys:
                ym = (wl.started.year, wl.started.month)
                tl_hours[wl.username][ym] += wl.hours

        for username, months in tl_hours.items():
            user_country = get_country(username)
            for (year, month), actual_hours in sorted(months.items()):
                try:
                    working_days = get_working_days(user_country, year, month)
                except ValueError:
                    continue
                limit_hours = (20.0 / 60.0) * working_days
                if actual_hours > limit_hours:
                    results.append(
                        CheckResult(
                            upload_id=upload_id,
                            username=username,
                            check_type="time_limit",
                            severity="warning",
                            message=(
                                f"Превышен лимит на задачи BUH-72900/BUH-115258 "
                                f"за {month:02d}.{year}: "
                                f"списано {actual_hours:.1f} ч, "
                                f"лимит {limit_hours:.1f} ч "
                                f"(20 мин × {working_days} раб. дней)"
                            ),
                            details=json.dumps(
                                {
                                    "year": year,
                                    "month": month,
                                    "actual_hours": round(actual_hours, 2),
                                    "limit_hours": round(limit_hours, 2),
                                    "working_days": working_days,
                                    "keys": sorted(time_limit_keys),
                                },
                                ensure_ascii=False,
                            ),
                        )
                    )

    # ---- 6. General rules (bottom of the Issues table) -----------------------
    _VG_PATTERN = re.compile(
        r"\bВГО?\b|\bвнутригрупповой\b|\bвнутригрупповая\b|\bвнутригрупповое\b|\bСД\b",
        re.IGNORECASE,
    )
    _SICK_VACATION_PATTERN = re.compile(
        r"\bбольнич\w*\b|\bотпуск\w*\b|\bотгул\w*\b",
        re.IGNORECASE,
    )

    general_issues_by_user: dict[str, list[dict]] = defaultdict(list)

    for wl in worklogs:
        text = f"{wl.title} {wl.comment or ''}"

        # Rule 2: ВГ/ВГО/внутригрупповой/СД must be on BUH-71413
        if _VG_PATTERN.search(text) and wl.key != "BUH-71413":
            general_issues_by_user[wl.username].append({
                "key": wl.key,
                "hours": wl.hours,
                "title": wl.title[:100],
                "reason": (
                    f"Задача с упоминанием ВГ/ВГО/СД должна быть списана "
                    f"на BUH-71413, а не на {wl.key}"
                ),
            })

        # Rule 1: sick/vacation/отгул must be on GENERAL, not HR
        if wl.project == "HR" and _SICK_VACATION_PATTERN.search(text):
            general_issues_by_user[wl.username].append({
                "key": wl.key,
                "hours": wl.hours,
                "title": wl.title[:100],
                "reason": (
                    f"Больничные/отпуска/отгулы должны списываться "
                    f"на GENERAL, а не на {wl.key} (HR)"
                ),
            })

    for username, items in general_issues_by_user.items():
        results.append(
            CheckResult(
                upload_id=upload_id,
                username=username,
                check_type="general_rules",
                severity="error",
                message=(
                    f"Нарушение общих правил списания: "
                    f"{len(items)} ошибок"
                ),
                details=json.dumps(items, ensure_ascii=False),
            )
        )

    logger.info("all steps done, %d issues total", len(results))

    # ---- Persist -----------------------------------------------------------
    for r in results:
        db.add(r)

    upload.status = "checked"
    db.commit()

    return results
