from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncomeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    source: str | None = None
    source_name: str | None = None
    title: str | None = None
    amount: float = Field(gt=0)
    income_date: date | None = None
    notes: str | None = None

    @field_validator("source", "source_name", "title", mode="before")
    @classmethod
    def _empty_to_none(cls, value):
        if value == "":
            return None
        return value


class IncomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str | None = None
    amount: float
    income_date: date | None = None
    notes: str | None = None