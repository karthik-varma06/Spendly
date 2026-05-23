from pydantic import BaseModel, Field
from datetime import date, time
from typing import Optional

class ExpenseItemIn(BaseModel):
    item_name: str
    quantity: float = 1
    unit_price: float = 0
    total_price: float = 0
    item_category: str | None = None

class ExpenseCreate(BaseModel):
    category_id: int | None = None
    vendor_name: str | None = None
    vendor_phone: str | None = None
    vendor_email: str | None = None
    vendor_address: str | None = None
    invoice_number: str | None = None
    expense_date: date | None = None
    expense_time: time | None = None
    currency: str = "INR"
    subtotal: float = 0
    cgst: float = 0
    sgst: float = 0
    igst: float = 0
    tax_amount: float = 0
    discount_amount: float = 0
    total_amount: float
    payment_method: str | None = None
    notes: str | None = None
    extraction_confidence: float | None = None
    status: str = "PENDING_REVIEW"
    is_reviewed: bool = False
    is_manual: bool = False
    items: list[ExpenseItemIn] = []

class ExpenseOut(BaseModel):
    id: str
    vendor_name: str | None = None
    total_amount: float
    category_id: int | None = None
    expense_date: date | None = None
    expense_time: time | None = None
    payment_method: str | None = None
    status: str
    is_reviewed: bool

    class Config:
        from_attributes = True
