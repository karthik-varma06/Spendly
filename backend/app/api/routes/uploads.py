from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.models.category import Category
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.schemas.upload import SaveReviewedExpenseRequest
from app.services.llm import extract_structured_from_image_bytes, extract_structured_from_text
from app.services.notifications import send_budget_notifications_and_emails
from app.services.ocr import (
    TesseractUnavailableError,
    extract_text_from_csv,
    extract_text_from_image,
    extract_text_from_pdf,
)

logger = logging.getLogger("ai_finance_tracker.uploads")
router = APIRouter(prefix="/uploads", tags=["uploads"])
settings = get_settings()

CATEGORY_OPTIONS = [
    "FOOD",
    "TRAVEL",
    "SHOPPING",
    "ELECTRONICS",
    "HEALTH",
    "UTILITIES",
    "ENTERTAINMENT",
    "SUBSCRIPTIONS",
    "EDUCATION",
    "TRANSPORT",
    "OTHER",
]

FOOD_HINTS = {
    "BIRYANI", "MEAL", "LUNCH", "DINNER", "BREAKFAST", "SNACK", "CAFE", "RESTAURANT",
    "MESS", "FOOD", "PIZZA", "BURGER", "SANDWICH", "SWIGGY", "ZOMATO", "TIFFIN",
    "THALI", "CHICKEN", "MUTTON", "RICE", "CURRY"
}
TRAVEL_HINTS = {
    "CAB", "TAXI", "UBER", "OLA", "BUS", "TRAIN", "FLIGHT", "AIRPORT", "METRO", "AUTO"
}
ELECTRONICS_HINTS = {
    "MOBILE", "PHONE", "LAPTOP", "TV", "HEADPHONE", "EARBUD", "CHARGER", "MONITOR",
    "KEYBOARD", "MOUSE", "ELECTRONIC"
}
SHOPPING_HINTS = {"MALL", "STORE", "SHOP", "BOUTIQUE", "CLOTH", "SHIRT", "PANT", "FASHION"}
HEALTH_HINTS = {"HOSPITAL", "CLINIC", "PHARMACY", "MEDICINE", "TABLET", "DOCTOR"}
UTILITIES_HINTS = {"ELECTRICITY", "WATER", "GAS", "INTERNET", "BROADBAND", "RECHARGE"}
SUBS_HINTS = {"NETFLIX", "AMAZON PRIME", "YOUTUBE PREMIUM", "SPOTIFY", "SUBSCRIPTION"}


def detect_type(filename: str, content_type: str | None) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        return "image"
    if content_type:
        if "csv" in content_type:
            return "csv"
        if "pdf" in content_type:
            return "pdf"
        if "image" in content_type:
            return "image"
    return "other"


def _normalize_category(category: str | None) -> str:
    if not category:
        return "OTHER"
    upper = category.strip().upper()
    return upper if upper in CATEGORY_OPTIONS else "OTHER"


def _infer_category_from_text(text: str | None) -> str:
    if not text:
        return "OTHER"
    up = text.upper()

    def has_any(words: set[str]) -> bool:
        return any(word in up for word in words)

    if has_any(FOOD_HINTS):
        return "FOOD"
    if has_any(TRAVEL_HINTS):
        return "TRAVEL"
    if has_any(ELECTRONICS_HINTS):
        return "ELECTRONICS"
    if has_any(SHOPPING_HINTS):
        return "SHOPPING"
    if has_any(HEALTH_HINTS):
        return "HEALTH"
    if has_any(UTILITIES_HINTS):
        return "UTILITIES"
    if has_any(SUBS_HINTS):
        return "SUBSCRIPTIONS"
    return "OTHER"


def _infer_category_from_draft(draft: dict, extracted_text: str | None) -> str:
    explicit = _normalize_category(draft.get("category"))
    if explicit != "OTHER":
        return explicit

    items = draft.get("items") or []
    item_categories = []
    item_names = []

    for item in items:
        if not isinstance(item, dict):
            continue
        item_cat = _normalize_category(item.get("item_category"))
        if item_cat != "OTHER":
            item_categories.append(item_cat)
        name = str(item.get("item_name") or "").strip()
        if name:
            item_names.append(name)

    if item_categories:
        return Counter(item_categories).most_common(1)[0][0]

    combined = " ".join(
        [
            str(draft.get("vendor_name") or ""),
            str(draft.get("invoice_number") or ""),
            " ".join(item_names),
            extracted_text or "",
        ]
    )
    return _infer_category_from_text(combined)


def _parse_date(value: str | None):
    if not value:
        return None

    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            pass

    return None


