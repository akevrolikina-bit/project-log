"""API endpoints for investment direction allocation workflow."""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.invest_allocation import (
    BuhCompanyMapping,
    InvestAllocation,
    InvestEmployeeSelection,
    InvestFtePlan,
)
from app.models.upload import Upload
from app.models.worklog import WorklogEntry
from app.services.buh_company import (
    merge_buh_companies,
    resolve_invest_project,
)
from app.services.invest_summary import aggregate_invest_hours, group_saved_allocations
from app.services.permitted_tasks import (
    INVEST_AUTO,
    INVEST_BUH_COMPANY,
    INVEST_KEYWORD,
    INVEST_MANUAL_PERCENT,
    INVEST_MANUAL_PROJECT,
    INVEST_PLAN_FTE,
    load_permitted_tasks,
    sort_invest_projects,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["invest"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EmployeeInvestInfo(BaseModel):
    username: str
    total_hours: float
    has_invest_tasks: bool
    selected: bool


class EmployeeSelectionPayload(BaseModel):
    usernames: list[str]


class AllocationEntry(BaseModel):
    username: str
    task_key: str
    invest_project: str
    percentage: float
    allocation_type: str


class AutoEntry(BaseModel):
    username: str
    task_key: str
    title: str
    hours: float
    invest_project: str


class BuhEntry(BaseModel):
    username: str
    task_key: str
    title: str
    hours: float
    buh_company: str | None
    invest_project: str | None


class ManualPercentEntry(BaseModel):
    username: str
    task_key: str
    title: str
    hours: float
    invest_project: str | None = None
    percentage: float | None = None


class ManualProjectEntry(BaseModel):
    username: str
    task_key: str
    title: str
    hours: float
    invest_project: str | None = None


class KeywordEntry(BaseModel):
    username: str
    task_key: str
    title: str
    hours: float
    matched_project: str | None = None


class PlanFteEntry(BaseModel):
    username: str
    task_key: str
    title: str
    hours: float


class FtePlanItem(BaseModel):
    username: str
    invest_project: str
    fte_value: float


class PlanVsFactEntry(BaseModel):
    username: str
    invest_project: str
    plan_fte: float | None = None
    plan_hours: float | None = None
    fact_hours: float
    fact_fte: float | None = None
    delta_fte: float | None = None
    delta_hours: float | None = None


class ExpectedHoursEntry(BaseModel):
    username: str
    expected_hours: float


class SavedAllocationItem(BaseModel):
    username: str
    task_key: str
    invest_project: str
    percentage: float
    allocation_type: str

    model_config = {"from_attributes": True}


class InvestDataResponse(BaseModel):
    auto_entries: list[AutoEntry]
    buh_entries: list[BuhEntry]
    manual_percent_entries: list[ManualPercentEntry]
    manual_project_entries: list[ManualProjectEntry]
    keyword_entries: list[KeywordEntry]
    plan_fte_entries: list[PlanFteEntry]
    fte_plans: list[FtePlanItem]
    plan_vs_fact: list[PlanVsFactEntry]
    expected_hours: list[ExpectedHoursEntry]
    selected_employees: list[str]
    saved_allocations: list[SavedAllocationItem]
    invest_projects: list[str]


class AllocationPayload(BaseModel):
    allocations: list[AllocationEntry]
    fte_plans: list[FtePlanItem] = []


class BuhCsvUploadResult(BaseModel):
    total_keys: int
    matched_keys: int
    unmatched_keys: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_upload_or_404(upload_id: int, db: Session) -> Upload:
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return upload


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{upload_id}/invest/employees", response_model=list[EmployeeInvestInfo])
def get_invest_employees(upload_id: int, db: Session = Depends(get_db)):
    """List all employees from this upload with invest-task metadata."""
    _get_upload_or_404(upload_id, db)

    worklogs = (
        db.query(WorklogEntry)
        .filter(WorklogEntry.upload_id == upload_id)
        .all()
    )

    registry = load_permitted_tasks()

    hours_by_user: dict[str, float] = defaultdict(float)
    invest_flags: dict[str, bool] = defaultdict(bool)

    for wl in worklogs:
        hours_by_user[wl.username] += wl.hours
        info = registry.get_invest_info(wl.key, wl.project, wl.task_type)
        if info is not None:
            invest_flags[wl.username] = True

    selected_rows = (
        db.query(InvestEmployeeSelection)
        .filter(InvestEmployeeSelection.upload_id == upload_id)
        .all()
    )
    selected_set = {r.username for r in selected_rows}

    result: list[EmployeeInvestInfo] = []
    for uname in sorted(hours_by_user):
        result.append(
            EmployeeInvestInfo(
                username=uname,
                total_hours=round(hours_by_user[uname], 2),
                has_invest_tasks=invest_flags.get(uname, False),
                selected=uname in selected_set,
            )
        )

    return result


@router.put("/{upload_id}/invest/employees")
def save_invest_employees(
    upload_id: int,
    payload: EmployeeSelectionPayload,
    db: Session = Depends(get_db),
):
    """Save the set of employees selected for invest analysis."""
    _get_upload_or_404(upload_id, db)

    db.query(InvestEmployeeSelection).filter(
        InvestEmployeeSelection.upload_id == upload_id
    ).delete()

    for uname in payload.usernames:
        db.add(InvestEmployeeSelection(upload_id=upload_id, username=uname))

    db.commit()
    return {"status": "ok", "count": len(payload.usernames)}


@router.post(
    "/{upload_id}/invest/buh-csv",
    response_model=BuhCsvUploadResult,
)
async def upload_buh_csv(
    upload_id: int,
    files: list[UploadFile],
    db: Session = Depends(get_db),
):
    """Upload one or more BUH company CSV files and store parsed mappings."""
    _get_upload_or_404(upload_id, db)

    contents: list[bytes] = []
    for f in files:
        contents.append(await f.read())

    merged = merge_buh_companies(contents)

    db.query(BuhCompanyMapping).filter(
        BuhCompanyMapping.upload_id == upload_id
    ).delete()

    matched = 0
    for task_key, buh_company in merged.items():
        project = resolve_invest_project(buh_company)
        if project:
            matched += 1
        db.add(
            BuhCompanyMapping(
                upload_id=upload_id,
                task_key=task_key,
                buh_company=buh_company,
                invest_project=project,
            )
        )

    db.commit()

    return BuhCsvUploadResult(
        total_keys=len(merged),
        matched_keys=matched,
        unmatched_keys=len(merged) - matched,
    )


@router.get("/{upload_id}/invest", response_model=InvestDataResponse)
def get_invest_data(upload_id: int, db: Session = Depends(get_db)):
    """Return the full invest picture for selected employees."""
    _get_upload_or_404(upload_id, db)

    selected_rows = (
        db.query(InvestEmployeeSelection)
        .filter(InvestEmployeeSelection.upload_id == upload_id)
        .all()
    )
    selected_users = {r.username for r in selected_rows}
    if not selected_users:
        return InvestDataResponse(
            auto_entries=[],
            buh_entries=[],
            manual_percent_entries=[],
            manual_project_entries=[],
            keyword_entries=[],
            plan_fte_entries=[],
            fte_plans=[],
            plan_vs_fact=[],
            expected_hours=[],
            selected_employees=[],
            saved_allocations=[],
            invest_projects=[],
        )

    worklogs = (
        db.query(WorklogEntry)
        .filter(
            WorklogEntry.upload_id == upload_id,
            WorklogEntry.username.in_(selected_users),
        )
        .all()
    )

    registry = load_permitted_tasks()

    buh_mappings_rows = (
        db.query(BuhCompanyMapping)
        .filter(BuhCompanyMapping.upload_id == upload_id)
        .all()
    )
    buh_map: dict[str, BuhCompanyMapping] = {r.task_key: r for r in buh_mappings_rows}

    saved_alloc_rows = (
        db.query(InvestAllocation)
        .filter(InvestAllocation.upload_id == upload_id)
        .all()
    )
    saved_alloc_key = group_saved_allocations(saved_alloc_rows)

    def _first_saved(username: str, task_key: str) -> InvestAllocation | None:
        items = saved_alloc_key.get((username, task_key), [])
        return items[0] if items else None

    fte_plan_rows = (
        db.query(InvestFtePlan)
        .filter(InvestFtePlan.upload_id == upload_id)
        .all()
    )

    auto_entries: list[AutoEntry] = []
    buh_entries: list[BuhEntry] = []
    manual_percent_entries: list[ManualPercentEntry] = []
    manual_project_entries: list[ManualProjectEntry] = []
    keyword_entries: list[KeywordEntry] = []
    plan_fte_entries: list[PlanFteEntry] = []
    invest_projects_set: set[str] = set()

    seen_manual_percent: set[tuple[str, str]] = set()
    seen_manual_project: set[tuple[str, str]] = set()
    seen_keyword: set[tuple[str, str]] = set()
    seen_plan_fte: set[tuple[str, str]] = set()
    seen_auto: set[tuple[str, str]] = set()
    seen_buh: set[tuple[str, str]] = set()

    for wl in worklogs:
        info = registry.get_invest_info(wl.key, wl.project, wl.task_type)
        if info is None:
            continue

        direction, alloc_type = info

        if alloc_type == INVEST_AUTO:
            invest_projects_set.add(direction)
            k = (wl.username, wl.key)
            if k not in seen_auto:
                seen_auto.add(k)
                auto_entries.append(
                    AutoEntry(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=0.0,
                        invest_project=direction,
                    )
                )
            for ae in auto_entries:
                if ae.username == wl.username and ae.task_key == wl.key:
                    ae.hours = round(ae.hours + wl.hours, 2)
                    break

        elif alloc_type == INVEST_BUH_COMPANY:
            buh_entry = buh_map.get(wl.key)
            k = (wl.username, wl.key)
            if buh_entry and buh_entry.invest_project:
                invest_projects_set.add(buh_entry.invest_project)
                if k not in seen_buh:
                    seen_buh.add(k)
                    buh_entries.append(
                        BuhEntry(
                            username=wl.username,
                            task_key=wl.key,
                            title=wl.title,
                            hours=0.0,
                            buh_company=buh_entry.buh_company,
                            invest_project=buh_entry.invest_project,
                        )
                    )
                for be in buh_entries:
                    if be.username == wl.username and be.task_key == wl.key:
                        be.hours = round(be.hours + wl.hours, 2)
                        break
            else:
                saved = _first_saved(wl.username, wl.key)
                if k not in seen_manual_project:
                    seen_manual_project.add(k)
                    manual_project_entries.append(
                        ManualProjectEntry(
                            username=wl.username,
                            task_key=wl.key,
                            title=wl.title,
                            hours=0.0,
                            invest_project=saved.invest_project if saved else None,
                        )
                    )
                for mp in manual_project_entries:
                    if mp.username == wl.username and mp.task_key == wl.key:
                        mp.hours = round(mp.hours + wl.hours, 2)
                        break

        elif alloc_type == INVEST_MANUAL_PERCENT:
            k = (wl.username, wl.key)
            saved = _first_saved(wl.username, wl.key)
            if k not in seen_manual_percent:
                seen_manual_percent.add(k)
                manual_percent_entries.append(
                    ManualPercentEntry(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=0.0,
                        invest_project=saved.invest_project if saved else None,
                        percentage=saved.percentage if saved else None,
                    )
                )
            for mp in manual_percent_entries:
                if mp.username == wl.username and mp.task_key == wl.key:
                    mp.hours = round(mp.hours + wl.hours, 2)
                    break

        elif alloc_type == INVEST_MANUAL_PROJECT:
            k = (wl.username, wl.key)
            saved = _first_saved(wl.username, wl.key)
            if k not in seen_manual_project:
                seen_manual_project.add(k)
                manual_project_entries.append(
                    ManualProjectEntry(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=0.0,
                        invest_project=saved.invest_project if saved else None,
                    )
                )
            for mp in manual_project_entries:
                if mp.username == wl.username and mp.task_key == wl.key:
                    mp.hours = round(mp.hours + wl.hours, 2)
                    break

        elif alloc_type == INVEST_KEYWORD:
            matched = registry.resolve_keyword_invest(
                wl.project, wl.task_type, wl.title
            )
            k = (wl.username, wl.key)
            saved = _first_saved(wl.username, wl.key)
            if matched:
                invest_projects_set.add(matched)
            elif saved:
                invest_projects_set.add(saved.invest_project)
            if k not in seen_keyword:
                seen_keyword.add(k)
                keyword_entries.append(
                    KeywordEntry(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=0.0,
                        matched_project=matched,
                    )
                )
            for ke in keyword_entries:
                if ke.username == wl.username and ke.task_key == wl.key:
                    ke.hours = round(ke.hours + wl.hours, 2)
                    if not ke.matched_project and matched:
                        ke.matched_project = matched
                    break

        elif alloc_type == INVEST_PLAN_FTE:
            k = (wl.username, wl.key)
            if k not in seen_plan_fte:
                seen_plan_fte.add(k)
                plan_fte_entries.append(
                    PlanFteEntry(
                        username=wl.username,
                        task_key=wl.key,
                        title=wl.title,
                        hours=0.0,
                    )
                )
            for pe in plan_fte_entries:
                if pe.username == wl.username and pe.task_key == wl.key:
                    pe.hours = round(pe.hours + wl.hours, 2)
                    break

    saved_allocations = [
        SavedAllocationItem.model_validate(r)
        for r in saved_alloc_rows
        if r.username in selected_users
    ]

    for sa in saved_alloc_rows:
        invest_projects_set.add(sa.invest_project)

    for fp in fte_plan_rows:
        invest_projects_set.add(fp.invest_project)

    # Always offer concrete directions from the rules file (MENA, Alphyn, …)
    # so manual % / project pickers can target them even when no auto rows
    # for that direction appear in the current selection.
    invest_projects_set.update(registry.list_concrete_invest_directions())

    invest_projects_set = {
        p for p in invest_projects_set if p and "/" not in p
    }
    if not invest_projects_set:
        invest_projects_set.add("MENA")

    all_worklogs = (
        db.query(WorklogEntry)
        .filter(WorklogEntry.upload_id == upload_id)
        .all()
    )
    fte_by_user: dict[str, dict[str, float]] = defaultdict(dict)
    for r in fte_plan_rows:
        if r.fte_value > 0:
            fte_by_user[r.username][r.invest_project] = r.fte_value

    invest_result = aggregate_invest_hours(
        worklogs=all_worklogs,
        selected_users=selected_users,
        registry=registry,
        buh_map=buh_map,
        saved_alloc=saved_alloc_key,
        fte_by_user=fte_by_user,
        auto_agg={},
        buh_agg={},
        manual_agg={},
    )

    return InvestDataResponse(
        auto_entries=auto_entries,
        buh_entries=buh_entries,
        manual_percent_entries=manual_percent_entries,
        manual_project_entries=manual_project_entries,
        keyword_entries=keyword_entries,
        plan_fte_entries=plan_fte_entries,
        fte_plans=[
            FtePlanItem(
                username=r.username,
                invest_project=r.invest_project,
                fte_value=r.fte_value,
            )
            for r in fte_plan_rows
        ],
        plan_vs_fact=[
            PlanVsFactEntry(
                username=r.username,
                invest_project=r.invest_project,
                plan_fte=r.plan_fte,
                plan_hours=r.plan_hours,
                fact_hours=r.fact_hours,
                fact_fte=r.fact_fte,
                delta_fte=r.delta_fte,
                delta_hours=r.delta_hours,
            )
            for r in invest_result.plan_vs_fact
        ],
        expected_hours=[
            ExpectedHoursEntry(username=u, expected_hours=h)
            for u, h in sorted(invest_result.expected_by_user.items())
        ],
        selected_employees=sorted(selected_users),
        saved_allocations=saved_allocations,
        invest_projects=sort_invest_projects(invest_projects_set),
    )


@router.put("/{upload_id}/invest")
def save_invest_allocations(
    upload_id: int,
    payload: AllocationPayload,
    db: Session = Depends(get_db),
):
    """Save manual invest allocations (replaces previous for this upload)."""
    _get_upload_or_404(upload_id, db)

    db.query(InvestAllocation).filter(
        InvestAllocation.upload_id == upload_id
    ).delete()

    db.query(InvestFtePlan).filter(
        InvestFtePlan.upload_id == upload_id
    ).delete()

    for a in payload.allocations:
        db.add(
            InvestAllocation(
                upload_id=upload_id,
                username=a.username,
                task_key=a.task_key,
                invest_project=a.invest_project,
                percentage=a.percentage,
                allocation_type=a.allocation_type,
            )
        )

    for fp in payload.fte_plans:
        if fp.fte_value > 0 and fp.username:
            db.add(
                InvestFtePlan(
                    upload_id=upload_id,
                    username=fp.username,
                    invest_project=fp.invest_project,
                    fte_value=fp.fte_value,
                )
            )

    db.commit()
    return {
        "status": "ok",
        "count": len(payload.allocations),
        "fte_plans": len(payload.fte_plans),
    }
