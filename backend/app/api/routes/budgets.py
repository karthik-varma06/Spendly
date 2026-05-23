from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetUpdate

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _today() -> date:
    return date.today()


def _week_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    end = d.replace(day=monthrange(d.year, d.month)[1])
    return start, end


def _normalize_period(value: str | None) -> str:
    period = (value or "monthly").strip().lower()
    if period not in {"weekly", "monthly", "custom"}:
        raise HTTPException(status_code=422, detail="Invalid budget period")
    return period


def _normalize_budget_dates(period: str, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    today = _today()
    period = _normalize_period(period)

    if period == "weekly":
        default_start, default_end = _week_bounds(today)
        return start_date or default_start, end_date or default_end

    if period == "monthly":
        default_start, default_end = _month_bounds(today)
        return start_date or default_start, end_date or default_end

    if period == "custom":
        if not end_date:
            raise HTTPException(status_code=422, detail="Custom budget needs an end_date")
        if not start_date:
            start_date = today
        if end_date < start_date:
            raise HTTPException(status_code=422, detail="end_date cannot be before start_date")
        return start_date, end_date

    raise HTTPException(status_code=422, detail="Invalid budget period")


def _get_category_by_name(db: Session, category_name: str) -> Category | None:
    name = (category_name or "OTHER").strip().upper()
    return db.scalar(select(Category).where(Category.name == name))


def _serialize_budget(db: Session, budget: Budget) -> dict:
    category = db.scalar(select(Category).where(Category.id == budget.category_id)) if budget.category_id else None
    budget_limit = float(getattr(budget, "budget_limit", 0) or 0)
    spent_amount = float(getattr(budget, "spent_amount", 0) or 0)
    progress_percent = int(round((spent_amount / budget_limit) * 100)) if budget_limit else 0

    return {
        "id": str(budget.id),
        "user_id": str(budget.user_id),
        "category_id": budget.category_id,
        "category_name": category.name if category else "ALL",
        "budget_limit": budget_limit,
        "spent_amount": spent_amount,
        "progress_percent": progress_percent,
        "period": _normalize_period(str(getattr(budget, "period", "monthly"))),
        "start_date": budget.start_date,
        "end_date": budget.end_date,
        "notify_percentage": int(getattr(budget, "notify_percentage", 80) or 80),
        "is_active": bool(getattr(budget, "is_active", True)),
        "created_at": getattr(budget, "created_at", None),
    }


@router.get("")
def list_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    budgets = (
        db.query(Budget)
        .filter(Budget.user_id == current_user.id)
        .order_by(Budget.created_at.desc())
        .all()
    )
    return [_serialize_budget(db, budget) for budget in budgets]


@router.post("")
def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = _get_category_by_name(db, payload.category_name)
    if not category:
        raise HTTPException(status_code=404, detail=f"Category '{payload.category_name}' not found")

    start_date, end_date = _normalize_budget_dates(payload.period, payload.start_date, payload.end_date)
    normalized_period = _normalize_period(payload.period)

    budget = Budget(
        id=str(uuid4()),
        user_id=str(current_user.id),
        category_id=category.id,
        budget_limit=float(payload.amount),
        spent_amount=0,
        period=normalized_period,
        start_date=start_date,
        end_date=end_date,
        notify_percentage=int(payload.threshold_percent),
        is_active=bool(payload.is_active),
    )

    try:
        db.add(budget)
        db.commit()
        db.refresh(budget)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Budget save failed because the database period constraint does not match the app. "
                "Run the provided ALTER TABLE migration for budgets_period_check."
            ),
        ) from exc

    return {"message": "Budget created", "budget": _serialize_budget(db, budget)}


@router.put("/{budget_id}")
def update_budget(
    budget_id: str,
    payload: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = db.scalar(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.user_id == current_user.id,
        )
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    if payload.category_name is not None:
        category = _get_category_by_name(db, payload.category_name)
        if not category:
            raise HTTPException(status_code=404, detail=f"Category '{payload.category_name}' not found")
        budget.category_id = category.id

    if payload.amount is not None:
        budget.budget_limit = float(payload.amount)

    if payload.period is not None:
        budget.period = _normalize_period(payload.period)

    if payload.threshold_percent is not None:
        budget.notify_percentage = int(payload.threshold_percent)

    if payload.is_active is not None:
        budget.is_active = bool(payload.is_active)

    if payload.start_date is not None:
        budget.start_date = payload.start_date
    if payload.end_date is not None:
        budget.end_date = payload.end_date

    try:
        budget.start_date, budget.end_date = _normalize_budget_dates(
            str(budget.period),
            budget.start_date,
            budget.end_date,
        )
        db.commit()
        db.refresh(budget)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Budget update failed because of a database constraint issue.") from exc

    return {"message": "Budget updated", "budget": _serialize_budget(db, budget)}


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = db.scalar(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.user_id == current_user.id,
        )
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db.delete(budget)
    db.commit()
    return {"message": "Budget deleted", "id": budget_id}