def _parse_time(value: str | None):
    if not value:
        return None

    value = value.strip().split()[0]
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except Exception:
            pass

    return None


def _to_float(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _ensure_category_id(db: Session, category_name: str) -> int:
    category_name = _normalize_category(category_name)
    existing = db.scalar(select(Category).where(Category.name == category_name))
    if existing:
        return int(existing.id)

    category_id = db.execute(
        text("INSERT INTO categories (name, icon, color) VALUES (:name, NULL, NULL) RETURNING id"),
        {"name": category_name},
    ).scalar_one()
    return int(category_id)


@router.post("/analyze")
async def analyze_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4()}_{file.filename}"
    file_path = upload_dir / stored_name
    content = await file.read()
    file_path.write_bytes(content)

    file_type = detect_type(file.filename, file.content_type)

    extracted_text = ""
    structured: dict
    extraction_mode = "unknown"
    ocr_engine = None
    ocr_error = None

    print(f"\n[UPLOAD] File: {file.filename} | Type: {file_type} | Size: {len(content)} bytes")

    try:
        if file_type == "image":
            print("[UPLOAD] Trying direct multimodal LLM extraction first...")
            structured = extract_structured_from_image_bytes(content, file.content_type)
            extraction_mode = "vision_llm"
        elif file_type == "pdf":
            extracted_text = extract_text_from_pdf(str(file_path))
            print("\n================ OCR/TEXT EXTRACTED FROM PDF ================")
            print(extracted_text or "[empty]")
            print("============================================================\n")
            structured = extract_structured_from_text(extracted_text or file.filename)
            extraction_mode = "text_llm_pdf"
        elif file_type == "csv":
            extracted_text = extract_text_from_csv(str(file_path))
            print("\n================ CSV TEXT EXTRACTED ================")
            print(extracted_text or "[empty]")
            print("=====================================================\n")
            structured = extract_structured_from_text(extracted_text or file.filename)
            extraction_mode = "text_llm_csv"
        else:
            extracted_text = file.filename
            structured = extract_structured_from_text(extracted_text)
            extraction_mode = "text_llm_other"

    except Exception:
        logger.warning("[UPLOAD] Direct LLM extraction failed, falling back to OCR/text")

        if file_type == "image":
            try:
                print("[UPLOAD] Falling back to OCR + LLM...")
                extracted_text = extract_text_from_image(str(file_path))
                ocr_engine = "TESSERACT"
                print("\n================ OCR EXTRACTED TEXT ================")
                print(extracted_text or "[empty]")
                print("====================================================\n")
                structured = extract_structured_from_text(extracted_text or file.filename or "")
                extraction_mode = "ocr_fallback"
            except TesseractUnavailableError as exc:
                ocr_error = str(exc)
                extracted_text = ""
                structured = extract_structured_from_text(file.filename or "")
                extraction_mode = "fallback_text"
            except Exception as second_error:
                ocr_error = str(second_error)
                extracted_text = ""
                structured = extract_structured_from_text(file.filename or "")
                extraction_mode = "fallback_text"
        else:
            structured = extract_structured_from_text(extracted_text or file.filename or "")
            extraction_mode = "fallback_text"

    structured["category"] = _normalize_category(structured.get("category"))
    structured["extraction_mode"] = extraction_mode

    print("\n================ LLM STRUCTURED RESPONSE ================")
    print(json.dumps(structured, indent=2))
    print("=========================================================\n")

    uploaded = UploadedFile(
        id=str(uuid4()),
        user_id=str(current_user.id),
        original_filename=file.filename,
        stored_filename=stored_name,
        file_type=file_type,
        file_size=len(content),
        mime_type=file.content_type,
        extracted_text=extracted_text if extracted_text else None,
        extraction_status="READY_FOR_REVIEW",
        upload_source="manual_upload",
        ocr_engine=ocr_engine,
        llm_model=(
            f"openrouter:{settings.openrouter_vision_model}"
            if settings.openrouter_api_key.strip()
            else None
        ),
    )

    db.add(uploaded)
    db.commit()
    db.refresh(uploaded)

    return {
        "uploaded_file_id": uploaded.id,
        "file_type": file_type,
        "structured_data": structured,
        "extraction_mode": extraction_mode,
        "ocr_engine": uploaded.ocr_engine or "NONE",
        "llm_model": uploaded.llm_model or "NONE",
        "ocr_error": ocr_error,
        "message": "Analysis complete. Review and save to store in the database.",
    }


