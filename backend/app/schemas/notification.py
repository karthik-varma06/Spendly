from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    message: str
    type: str
    action_url: str | None = None
    is_read: bool
    created_at: datetime | None = None


class MarkReadRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)