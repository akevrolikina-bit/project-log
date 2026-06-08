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
)
from app.models.upload import Upload
from app.models.worklog import WorklogEntry
from app.services.buh_company import (
    merge_buh_companies,
    resolve_invest_project,
)
from app.services.permitted_tasks import (
    INVEST_AUTO,
    INVEST_BUH_COMPANY,
    INVEST_MANUAL_PERCENT,
    INVEST_MANUAL_PROJECT,
    load_permitted_tasks,
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


class AllocationPayload(BaseModel):
    allocations: list[AllocationEntry]


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
    saved_allocations: list[SavedAllocationItem]
    invest_projects: list[str]


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
    saved_alloc_key: dict[tuple[str, str], InvestAllocation] = {
        (r.username, r.task_key): r for r in saved_alloc_rows
    }

    auto_entries: list[AutoEntry] = []
    buh_entries: list[BuhEntry] = []
    manual_percent_entries: list[ManualPercentEntry] = []
    manual_project_entries: list[ManualProjectEntry] = []
    invest_projects_set: set[str] = set()

    seen_manual_percent: set[tuple[str, str]] = set()
    seen_manual_project: set[tuple[str, str]] = set()
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
                saved = saved_alloc_key.get((wl.username, wl.key))
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
            saved = saved_alloc_key.get(k)
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
            saved = saved_alloc_key.get(k)
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

    saved_allocations = [
        SavedAllocationItem.model_validate(r)
        for r in saved_alloc_rows
        if r.username in selected_users
    ]

    for sa in saved_alloc_rows:
        invest_projects_set.add(sa.invest_project)

    invest_projects_set = {
        p for p in invest_projects_set if "/" not in p
    }
    if not invest_projects_set:
        invest_projects_set.add("MENA")

    return InvestDataResponse(
        auto_entries=auto_entries,
        buh_entries=buh_entries,
        manual_percent_entries=manual_percent_entries,
        manual_project_entries=manual_project_entries,
        saved_allocations=saved_allocations,
        invest_projects=sorted(invest_projects_set),
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

    db.commit()
    return {"status": "ok", "count": len(payload.allocations)}
