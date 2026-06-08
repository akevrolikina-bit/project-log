"""Generate an Excel (.xlsx) report.

Sheets: Сводка, Распределение, Ошибки, Недобор часов.
Styled according to docs/brandbook.html.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    NamedStyle,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.check_result import CheckResult
from app.models.worklog import WorklogEntry
from app.services.calendar import get_expected_hours
from app.services.employee_country import get_country

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brandbook tokens → openpyxl primitives
# ---------------------------------------------------------------------------
_CLR_TEXT_PRIMARY = "111827"
_CLR_TEXT_SECONDARY = "4B5563"
_CLR_BG_SECONDARY = "F9FAFB"
_CLR_BORDER = "E5E7EB"

_CLR_SUCCESS = "059669"
_CLR_SUCCESS_LIGHT = "ECFDF5"
_CLR_WARNING = "D97706"
_CLR_WARNING_LIGHT = "FFFBEB"
_CLR_ERROR = "DC2626"
_CLR_ERROR_LIGHT = "FEF2F2"

_THIN_SIDE = Side(style="thin", color=_CLR_BORDER)
_THIN_BORDER = Border(
    left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE
)

_FONT_HEADER = Font(name="Calibri", bold=True, size=14, color=_CLR_TEXT_PRIMARY)
_FONT_SUBHEADER = Font(name="Calibri", bold=True, size=11, color=_CLR_TEXT_PRIMARY)
_FONT_TABLE_HEADER = Font(name="Calibri", bold=True, size=10, color=_CLR_TEXT_SECONDARY)
_FONT_DATA = Font(name="Calibri", size=10, color=_CLR_TEXT_PRIMARY)
_FONT_MONO = Font(name="Consolas", size=10, color=_CLR_TEXT_PRIMARY)
_FONT_SUCCESS = Font(name="Calibri", bold=True, size=10, color=_CLR_SUCCESS)
_FONT_WARNING = Font(name="Calibri", bold=True, size=10, color=_CLR_WARNING)
_FONT_ERROR = Font(name="Calibri", bold=True, size=10, color=_CLR_ERROR)
_FONT_LABEL = Font(name="Calibri", size=10, color=_CLR_TEXT_SECONDARY)

_FILL_TABLE_HEADER = PatternFill(start_color=_CLR_BG_SECONDARY, end_color=_CLR_BG_SECONDARY, fill_type="solid")
_FILL_SUCCESS = PatternFill(start_color=_CLR_SUCCESS_LIGHT, end_color=_CLR_SUCCESS_LIGHT, fill_type="solid")
_FILL_WARNING = PatternFill(start_color=_CLR_WARNING_LIGHT, end_color=_CLR_WARNING_LIGHT, fill_type="solid")
_FILL_ERROR = PatternFill(start_color=_CLR_ERROR_LIGHT, end_color=_CLR_ERROR_LIGHT, fill_type="solid")

_ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")

_CHECK_TYPE_LABELS: dict[str, str] = {
    "permitted_task": "Разрешённые задачи",
    "hours_mismatch": "Расхождение часов",
    "comment_quality": "Качество комментариев",
    "comment_relevance": "Релевантность комментариев",
    "time_limit": "Лимит времени",
    "general_rules": "Общие правила",
}

_COUNTRY_LABELS: dict[str, str] = {
    "RU": "Россия",
    "KZ": "Казахстан",
    "BY": "Беларусь",
}


# ---------------------------------------------------------------------------
# Named styles (registered once per workbook)
# ---------------------------------------------------------------------------

def _register_styles(wb: Workbook) -> None:
    """Create and register reusable NamedStyle objects."""

    styles: list[NamedStyle] = [
        NamedStyle(
            name="ta_header",
            font=_FONT_HEADER,
            alignment=_ALIGN_LEFT,
        ),
        NamedStyle(
            name="ta_subheader",
            font=_FONT_SUBHEADER,
            alignment=_ALIGN_LEFT,
        ),
        NamedStyle(
            name="ta_table_header",
            font=_FONT_TABLE_HEADER,
            fill=_FILL_TABLE_HEADER,
            border=_THIN_BORDER,
            alignment=_ALIGN_CENTER,
        ),
        NamedStyle(
            name="ta_data",
            font=_FONT_DATA,
            border=_THIN_BORDER,
            alignment=_ALIGN_LEFT,
        ),
        NamedStyle(
            name="ta_mono",
            font=_FONT_MONO,
            border=_THIN_BORDER,
            alignment=_ALIGN_LEFT,
        ),
        NamedStyle(
            name="ta_label",
            font=_FONT_LABEL,
            alignment=_ALIGN_LEFT,
        ),
        NamedStyle(
            name="ta_status_ok",
            font=_FONT_SUCCESS,
            fill=_FILL_SUCCESS,
            border=_THIN_BORDER,
            alignment=_ALIGN_CENTER,
        ),
        NamedStyle(
            name="ta_status_warning",
            font=_FONT_WARNING,
            fill=_FILL_WARNING,
            border=_THIN_BORDER,
            alignment=_ALIGN_CENTER,
        ),
        NamedStyle(
            name="ta_status_error",
            font=_FONT_ERROR,
            fill=_FILL_ERROR,
            border=_THIN_BORDER,
            alignment=_ALIGN_CENTER,
        ),
    ]

    for s in styles:
        wb.add_named_style(s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_column_widths(ws, widths: dict[int, float]) -> None:
    """Set column widths by 1-based column index."""
    for col_idx, width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _write_row(ws, row: int, values: list, style: str | None = None) -> None:
    """Write a list of values into a row, optionally applying a named style."""
    for col, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=val)
        if style:
            cell.style = style


# ---------------------------------------------------------------------------
# Summary sheet builder ("Сводка")
# ---------------------------------------------------------------------------

def _build_summary_sheet(
    ws,
    wl_by_user: dict[str, list[WorklogEntry]],
    cr_by_user: dict[str, list[CheckResult]],
) -> None:
    """Build the 'Сводка' sheet — one row per employee with hours/status overview."""

    ws.cell(row=1, column=1, value="Сводка по сотрудникам").style = "ta_header"

    headers = [
        "Сотрудник", "Страна", "Факт, ч", "Норма, ч",
        "Разница", "Статус", "Замечания",
    ]
    header_row = 3
    _write_row(ws, header_row, headers, style="ta_table_header")

    total_actual = 0.0
    total_expected = 0.0
    current_row = header_row + 1

    for username in sorted(wl_by_user.keys()):
        user_wl = wl_by_user[username]
        user_cr = cr_by_user.get(username, [])
        country = get_country(username)

        actual = sum(wl.hours for wl in user_wl)
        dates = [wl.started for wl in user_wl]
        year = min(dates).year
        month = min(dates).month
        try:
            expected = get_expected_hours(country, year, month)
        except ValueError:
            expected = 0.0
        diff = actual - expected

        has_error = any(cr.severity == "error" for cr in user_cr)
        has_warning = any(cr.severity == "warning" for cr in user_cr)
        if has_error:
            status = "Ошибка"
        elif has_warning:
            status = "Внимание"
        else:
            status = "OK"

        issue_count = len(user_cr)
        total_actual += actual
        total_expected += expected

        row_vals = [
            username,
            country,
            round(actual, 1),
            round(expected, 1),
            round(diff, 1),
            status,
            issue_count,
        ]
        _write_row(ws, current_row, row_vals, style="ta_data")

        # Apply monospace to numeric columns
        for col in (3, 4, 5, 7):
            ws.cell(row=current_row, column=col).style = "ta_mono"

        # Status cell coloring
        status_cell = ws.cell(row=current_row, column=6)
        if status == "Ошибка":
            status_cell.style = "ta_status_error"
        elif status == "Внимание":
            status_cell.style = "ta_status_warning"
        else:
            status_cell.style = "ta_status_ok"

        current_row += 1

    # Totals row
    current_row += 1
    ws.cell(row=current_row, column=1, value="Итого").font = _FONT_SUBHEADER
    ws.cell(row=current_row, column=3, value=round(total_actual, 1)).style = "ta_mono"
    ws.cell(row=current_row, column=3).font = _FONT_SUBHEADER
    ws.cell(row=current_row, column=4, value=round(total_expected, 1)).style = "ta_mono"
    ws.cell(row=current_row, column=4).font = _FONT_SUBHEADER

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    _set_column_widths(ws, {
        1: 30,  # Сотрудник
        2: 14,  # Страна
        3: 12,  # Факт
        4: 12,  # Норма
        5: 12,  # Разница
        6: 14,  # Статус
        7: 14,  # Замечания
    })


# ---------------------------------------------------------------------------
# Distribution sheet builder ("Распределение")
# ---------------------------------------------------------------------------

def _build_distribution_sheet(
    ws,
    wl_by_user: dict[str, list[WorklogEntry]],
) -> None:
    """Build the 'Распределение' sheet — hours by project × employee pivot."""

    ws.cell(row=1, column=1, value="Распределение часов по проектам").style = "ta_header"

    sorted_users = sorted(wl_by_user.keys())
    projects: set[str] = set()
    hours_matrix: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for username, entries in wl_by_user.items():
        for wl in entries:
            projects.add(wl.project)
            hours_matrix[wl.project][username] += wl.hours

    sorted_projects = sorted(projects)

    # Column layout: A = Проект, B..N = employees, last = Итого
    header_row = 3
    ws.cell(row=header_row, column=1, value="Проект").style = "ta_table_header"
    for col_idx, uname in enumerate(sorted_users, start=2):
        parts = uname.split()
        short_name = parts[0] if parts else uname
        ws.cell(row=header_row, column=col_idx, value=short_name).style = "ta_table_header"
    total_col = len(sorted_users) + 2
    ws.cell(row=header_row, column=total_col, value="Итого").style = "ta_table_header"

    current_row = header_row + 1
    user_totals: dict[str, float] = defaultdict(float)

    for project in sorted_projects:
        ws.cell(row=current_row, column=1, value=project).style = "ta_data"
        project_total = 0.0
        for col_idx, uname in enumerate(sorted_users, start=2):
            h = hours_matrix[project].get(uname, 0.0)
            val = round(h, 1) if h else None
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.style = "ta_mono"
            project_total += h
            user_totals[uname] += h
        ws.cell(row=current_row, column=total_col, value=round(project_total, 1)).style = "ta_mono"
        current_row += 1

    # "Итого" row per employee
    current_row += 1
    ws.cell(row=current_row, column=1, value="Итого").font = _FONT_SUBHEADER
    grand_total = 0.0
    for col_idx, uname in enumerate(sorted_users, start=2):
        t = user_totals[uname]
        cell = ws.cell(row=current_row, column=col_idx, value=round(t, 1))
        cell.style = "ta_mono"
        cell.font = _FONT_SUBHEADER
        grand_total += t
    cell = ws.cell(row=current_row, column=total_col, value=round(grand_total, 1))
    cell.style = "ta_mono"
    cell.font = _FONT_SUBHEADER

    # --- Region totals section ---
    current_row += 2
    ws.cell(row=current_row, column=1, value="Итого по регионам").style = "ta_subheader"
    current_row += 1

    region_headers = ["Регион", "Сотрудников", "Часов"]
    _write_row(ws, current_row, region_headers, style="ta_table_header")
    current_row += 1

    region_hours: dict[str, float] = defaultdict(float)
    region_count: dict[str, int] = defaultdict(int)
    for uname in sorted_users:
        country = get_country(uname)
        region_hours[country] += user_totals.get(uname, 0.0)
        region_count[country] += 1

    for country in sorted(region_hours.keys()):
        label = _COUNTRY_LABELS.get(country, country)
        _write_row(
            ws, current_row,
            [label, region_count[country], round(region_hours[country], 1)],
            style="ta_data",
        )
        ws.cell(row=current_row, column=2).style = "ta_mono"
        ws.cell(row=current_row, column=3).style = "ta_mono"
        current_row += 1

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    _set_column_widths(ws, {1: 24})
    for col_idx in range(2, total_col + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14


# ---------------------------------------------------------------------------
# Errors sheet builder ("Ошибки")
# ---------------------------------------------------------------------------

_FIX_HINTS: dict[str, str] = {
    "permitted_task": "Перенести списание на разрешённую задачу",
    "comment_quality": "Исправить комментарий согласно требованиям",
    "comment_relevance": "Переписать комментарий, чтобы он соответствовал задаче",
    "time_limit": "Уменьшить время списания (лимит: 20 мин/день)",
    "general_rules": "Перенести списание согласно правилам",
}


def _build_errors_sheet(
    ws,
    check_results: list[CheckResult],
    worklogs: list[WorklogEntry],
) -> None:
    """Build the 'Ошибки' sheet — one row per worklog-level error (excluding hours_mismatch)."""

    ws.cell(row=1, column=1, value="Ошибки в списаниях").style = "ta_header"

    headers = [
        "Key", "Title", "Started", "Username",
        "Time Spent (Hours)", "Comment", "Тип ошибки", "Как исправить",
    ]
    header_row = 3
    _write_row(ws, header_row, headers, style="ta_table_header")

    # Build worklog lookup: (key, username) → WorklogEntry
    wl_lookup: dict[tuple[str, str], WorklogEntry] = {}
    for wl in worklogs:
        wl_lookup.setdefault((wl.key, wl.username), wl)

    current_row = header_row + 1

    for cr in check_results:
        if cr.check_type == "hours_mismatch":
            continue

        check_label = _CHECK_TYPE_LABELS.get(cr.check_type, cr.check_type)
        default_fix = _FIX_HINTS.get(cr.check_type, "")

        try:
            details = json.loads(cr.details)
        except (json.JSONDecodeError, TypeError):
            continue

        if cr.check_type == "permitted_task":
            # details: list of {"key", "hours", "title", "reason", "rule_type"}
            for item in details:
                wl = wl_lookup.get((item["key"], cr.username))
                row_data = [
                    item.get("key", ""),
                    item.get("title", ""),
                    wl.started.strftime("%d.%m.%Y") if wl else "",
                    cr.username,
                    round(item.get("hours", 0), 2),
                    (wl.comment or "") if wl else "",
                    check_label,
                    item.get("reason", default_fix),
                ]
                _write_error_row(ws, current_row, row_data)
                current_row += 1

        elif cr.check_type == "comment_quality":
            # details: list of {"key", "hours", "comment", "severity", "reason"}
            for item in details:
                wl = wl_lookup.get((item["key"], cr.username))
                row_data = [
                    item.get("key", ""),
                    (wl.title if wl else ""),
                    wl.started.strftime("%d.%m.%Y") if wl else "",
                    cr.username,
                    round(item.get("hours", 0), 2),
                    item.get("comment", ""),
                    check_label,
                    item.get("reason", default_fix),
                ]
                _write_error_row(ws, current_row, row_data)
                current_row += 1

        elif cr.check_type == "comment_relevance":
            # details: list of {"key", "hours", "comment", "verdict", "explanation"}
            for item in details:
                wl = wl_lookup.get((item["key"], cr.username))
                row_data = [
                    item.get("key", ""),
                    (wl.title if wl else ""),
                    wl.started.strftime("%d.%m.%Y") if wl else "",
                    cr.username,
                    round(item.get("hours", 0), 2),
                    item.get("comment", ""),
                    check_label,
                    item.get("explanation", default_fix),
                ]
                _write_error_row(ws, current_row, row_data)
                current_row += 1

        elif cr.check_type == "general_rules":
            # details: list of {"key", "hours", "title", "reason"}
            for item in details:
                wl = wl_lookup.get((item["key"], cr.username))
                row_data = [
                    item.get("key", ""),
                    item.get("title", ""),
                    wl.started.strftime("%d.%m.%Y") if wl else "",
                    cr.username,
                    round(item.get("hours", 0), 2),
                    (wl.comment or "") if wl else "",
                    check_label,
                    item.get("reason", default_fix),
                ]
                _write_error_row(ws, current_row, row_data)
                current_row += 1

        elif cr.check_type == "time_limit":
            # details: {"year", "month", "actual_hours", "limit_hours", "working_days", "keys"}
            limited_keys = details.get("keys", [])
            for wl in worklogs:
                if wl.username == cr.username and wl.key in limited_keys:
                    row_data = [
                        wl.key,
                        wl.title,
                        wl.started.strftime("%d.%m.%Y"),
                        cr.username,
                        round(wl.hours, 2),
                        wl.comment or "",
                        check_label,
                        default_fix,
                    ]
                    _write_error_row(ws, current_row, row_data)
                    current_row += 1

    if current_row == header_row + 1:
        ws.cell(row=current_row, column=1, value="Нет ошибок").font = _FONT_SUCCESS
        ws.cell(row=current_row, column=1).fill = _FILL_SUCCESS

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    _set_column_widths(ws, {
        1: 16,   # Key
        2: 40,   # Title
        3: 14,   # Started
        4: 28,   # Username
        5: 14,   # Time Spent
        6: 40,   # Comment
        7: 22,   # Тип ошибки
        8: 50,   # Как исправить
    })


def _write_error_row(ws, row: int, values: list) -> None:
    """Write a row into the errors sheet with appropriate styling."""
    for col_idx, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col_idx, value=val)
        if col_idx == 5:  # hours → monospace
            cell.style = "ta_mono"
        elif col_idx == 1:  # key → monospace
            cell.style = "ta_mono"
        else:
            cell.style = "ta_data"


# ---------------------------------------------------------------------------
# Under-logged hours sheet ("Недобор часов")
# ---------------------------------------------------------------------------

def _build_underlogged_sheet(
    ws,
    check_results: list[CheckResult],
) -> None:
    """Build the 'Недобор часов' sheet — hours_mismatch errors about under-logging."""

    ws.cell(row=1, column=1, value="Недобор часов").style = "ta_header"

    headers = [
        "Сотрудник", "Страна", "Месяц",
        "Факт, ч", "Норма, ч", "Разница, ч",
    ]
    header_row = 3
    _write_row(ws, header_row, headers, style="ta_table_header")

    current_row = header_row + 1
    has_rows = False

    for cr in check_results:
        if cr.check_type != "hours_mismatch":
            continue

        try:
            details = json.loads(cr.details)
        except (json.JSONDecodeError, TypeError):
            continue

        diff = details.get("diff", 0)
        if diff >= 0:
            continue

        has_rows = True
        year = details.get("year", 0)
        month = details.get("month", 0)
        country = details.get("country", "")

        row_data = [
            cr.username,
            country,
            f"{month:02d}.{year}",
            round(details.get("actual_hours", 0), 1),
            round(details.get("expected_hours", 0), 1),
            round(diff, 1),
        ]
        _write_row(ws, current_row, row_data, style="ta_data")

        for col in (4, 5, 6):
            ws.cell(row=current_row, column=col).style = "ta_mono"

        # Highlight the difference cell in red
        diff_cell = ws.cell(row=current_row, column=6)
        diff_cell.font = _FONT_ERROR
        diff_cell.fill = _FILL_ERROR

        current_row += 1

    if not has_rows:
        ws.cell(row=current_row, column=1, value="Нет недобора часов").font = _FONT_SUCCESS
        ws.cell(row=current_row, column=1).fill = _FILL_SUCCESS

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    _set_column_widths(ws, {
        1: 30,   # Сотрудник
        2: 14,   # Страна
        3: 12,   # Месяц
        4: 12,   # Факт
        5: 12,   # Норма
        6: 14,   # Разница
    })


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(upload_id: int, db: Session) -> bytes:
    """Build an openpyxl Workbook and return .xlsx bytes.

    Sheets: Сводка, Распределение, Ошибки, Недобор часов.
    """

    worklogs: list[WorklogEntry] = (
        db.query(WorklogEntry)
        .filter(WorklogEntry.upload_id == upload_id)
        .all()
    )
    if not worklogs:
        raise ValueError(f"No worklog entries for upload {upload_id}")

    check_results: list[CheckResult] = (
        db.query(CheckResult)
        .filter(CheckResult.upload_id == upload_id)
        .all()
    )

    # Group by username
    wl_by_user: dict[str, list[WorklogEntry]] = defaultdict(list)
    for wl in worklogs:
        wl_by_user[wl.username].append(wl)

    cr_by_user: dict[str, list[CheckResult]] = defaultdict(list)
    for cr in check_results:
        cr_by_user[cr.username].append(cr)

    wb = Workbook()
    _register_styles(wb)

    # Remove the default sheet created by Workbook()
    default_ws = wb.active
    if default_ws is not None:
        wb.remove(default_ws)

    # 1) Summary sheet — must be first
    ws_summary = wb.create_sheet(title="Сводка")
    _build_summary_sheet(ws_summary, wl_by_user, cr_by_user)

    # 2) Distribution sheet — second
    ws_distribution = wb.create_sheet(title="Распределение")
    _build_distribution_sheet(ws_distribution, wl_by_user)

    # 3) Consolidated errors sheet
    ws_errors = wb.create_sheet(title="Ошибки")
    _build_errors_sheet(ws_errors, check_results, worklogs)

    # 4) Under-logged hours sheet (hours_mismatch with negative diff)
    ws_underlogged = wb.create_sheet(title="Недобор часов")
    _build_underlogged_sheet(ws_underlogged, check_results)

    logger.info(
        "Report generated for upload %d: 4 sheets, %d check results",
        upload_id,
        len(check_results),
    )

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
