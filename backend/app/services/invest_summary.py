"""Shared helpers for invest-hour aggregation and plan-vs-fact comparison."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.models.invest_allocation import BuhCompanyMapping, InvestAllocation
from app.models.worklog import WorklogEntry
from app.services.employee_country import get_country
from app.services.calendar import get_expected_hours
from app.services.permitted_tasks import (
    INVEST_AUTO,
    INVEST_BUH_COMPANY,
    INVEST_KEYWORD,
    INVEST_MANUAL_PERCENT,
    INVEST_MANUAL_PROJECT,
    INVEST_PLAN_FTE,
    PermittedTasksRegistry,
    sort_invest_projects,
)

SavedAllocMap = dict[tuple[str, str], list[InvestAllocation]]


def group_saved_allocations(
    rows: Iterable[InvestAllocation],
) -> SavedAllocMap:
    """Group allocation rows by (username, task_key).

    One task can have several rows — one per invest project.
    """
    grouped: SavedAllocMap = defaultdict(list)
    for r in rows:
        grouped[(r.username, r.task_key)].append(r)
    return grouped


@dataclass
class PlanVsFactRow:
    username: str
    invest_project: str
    plan_fte: float | None
    plan_hours: float | None
    fact_hours: float
    fact_fte: float | None
    delta_fte: float | None
    delta_hours: float | None


@dataclass
class ProjectPlanVsFact:
    """Plan vs fact totals for one invest project, with per-person detail."""

    invest_project: str
    plan_fte: float | None
    plan_hours: float | None
    fact_hours: float
    fact_fte: float | None
    delta_fte: float | None
    delta_hours: float | None
    people: list[PlanVsFactRow]


@dataclass
class InvestAggregation:
    """Invest hours grouped for reporting."""

    auto_rows: list = field(default_factory=list)
    buh_rows: list = field(default_factory=list)
    manual_rows: list = field(default_factory=list)
    emp_dir_hours: dict[tuple[str, str], float] = field(default_factory=dict)
    plan_vs_fact: list[PlanVsFactRow] = field(default_factory=list)
    expected_by_user: dict[str, float] = field(default_factory=dict)


def expected_hours_for_username(
    worklogs: list[WorklogEntry], username: str
) -> float:
    """Return calendar norm hours for the employee's worklog month."""
    user_wl = [wl for wl in worklogs if wl.username == username]
    if not user_wl:
        return 0.0
    country = get_country(username)
    dates = [wl.started for wl in user_wl]
    year = min(dates).year
    month = min(dates).month
    try:
        return get_expected_hours(country, year, month)
    except ValueError:
        return 0.0


def compute_emp_dir_hours(
    *,
    auto_rows: list,
    buh_rows: list,
    manual_rows: list,
) -> dict[tuple[str, str], float]:
    """Sum invest hours by (employee, project) from aggregated rows."""
    emp_dir_hours: dict[tuple[str, str], float] = defaultdict(float)

    for r in auto_rows:
        emp_dir_hours[(r.username, r.invest_project)] += r.hours

    for r in buh_rows:
        if r.invest_project:
            emp_dir_hours[(r.username, r.invest_project)] += r.hours

    for r in manual_rows:
        if r.invest_project and r.percentage is not None:
            emp_dir_hours[(r.username, r.invest_project)] += (
                r.hours * r.percentage / 100.0
            )

    return dict(emp_dir_hours)


def build_plan_vs_fact(
    *,
    emp_dir_hours: dict[tuple[str, str], float],
    fte_by_user: dict[str, dict[str, float]],
    expected_by_user: dict[str, float],
    selected_users: set[str],
) -> list[PlanVsFactRow]:
    """Build plan-vs-fact rows for every employee × project combination."""
    keys: set[tuple[str, str]] = set()
    for username in selected_users:
        for project in fte_by_user.get(username, {}):
            keys.add((username, project))
    for username, project in emp_dir_hours:
        if username in selected_users:
            keys.add((username, project))

    rows: list[PlanVsFactRow] = []
    for username, project in sorted(
        keys, key=lambda t: (t[0], 0 if t[1] == "MENA" else 1, t[1])
    ):
        plan_fte = fte_by_user.get(username, {}).get(project)
        expected = expected_by_user.get(username, 0.0)
        fact_hours = emp_dir_hours.get((username, project), 0.0)

        plan_hours = (
            round(plan_fte * expected, 2)
            if plan_fte is not None and expected > 0
            else None
        )
        fact_fte = (
            round(fact_hours / expected, 4) if expected > 0 else None
        )
        delta_fte = (
            round(fact_fte - plan_fte, 4)
            if fact_fte is not None and plan_fte is not None
            else None
        )
        delta_hours = (
            round(fact_hours - plan_hours, 2)
            if plan_hours is not None
            else None
        )

        rows.append(
            PlanVsFactRow(
                username=username,
                invest_project=project,
                plan_fte=plan_fte,
                plan_hours=plan_hours,
                fact_hours=round(fact_hours, 2),
                fact_fte=fact_fte,
                delta_fte=delta_fte,
                delta_hours=delta_hours,
            )
        )

    return rows


