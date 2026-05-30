from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.upload import Upload
from app.models.worklog import WorklogEntry as WorklogEntryModel
from app.schemas.upload import UploadListItem, UploadResponse
from app.schemas.worklog import WorklogEntry as WorklogEntrySchema
from app.services.excel_parser import parse_worklog_file

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def create_upload(file: UploadFile, db: Session = Depends(get_db)):
    """Accept a multipart file upload, parse worklogs, save to DB."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    contents = await file.read()

    try:
        entries = parse_worklog_file(contents)
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}")

    upload = Upload(filename=file.filename, row_count=len(entries), status="parsed")
    db.add(upload)
    db.flush()

    for entry in entries:
        db.add(
            WorklogEntryModel(
                upload_id=upload.id,
                project=entry.project,
                task_type=entry.task_type,
                key=entry.key,
                title=entry.title,
                started=entry.started,
                username=entry.username,
                hours=entry.hours,
                comment=entry.comment,
            )
        )

    db.commit()
    db.refresh(upload)
    return upload


@router.get("", response_model=list[UploadListItem])
def list_uploads(db: Session = Depends(get_db)):
    """Return all uploads."""
    return db.query(Upload).order_by(Upload.uploaded_at.desc()).all()


@router.get("/{upload_id}/worklogs", response_model=list[WorklogEntrySchema])
def get_worklogs(upload_id: int, username: str | None = None, db: Session = Depends(get_db)):
    """Return worklog entries for an upload, optionally filtered by username."""
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    query = db.query(WorklogEntryModel).filter(WorklogEntryModel.upload_id == upload_id)
    if username:
        query = query.filter(WorklogEntryModel.username == username)

    return query.order_by(WorklogEntryModel.started).all()
