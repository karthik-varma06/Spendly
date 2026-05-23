from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.expense import Expense
from app.models.expense_item import ExpenseItem

try:
    from app.models.income import Income
except Exception:  # pragma: no cover
    Income = None  # type: ignore


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def build_dashboard_summary(db: Session, user_id: str) -> dict[str, Any]:
    today = date.today()

    month_expense = db.query(
        func.coalesce(func.sum(Expense.total_amount), 0)
    ).filter(
        Expense.user_id == user_id,
        Expense.expense_date.isnot(None),
        func.extract("year", Expense.expense_date) == today.year,
        func.extract("month", Expense.expense_date) == today.month,
    ).scalar()

    year_expense = db.query(
        func.coalesce(func.sum(Expense.total_amount), 0)
    ).filter(
        Expense.user_id == user_id,
        Expense.expense_date.isnot(None),
        func.extract("year", Expense.expense_date) == today.year,
    ).scalar()

    income_total = 0.0
    if Income is not None:
        try:
            income_total = _as_float(
                db.query(func.coalesce(func.sum(Income.amount), 0))
                .filter(Income.user_id == user_id)
                .scalar()
            )
        except Exception:
            income_total = 0.0

    monthly_expense = _as_float(month_expense)
    yearly_expense = _as_float(year_expense)
    savings = max(income_total - yearly_expense, 0.0)

    # IMPORTANT:
    # Category breakdown must use the saved expense category only.
    # Do NOT split taxes into a separate "OTHER" category.
    category_expr = func.coalesce(Category.name, "OTHER")
    category_rows = (
        db.query(
            category_expr.label("name"),
            func.coalesce(func.sum(Expense.total_amount), 0).label("value"),
        )
        .select_from(Expense)
        .outerjoin(Category, Expense.category_id == Category.id)
        .filter(Expense.user_id == user_id)
        .group_by(category_expr)
        .order_by(desc("value"))
        .all()
    )

    merchant_expr = func.coalesce(Expense.vendor_name, "Unknown")
    merchant_rows = (
        db.query(
            merchant_expr.label("name"),
            func.coalesce(func.sum(Expense.total_amount), 0).label("value"),
        )
        .filter(Expense.user_id == user_id)
        .group_by(merchant_expr)
        .order_by(desc("value"))
        .limit(5)
        .all()
    )

    month_key = func.to_char(Expense.expense_date, "YYYY-MM")
    month_label = func.to_char(Expense.expense_date, "Mon YYYY")
    trend_rows = (
        db.query(
            month_label.label("month"),
            func.coalesce(func.sum(Expense.total_amount), 0).label("amount"),
            month_key.label("sort_key"),
        )
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
        )
        .group_by(month_key, month_label)
        .order_by(month_key)
        .all()
    )

    item_rows = (
        db.query(
            ExpenseItem.item_name.label("name"),
            func.coalesce(func.sum(ExpenseItem.total_price), 0).label("value"),
        )
        .select_from(ExpenseItem)
        .join(Expense, Expense.id == ExpenseItem.expense_id)
        .filter(Expense.user_id == user_id)
        .group_by(ExpenseItem.item_name)
        .order_by(desc("value"))
        .limit(5)
        .all()
    )

    most_expensive_month_row = (
        db.query(
            month_label.label("month"),
            func.coalesce(func.sum(Expense.total_amount), 0).label("amount"),
            month_key.label("sort_key"),
        )
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
        )
        .group_by(month_key, month_label)
        .order_by(desc("amount"))
        .first()
    )

    return {
        "monthly_expense": monthly_expense,
        "yearly_expense": yearly_expense,
        "savings": savings,
        "top_items": [{"name": r.name, "value": _as_float(r.value)} for r in item_rows],
        "top_merchants": [{"name": r.name, "value": _as_float(r.value)} for r in merchant_rows],
        "category_breakdown": [{"name": r.name, "value": _as_float(r.value)} for r in category_rows],
        "spending_trends": [{"month": r.month, "amount": _as_float(r.amount)} for r in trend_rows],
        "income_vs_expense": {"income": income_total, "expense": yearly_expense},
        "most_expensive_month": (
            {"month": most_expensive_month_row.month, "amount": _as_float(most_expensive_month_row.amount)}
            if most_expensive_month_row
            else None
        ),
    }


def build_chat_context(db: Session, user_id: str) -> dict[str, Any]:
    summary = build_dashboard_summary(db, user_id)

    month_key = func.to_char(Expense.expense_date, "YYYY-MM")
    month_label = func.to_char(Expense.expense_date, "Mon YYYY")

    monthly_rows = (
        db.query(
            month_label.label("month"),
            func.coalesce(func.sum(Expense.total_amount), 0).label("amount"),
            month_key.label("sort_key"),
        )
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
        )
        .group_by(month_key, month_label)
        .order_by(month_key)
        .all()
    )

    item_rows = (
        db.query(
            ExpenseItem.item_name.label("name"),
            func.coalesce(func.sum(ExpenseItem.total_price), 0).label("value"),
        )
        .select_from(ExpenseItem)
        .join(Expense, Expense.id == ExpenseItem.expense_id)
        .filter(Expense.user_id == user_id)
        .group_by(ExpenseItem.item_name)
        .order_by(desc("value"))
        .all()
    )

    recent_rows = (
        db.query(
            Expense.vendor_name,
            Expense.invoice_number,
            Expense.expense_date,
            Expense.total_amount,
            Category.name.label("category_name"),
        )
        .select_from(Expense)
        .outerjoin(Category, Expense.category_id == Category.id)
        .filter(Expense.user_id == user_id)
        .order_by(Expense.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "summary": summary,
        "monthly_totals": [{"month": r.month, "amount": _as_float(r.amount)} for r in monthly_rows],
        "item_totals": [{"name": r.name, "value": _as_float(r.value)} for r in item_rows],
        "recent_expenses": [
            {
                "vendor_name": r.vendor_name,
                "invoice_number": r.invoice_number,
                "expense_date": r.expense_date.isoformat() if r.expense_date else None,
                "total_amount": _as_float(r.total_amount),
                "category_name": r.category_name,
            }
            for r in recent_rows
        ],
    }