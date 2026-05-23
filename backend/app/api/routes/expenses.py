from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.category import Category
from app.models.expense import Expense
from app.models.expense_item import ExpenseItem
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseOut
from app.services.notifications import (
    create_notification,
    send_budget_notifications_and_emails,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/expenses", tags=["expenses"])


def _resolve_category_id(db: Session, category_id: int | None) -> int | None:
    if category_id:
        return category_id
    default_category = db.scalar(select(Category).where(Category.name == "OTHER"))
    return default_category.id if default_category else None


@router.post("")
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        expense = Expense(
            id=str(uuid4()),
            user_id=str(current_user.id),
            category_id=_resolve_category_id(db, payload.category_id),
            vendor_name=payload.vendor_name,
            vendor_phone=payload.vendor_phone,
            vendor_email=payload.vendor_email,
            vendor_address=payload.vendor_address,
            invoice_number=payload.invoice_number,
            expense_date=payload.expense_date,
            expense_time=payload.expense_time,
            currency=payload.currency or "INR",
            subtotal=payload.subtotal or 0,
            cgst=payload.cgst or 0,
            sgst=payload.sgst or 0,
            igst=payload.igst or 0,
            tax_amount=payload.tax_amount or (payload.cgst or 0) + (payload.sgst or 0) + (payload.igst or 0),
            discount_amount=payload.discount_amount or 0,
            total_amount=payload.total_amount,
            payment_method=payload.payment_method,
            notes=payload.notes,
            extraction_confidence=payload.extraction_confidence,
            status=payload.status or "PENDING_REVIEW",
            is_reviewed=payload.is_reviewed,
            is_manual=payload.is_manual,
        )
        db.add(expense)
        db.flush()

        for item in payload.items or []:
            db.add(
                ExpenseItem(
                    id=str(uuid4()),
                    expense_id=expense.id,
                    item_name=item.item_name,
                    quantity=item.quantity or 1,
                    unit_price=item.unit_price or 0,
                    total_price=item.total_price or 0,
                    item_category=item.item_category,
                )
            )

        db.commit()
        db.refresh(expense)

    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create expense: {exc}")

    expense_id = str(expense.id)

    try:
        create_notification(
            db,
            str(current_user.id),
            "Expense added",
            f"₹{float(expense.total_amount or 0):.2f} saved for {expense.vendor_name or 'your expense'}",
            "EXPENSE_ADDED",
            action_url="/dashboard",
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("[Expenses] notification insert failed: %s", exc)

    try:
        send_budget_notifications_and_emails(db, str(current_user.id), periodic_check=False)
    except Exception as exc:
        logger.exception("[Expenses] budget sync failed: %s", exc)

    return {
        "message": "Expense saved successfully",
        "expense_id": expense_id,
    }


@router.get("")
def list_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.scalars(
        select(Expense)
        .where(Expense.user_id == str(current_user.id))
        .order_by(Expense.created_at.desc())
    ).all()

    return [
        {
            "id": e.id,
            "vendor_name": e.vendor_name,
            "total_amount": float(e.total_amount or 0),
            "category_id": e.category_id,
            "expense_date": e.expense_date,
            "expense_time": e.expense_time,
            "payment_method": e.payment_method,
            "status": e.status,
            "is_reviewed": e.is_reviewed,
        }
        for e in items
    ]