@router.post("/save")
def save_reviewed_expense(
    payload: SaveReviewedExpenseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uploaded = db.scalar(
        select(UploadedFile).where(
            UploadedFile.id == payload.uploaded_file_id,
            UploadedFile.user_id == str(current_user.id),
        )
    )
    if not uploaded:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    draft = payload.draft.model_dump()
    inferred_category = _infer_category_from_draft(draft, uploaded.extracted_text)
    category_id = _ensure_category_id(db, inferred_category)

    def _to_date(value):
        if not value:
            return None
        if isinstance(value, str):
            return _parse_date(value)
        return value

    def _to_time(value):
        if not value:
            return None
        if isinstance(value, str):
            return _parse_time(value)
        return value

    try:
        expense_id = str(uuid4())

        db.execute(
            text(
                """
                INSERT INTO expenses (
                    id, user_id, category_id, uploaded_file_id,
                    vendor_name, vendor_phone, vendor_email, vendor_address,
                    invoice_number, expense_date, expense_time, currency,
                    subtotal, cgst, sgst, igst, tax_amount, discount_amount,
                    total_amount, payment_method, notes, extraction_confidence,
                    status, is_reviewed, is_manual
                )
                VALUES (
                    :id, :user_id, :category_id, :uploaded_file_id,
                    :vendor_name, :vendor_phone, :vendor_email, :vendor_address,
                    :invoice_number, :expense_date, :expense_time, :currency,
                    :subtotal, :cgst, :sgst, :igst, :tax_amount, :discount_amount,
                    :total_amount, :payment_method, :notes, :extraction_confidence,
                    :status, :is_reviewed, :is_manual
                )
                """
            ),
            {
                "id": expense_id,
                "user_id": str(current_user.id),
                "category_id": category_id,
                "uploaded_file_id": uploaded.id,
                "vendor_name": draft.get("vendor_name") or None,
                "vendor_phone": draft.get("phone") or None,
                "vendor_email": draft.get("email") or None,
                "vendor_address": draft.get("address") or None,
                "invoice_number": draft.get("invoice_number") or None,
                "expense_date": _to_date(draft.get("date")),
                "expense_time": _to_time(draft.get("time")),
                "currency": "INR",
                "subtotal": _to_float(draft.get("subtotal")),
                "cgst": _to_float(draft.get("cgst")),
                "sgst": _to_float(draft.get("sgst")),
                "igst": _to_float(draft.get("igst")),
                "tax_amount": _to_float(draft.get("cgst")) + _to_float(draft.get("sgst")) + _to_float(draft.get("igst")),
                "discount_amount": _to_float(draft.get("discount")),
                "total_amount": _to_float(draft.get("total_amount")),
                "payment_method": draft.get("payment_method") or None,
                "notes": json.dumps(
                    {
                        "extraction_mode": draft.get("extraction_mode"),
                        "llm_model": draft.get("llm_model"),
                        "llm_provider": draft.get("llm_provider"),
                        "inferred_category": inferred_category,
                    }
                ),
                "extraction_confidence": 1.0,
                "status": "COMPLETED",
                "is_reviewed": True,
                "is_manual": False,
            },
        )

        for item in draft.get("items", []) or []:
            quantity = _to_float(item.get("quantity"), 1)
            unit_price = _to_float(item.get("unit_price"))
            total_price = _to_float(item.get("total_price"))
            if total_price == 0 and quantity and unit_price:
                total_price = quantity * unit_price

            db.execute(
                text(
                    """
                    INSERT INTO expense_items (
                        id, expense_id, item_name, quantity, unit_price, total_price, item_category
                    )
                    VALUES (
                        :id, :expense_id, :item_name, :quantity, :unit_price, :total_price, :item_category
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "expense_id": expense_id,
                    "item_name": item.get("item_name") or "Unknown",
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "item_category": _normalize_category(item.get("item_category")) if item.get("item_category") else None,
                },
            )

        db.execute(
            text(
                """
                UPDATE uploaded_files
                SET extraction_status = 'SAVED',
                    llm_model = :llm_model
                WHERE id = :uploaded_file_id
                """
            ),
            {
                "llm_model": (
                    f"openrouter:{settings.openrouter_vision_model}"
                    if settings.openrouter_api_key.strip()
                    else uploaded.llm_model
                ),
                "uploaded_file_id": uploaded.id,
            },
        )

        db.commit()
        send_budget_notifications_and_emails(db, str(current_user.id))

        return {
            "message": "Expense saved successfully",
            "expense_id": expense_id,
            "uploaded_file_id": uploaded.id,
            "category_used": inferred_category,
        }

    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save expense: {exc}")