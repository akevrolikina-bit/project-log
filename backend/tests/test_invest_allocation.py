"""Tests for invest project ordering and multi-project manual splits."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.invest_summary import (
    PlanVsFactRow,
    aggregate_invest_hours,
    format_project_total_line,
    group_plan_vs_fact_by_project,
    group_saved_allocations,
)
from app.services.permitted_tasks import (
    INVEST_AUTO,
    INVEST_KEYWORD,
    INVEST_MANUAL_PERCENT,
    INVEST_MANUAL_PROJECT,
    INVEST_PLAN_FTE,
    load_permitted_tasks,
    match_keyword_project,
    sort_invest_projects,
)


def test_sort_invest_projects_puts_mena_first():
    assert sort_invest_projects({"Alphyn", "MENA", "Zeta"}) == [
        "MENA",
        "Alphyn",
        "Zeta",
    ]
    assert sort_invest_projects(["Alphyn", "Zeta"]) == ["Alphyn", "Zeta"]
    assert sort_invest_projects([]) == []
    assert sort_invest_projects(["MENA"]) == ["MENA"]


def test_group_saved_allocations_keeps_all_projects_for_one_task():
    rows = [
        SimpleNamespace(username="Ivan", task_key="BUH-1", invest_project="MENA"),
        SimpleNamespace(username="Ivan", task_key="BUH-1", invest_project="Alphyn"),
        SimpleNamespace(username="Ivan", task_key="BUH-2", invest_project="MENA"),
    ]
    grouped = group_saved_allocations(rows)
    assert len(grouped[("Ivan", "BUH-1")]) == 2
    assert len(grouped[("Ivan", "BUH-2")]) == 1


class _FakeRegistry:
    def __init__(self, alloc_type: str):
        self.alloc_type = alloc_type

    def get_invest_info(self, key: str, project: str, task_type: str):
        return ("MENA / другой", self.alloc_type)

    def resolve_keyword_invest(self, project: str, task_type: str, title: str):
        return None


def _worklog(*, username="Ivan", key="BUH-1", hours=40.0, title="Shared"):
    return SimpleNamespace(
        username=username,
        key=key,
        project="BUH",
        task_type="Task",
        title=title,
        hours=hours,
        started=datetime(2026, 5, 4),
        comment="",
    )


def _alloc(project: str, percentage: float, *, username="Ivan", key="BUH-1"):
    return SimpleNamespace(
        username=username,
        task_key=key,
        invest_project=project,
        percentage=percentage,
        allocation_type="manual_percent",
    )


def test_manual_percent_splits_hours_across_projects():
    wl = _worklog(hours=40.0)
    saved = group_saved_allocations(
        [_alloc("MENA", 30), _alloc("Alphyn", 20)]
    )
    result = aggregate_invest_hours(
        worklogs=[wl],
        selected_users={"Ivan"},
        registry=_FakeRegistry(INVEST_MANUAL_PERCENT),
        buh_map={},
        saved_alloc=saved,
        fte_by_user={},
        auto_agg={},
        buh_agg={},
        manual_agg={},
    )
    by_project = {r.invest_project: r for r in result.manual_rows}
    assert set(by_project) == {"MENA", "Alphyn"}
    assert by_project["MENA"].hours == 40.0
    assert by_project["MENA"].percentage == 30
    assert by_project["Alphyn"].percentage == 20
    assert result.emp_dir_hours[("Ivan", "MENA")] == 12.0
    assert result.emp_dir_hours[("Ivan", "Alphyn")] == 8.0


def test_manual_project_one_assignment_stays_100_percent():
    wl = _worklog(hours=10.0)
    saved = group_saved_allocations([_alloc("MENA", 100)])
    result = aggregate_invest_hours(
        worklogs=[wl],
        selected_users={"Ivan"},
        registry=_FakeRegistry(INVEST_MANUAL_PROJECT),
        buh_map={},
        saved_alloc=saved,
        fte_by_user={},
        auto_agg={},
        buh_agg={},
        manual_agg={},
    )
    assert len(result.manual_rows) == 1
    row = result.manual_rows[0]
    assert row.invest_project == "MENA"
    assert row.percentage == 100
    assert result.emp_dir_hours[("Ivan", "MENA")] == 10.0


def test_auto_allocation_keeps_alphyn_direction():
    """Type 1 hours follow the project name from column I, not only MENA."""

    class AlphynAuto(_FakeRegistry):
        def get_invest_info(self, key, project, task_type):
            return ("Alphyn", INVEST_AUTO)

    wl = _worklog(hours=5.0, key="BUH-122582", title="ALPHYN Проведение платежей")
    result = aggregate_invest_hours(
        worklogs=[wl],
        selected_users={"Ivan"},
        registry=AlphynAuto("unused"),
        buh_map={},
        saved_alloc={},
        fte_by_user={},
        auto_agg={},
        buh_agg={},
        manual_agg={},
    )
    assert len(result.auto_rows) == 1
    assert result.auto_rows[0].invest_project == "Alphyn"
    assert result.emp_dir_hours[("Ivan", "Alphyn")] == 5.0


def test_plan_fte_multiplies_logged_hours_by_fte():
    """0.2 Alphyn + 0.1 MENA of 40 GENERAL hours → 8 and 4, not a 2:1 split of 40."""
    wl = _worklog(hours=40.0, key="GENERAL-1")
    result = aggregate_invest_hours(
        worklogs=[wl],
        selected_users={"Ivan"},
        registry=_FakeRegistry(INVEST_PLAN_FTE),
        buh_map={},
        saved_alloc={},
        fte_by_user={"Ivan": {"Alphyn": 0.2, "MENA": 0.1}},
        auto_agg={},
        buh_agg={},
        manual_agg={},
    )
    assert result.emp_dir_hours[("Ivan", "Alphyn")] == 8.0
    assert result.emp_dir_hours[("Ivan", "MENA")] == 4.0
    assert len(result.emp_dir_hours) == 2


def test_group_plan_vs_fact_by_project_totals_and_mena_first():
    rows = [
        PlanVsFactRow("Ivan", "Alphyn", 0.2, 32.0, 30.0, 0.1875, -0.0125, -2.0),
        PlanVsFactRow("Ivan", "MENA", 0.1, 16.0, 20.0, 0.125, 0.025, 4.0),
        PlanVsFactRow("Petr", "MENA", 0.5, 80.0, 70.0, 0.4375, -0.0625, -10.0),
    ]
    grouped = group_plan_vs_fact_by_project(rows)
    assert [g.invest_project for g in grouped] == ["MENA", "Alphyn"]

    mena = grouped[0]
    assert mena.plan_fte == 0.6
    assert mena.plan_hours == 96.0
    assert mena.fact_hours == 90.0
    assert mena.fact_fte == 0.5625
    assert mena.delta_hours == -6.0
    assert mena.delta_fte == -0.0375
    assert [p.username for p in mena.people] == ["Ivan", "Petr"]

    line = format_project_total_line(mena)
    assert line.startswith("Итого проект MENA:")
    assert "план 96.00 часов" in line
    assert "план 0.60 FTE" in line
    assert "факт 90.00 часов" in line
    assert "0.56 FTE" in line
    assert "разница план-факт -6.00 часов" in line


def test_mena_keywords_match_dbad_and_db_ad():
    rules = {
        "MENA": ["ОАЭ", "КСА", "DBFZ", "DBAD", "DB AD"],
        "Alphyn": ["ALFZ", "Alphyn"],
    }
    assert match_keyword_project("Акт DBAD FZ", rules) == "MENA"
    assert match_keyword_project("Договор DB AD 2026", rules) == "MENA"
    assert match_keyword_project("ALFZ контрагент", rules) == "Alphyn"


def test_rules_workbook_includes_dbad_mena_keywords():
    """Smoke-test that the live workbook picked up DBAD / DB AD for MENA."""
    path = Path(settings.permitted_tasks_path)
    if not path.exists():
        pytest.skip(f"Rules workbook is not present: {path}")

    reg = load_permitted_tasks()
    mena_keywords = [
        k.lower()
        for k in reg.project_type_rules[("BUH", "Прочее")].keyword_rules.get("MENA", [])
    ]
    assert "dbad" in mena_keywords
    assert "db ad" in mena_keywords
    assert reg.resolve_keyword_invest("BUH", "Прочее", "Акт DBAD") == "MENA"
    assert reg.resolve_keyword_invest("BUH", "Прочее", "Договор DB AD") == "MENA"
    assert reg.resolve_keyword_invest("HR", "Civil law contract", "GPH DBAD") == "MENA"
    assert (
        reg.resolve_keyword_invest("BUH", "Акт сверки взаиморасчетов", "Сверка DB AD")
        == "MENA"
    )
    assert reg.get_invest_info("X", "BUH", "Прочее")[1] == INVEST_KEYWORD


_ALPHYN_AUTO_KEYS = {
    "BUH-121400",
    "BUH-122582",
    "BUH-122583",
    "BUH-122585",
    "BUH-122586",
    "BUH-122587",
    "BUH-122589",
    "BUH-122591",
    "BUH-122592",
}


def test_rules_workbook_includes_alphyn_auto_tasks():
    """Smoke-test that Alphyn operational keys are Type 1 auto."""
    path = Path(settings.permitted_tasks_path)
    if not path.exists():
        pytest.skip(f"Rules workbook is not present: {path}")

    reg = load_permitted_tasks()
    assert "Alphyn" in reg.list_concrete_invest_directions()
    for key in _ALPHYN_AUTO_KEYS:
        assert reg.get_invest_info(key, "BUH", "Task") == ("Alphyn", INVEST_AUTO)