def _sum_known(values: Iterable[float | None]) -> float | None:
    """Sum non-null numbers. Return None when every value is missing."""
    known = [v for v in values if v is not None]
    if not known:
        return None
    return sum(known)


def group_plan_vs_fact_by_project(
    rows: list[PlanVsFactRow],
) -> list[ProjectPlanVsFact]:
    """Group employee rows by invest project and add plan/fact totals.

    MENA comes first, then the remaining projects alphabetically.
    People inside a project are sorted by name.
    """
    by_project: dict[str, list[PlanVsFactRow]] = defaultdict(list)
    for row in rows:
        by_project[row.invest_project].append(row)

    grouped: list[ProjectPlanVsFact] = []
    for project in sort_invest_projects(by_project.keys()):
        people = sorted(by_project[project], key=lambda r: r.username)
        plan_fte = _sum_known(p.plan_fte for p in people)
        plan_hours = _sum_known(p.plan_hours for p in people)
        fact_hours = round(sum(p.fact_hours for p in people), 2)
        fact_fte = _sum_known(p.fact_fte for p in people)
        if plan_fte is not None:
            plan_fte = round(plan_fte, 4)
        if plan_hours is not None:
            plan_hours = round(plan_hours, 2)
        if fact_fte is not None:
            fact_fte = round(fact_fte, 4)
        delta_fte = (
            round(fact_fte - plan_fte, 4)
            if fact_fte is not None and plan_fte is not None
            else None
        )
        delta_hours = (
            round(fact_hours - plan_hours, 2) if plan_hours is not None else None
        )
        grouped.append(
            ProjectPlanVsFact(
                invest_project=project,
                plan_fte=plan_fte,
                plan_hours=plan_hours,
                fact_hours=fact_hours,
                fact_fte=fact_fte,
                delta_fte=delta_fte,
                delta_hours=delta_hours,
                people=people,
            )
        )
    return grouped


def format_project_total_line(block: ProjectPlanVsFact) -> str:
    """Human-readable project total in the agreed UI/Excel wording."""

    def fmt(value: float | None) -> str:
        return f"{value:.2f}" if value is not None else "—"

    return (
        f"Итого проект {block.invest_project}: "
        f"план {fmt(block.plan_hours)} часов, "
        f"план {fmt(block.plan_fte)} FTE, "
        f"факт {fmt(block.fact_hours)} часов, "
        f"{fmt(block.fact_fte)} FTE, "
        f"разница план-факт {fmt(block.delta_hours)} часов, "
        f"разница план-факт {fmt(block.delta_fte)} FTE"
    )


def _append_manual_splits(
    manual_agg: dict,
    wl: WorklogEntry,
    allocs: list[InvestAllocation],
    *,
    allocation_type: str,
    single_default_percent: float | None = None,
) -> None:
    """Add this worklog's hours to one row per invest project (or one empty row)."""
    if not allocs:
        k = (wl.username, wl.key)
        if k in manual_agg:
            manual_agg[k].hours += wl.hours
        else:
            manual_agg[k] = _ManualRow(
                username=wl.username,
                task_key=wl.key,
                title=wl.title,
                hours=wl.hours,
                percentage=None,
                invest_project=None,
                allocation_type=allocation_type,
            )
        return

    for sa in allocs:
        row_key = (wl.username, f"{wl.key}→{sa.invest_project}")
        pct = sa.percentage
        if pct is None and single_default_percent is not None:
            pct = single_default_percent
        if row_key in manual_agg:
            manual_agg[row_key].hours += wl.hours
        else:
            manual_agg[row_key] = _ManualRow(
                username=wl.username,
                task_key=wl.key,
                title=wl.title,
                hours=wl.hours,
                percentage=pct,
                invest_project=sa.invest_project,
                allocation_type=allocation_type,
            )


