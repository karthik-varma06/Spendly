from pydantic import BaseModel, ConfigDict, Field


class ExpenseItemDraft(BaseModel):
    item_name: str = ""
    quantity: float = 1
    unit_price: float = 0
    total_price: float = 0
    item_category: str | None = None


class ExpenseDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    vendor_name: str | None = None
    invoice_number: str | None = None
    date: str | None = None
    time: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    items: list[ExpenseItemDraft] = Field(default_factory=list)

    subtotal: float = 0
    cgst: float = 0
    sgst: float = 0
    igst: float = 0
    discount: float = 0
    total_amount: float = 0

    payment_method: str | None = None
    category: str = "OTHER"

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_error: str | None = None
    extraction_mode: str | None = None


class SaveReviewedExpenseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    uploaded_file_id: str
    draft: ExpenseDraft