from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    row_count: int
    status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}


class UploadListItem(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    row_count: int
    status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}
