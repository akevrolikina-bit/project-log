"""API endpoint for downloading the Excel report."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.upload import Upload
from app.services.excel_report import generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["reports"])

_XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@router.get("/{upload_id}/report")
def download_report(upload_id: int, db: Session = Depends(get_db)):
    """Generate and return the Excel report for an uploaded worklog file.

    Checks are optional. While a check run is in progress the report is
    blocked so the file does not mix incomplete results.
    """

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    if upload.status == "checking":
        raise HTTPException(
            status_code=409,
            detail="Дождитесь окончания проверки, затем скачайте отчёт.",
        )

    try:
        data = generate_report(upload_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    filename = f"TimeAudit_Report_{upload_id}.xlsx"

    return Response(
        content=data,
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
