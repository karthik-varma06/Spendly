from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BudgetPeriod = Literal["weekly", "monthly", "custom"]


class BudgetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_name: str = Field(default="OTHER", min_length=2, max_length=64)
    amount: float = Field(gt=0)
    period: BudgetPeriod = "monthly"
    threshold_percent: int = Field(default=80, ge=1, le=100)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True

    @field_validator("category_name")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        return (v or "OTHER").strip().upper()

    @model_validator(mode="after")
    def validate_dates(self):
        if self.period == "custom" and not self.end_date:
            raise ValueError("Custom budget needs an end_date")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class BudgetUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_name: str | None = None
    amount: float | None = Field(default=None, gt=0)
    period: BudgetPeriod | None = None
    threshold_percent: int | None = Field(default=None, ge=1, le=100)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None

    @field_validator("category_name")
    @classmethod
    def normalize_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_dates(self):
        if self.period == "custom" and self.end_date is None:
            raise ValueError("Custom budget needs an end_date")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self