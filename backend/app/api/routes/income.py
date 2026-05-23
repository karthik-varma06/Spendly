from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.income import IncomeCreate
from app.services.notifications import create_notification, send_budget_notifications_and_emails

try:
    from app.models.income import Income
except Exception:  # pragma: no cover
    Income = None  # type: ignore

router = APIRouter(prefix="/income", tags=["income"])


def _coerce_income_date(value: date | None) -> date:
    return value or date.today()


def _income_source(payload: IncomeCreate) -> str:
    source = (
        getattr(payload, "source", None)
        or getattr(payload, "source_name", None)
        or getattr(payload, "title", None)
        or "Income"
    )
    source = str(source).strip()
    return source or "Income"


@router.get("")
def list_income(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if Income is None:
        raise HTTPException(status_code=503, detail="Income model not available")

    rows = db.scalars(
        select(Income)
        .where(Income.user_id == str(current_user.id))
        .order_by(desc(Income.income_date), desc(Income.created_at))
    ).all()

    return [
        {
            "id": r.id,
            "source": getattr(r, "source", None),
            "amount": float(getattr(r, "amount", 0) or 0),
            "income_date": getattr(r, "income_date", None),
            "notes": getattr(r, "notes", None),
        }
        for r in rows
    ]


@router.post("")
def create_income(
    payload: IncomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if Income is None:
        raise HTTPException(status_code=503, detail="Income model not available")

    income_date = _coerce_income_date(payload.income_date)
    source = _income_source(payload)

    try:
        row = Income(
            id=str(uuid4()),
            user_id=str(current_user.id),
            source=source,
            amount=float(payload.amount),
            income_date=income_date,
            notes=payload.notes,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create income: {exc}",
        )

    try:
        create_notification(
            db,
            str(current_user.id),
            "Savings added",
            f"₹{float(row.amount or 0):.2f} added to your savings/income.",
            "INCOME_ADDED",
            action_url="/dashboard",
        )
        db.commit()
    except Exception:
        db.rollback()

    try:
        send_budget_notifications_and_emails(db, str(current_user.id), periodic_check=False)
    except Exception:
        # Do not fail income creation if notification sync has a problem.
        pass

    return {
        "message": "Income created",
        "id": row.id,
        "source": row.source,
        "income_date": row.income_date,
    }