def aggregate_invest_hours(
    *,
    worklogs: list[WorklogEntry],
    selected_users: set[str],
    registry: PermittedTasksRegistry,
    buh_map: dict[str, BuhCompanyMapping],
    saved_alloc: SavedAllocMap,
    fte_by_user: dict[str, dict[str, float]],
    auto_agg: dict,
    buh_agg: dict,
    manual_agg: dict,
) -> InvestAggregation:
    """Process worklogs into per-employee/project fact hours and plan comparison."""
    user_worklogs = [wl for wl in worklogs if wl.username in selected_users]

    for wl in user_worklogs:
        info = registry.get_invest_info(wl.key, wl.project, wl.task_type)
        if info is None:
            continue

        direction, alloc_type = info
        k = (wl.username, wl.key)
        allocs = saved_alloc.get(k, [])

        if alloc_type == INVEST_AUTO:
            if k in auto_agg:
                auto_agg[k].hours += wl.hours
            else:
                auto_agg[k] = _AutoRow(
                    username=wl.username,
                    task_key=wl.key,
                    title=wl.title,
                    hours=wl.hours,
                    invest_project=direction,
                )

        elif alloc_type == INVEST_BUH_COMPANY:
            buh_entry = buh_map.get(wl.key)
            if buh_entry and buh_entry.invest_project:
                if k in buh_agg:
                    buh_agg[k].hours += wl.hours
                else:
                    buh_agg[k] = _BuhRow(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=wl.hours,
                        buh_company=buh_entry.buh_company,
                        invest_project=buh_entry.invest_project,
                    )
            elif len(allocs) >= 2:
                # Several invest projects: same as a manual split.
                _append_manual_splits(
                    manual_agg,
                    wl,
                    allocs,
                    allocation_type="manual_project",
                )
            else:
                sa = allocs[0] if allocs else None
                if k in buh_agg:
                    buh_agg[k].hours += wl.hours
                else:
                    buh_agg[k] = _BuhRow(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=wl.hours,
                        buh_company=buh_entry.buh_company if buh_entry else "",
                        invest_project=sa.invest_project if sa else None,
                        manual_assigned=sa is not None,
                    )

        elif alloc_type == INVEST_MANUAL_PERCENT:
            _append_manual_splits(
                manual_agg,
                wl,
                allocs,
                allocation_type="manual_percent",
            )

        elif alloc_type == INVEST_MANUAL_PROJECT:
            _append_manual_splits(
                manual_agg,
                wl,
                allocs,
                allocation_type="manual_project",
                single_default_percent=100.0,
            )

        elif alloc_type == INVEST_KEYWORD:
            matched = registry.resolve_keyword_invest(
                wl.project, wl.task_type, wl.title
            )
            if matched:
                if k in manual_agg:
                    manual_agg[k].hours += wl.hours
                    if not manual_agg[k].invest_project:
                        manual_agg[k].invest_project = matched
                        manual_agg[k].percentage = 100.0
                else:
                    manual_agg[k] = _ManualRow(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=wl.hours,
                        percentage=100.0,
                        invest_project=matched,
                        allocation_type="keyword",
                    )
            else:
                _append_manual_splits(
                    manual_agg,
                    wl,
                    allocs,
                    allocation_type="keyword",
                    single_default_percent=100.0,
                )

        elif alloc_type == INVEST_PLAN_FTE:
            # FTE is applied as-is to logged hours (0.2 FTE of 40 h → 8 h).
            # Remaining hours stay outside invest directions.
            user_fte = {
                project: fte
                for project, fte in fte_by_user.get(wl.username, {}).items()
                if fte > 0
            }
            if not user_fte:
                if k in manual_agg:
                    manual_agg[k].hours += wl.hours
                else:
                    manual_agg[k] = _ManualRow(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=wl.hours,
                        percentage=None,
                        invest_project=None,
                        allocation_type="plan_fte",
                    )
            else:
                for project, fte in user_fte.items():
                    plan_key = (wl.username, f"{wl.key}→{project}")
                    portion_hours = wl.hours * fte
                    if plan_key in manual_agg:
                        manual_agg[plan_key].hours += portion_hours
                    else:
                        manual_agg[plan_key] = _ManualRow(
                            username=wl.username,
                            task_key=wl.key,
                            title=wl.title,
                            hours=portion_hours,
                            percentage=100.0,
                            invest_project=project,
                            allocation_type="plan_fte",
                        )

    auto_rows = sorted(auto_agg.values(), key=lambda r: (r.username, r.task_key))
    buh_rows = sorted(buh_agg.values(), key=lambda r: (r.username, r.task_key))
    manual_rows = sorted(manual_agg.values(), key=lambda r: (r.username, r.task_key))

    emp_dir_hours = compute_emp_dir_hours(
        auto_rows=auto_rows,
        buh_rows=buh_rows,
        manual_rows=manual_rows,
    )

    expected_by_user = {
        u: expected_hours_for_username(worklogs, u) for u in selected_users
    }
    plan_vs_fact = build_plan_vs_fact(
        emp_dir_hours=emp_dir_hours,
        fte_by_user=fte_by_user,
        expected_by_user=expected_by_user,
        selected_users=selected_users,
    )

    return InvestAggregation(
        auto_rows=auto_rows,
        buh_rows=buh_rows,
        manual_rows=manual_rows,
        emp_dir_hours=emp_dir_hours,
        plan_vs_fact=plan_vs_fact,
        expected_by_user=expected_by_user,
    )


@dataclass
class _AutoRow:
    username: str
    task_key: str
    title: str
    hours: float
    invest_project: str


@dataclass
class _BuhRow:
    username: str
    task_key: str
    title: str
    hours: float
    buh_company: str
    invest_project: str | None
    manual_assigned: bool = False


@dataclass
class _ManualRow:
    username: str
    task_key: str
    title: str
    hours: float
    percentage: float | None
    invest_project: str | None
    allocation_type: str
