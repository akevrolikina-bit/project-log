from datetime import datetime

from pydantic import BaseModel


class WorklogEntry(BaseModel):
    """Single worklog row parsed from a Jira time-sheet export."""

    project: str
    task_type: str
    key: str
    title: str
    started: datetime
    username: str
    hours: float
    comment: str

    model_config = {"from_attributes": True}
