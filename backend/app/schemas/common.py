from pydantic import BaseModel
from datetime import datetime, date
from typing import Any

class IdName(BaseModel):
    id: int | str
    name: str

class MessageResponse(BaseModel):
    message: str

class UploadedFileOut(BaseModel):
    id: str
    original_filename: str
    file_type: str
    extraction_status: str
    extracted_text: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardSummary(BaseModel):
    monthly_expense: float
    yearly_expense: float
    income_vs_expense: dict[str, float]
    category_breakdown: list[dict[str, Any]]
    top_merchants: list[dict[str, Any]]
    most_expensive_month: dict[str, Any] | None
    spending_trends: list[dict[str, Any]]
    top_items: list[dict[str, Any]]
    savings: float
