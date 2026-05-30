from pydantic import BaseModel


class CheckResultResponse(BaseModel):
    id: int
    upload_id: int
    username: str
    check_type: str
    severity: str
    message: str
    details: str

    model_config = {"from_attributes": True}


class CheckSummaryItem(BaseModel):
    """Per-employee summary returned by the results endpoint."""

    username: str
    total_hours: float
    expected_hours: float | None
    status: str
    issues: list[CheckResultResponse]
