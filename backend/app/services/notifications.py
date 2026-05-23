from __future__ import annotations

import html
import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from openrouter import OpenRouter
from sqlalchemy import insert, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.budget import Budget
from app.models.category import Category
from app.models.email_log import EmailLog
from app.models.expense import Expense
from app.models.expense_item import ExpenseItem
from app.models.notification import Notification
from app.models.user import User
from app.models.user_setting import UserSetting
from app.services.analytics import build_dashboard_summary
from app.services.emailer import send_email

logger = logging.getLogger("ai_finance_tracker.notifications")
settings = get_settings()


@dataclass
class BudgetInsight:
    budget_id: str
    category_name: str
    period: str
    budget_limit: float
    spent_amount: float
    threshold_percent: int
    progress_percent: int
    crossed: bool
    warning: bool
    start_date: date
    end_date: date
    remaining_amount: float


def _today() -> date:
    return date.today()


def _month_end(d: date) -> date:
    if d.month == 12:
        return date(d.year, 12, 31)
    return date(d.year, d.month + 1, 1) - timedelta(days=1)


def _week_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _period_bounds(budget: Budget) -> tuple[date, date]:
    today = _today()
    period = str(getattr(budget, "period", "monthly")).lower()

    if period == "weekly":
        start, end = _week_bounds(today)
        if budget.start_date:
            start = budget.start_date
        if budget.end_date:
            end = budget.end_date
        return start, end

    if period == "monthly":
        start = today.replace(day=1)
        end = _month_end(today)
        if budget.start_date:
            start = budget.start_date
        if budget.end_date:
            end = budget.end_date
        return start, end

    start = budget.start_date or today
    end = budget.end_date or today
    return start, end


def _budget_category_name(db: Session, budget: Budget) -> str:
    if not budget.category_id:
        return "ALL"
    category = db.scalar(select(Category).where(Category.id == budget.category_id))
    return category.name if category else "ALL"


def _budget_spent(db: Session, user_id: str, budget: Budget, start: date, end: date) -> float:
    query = db.query(func.coalesce(func.sum(Expense.total_amount), 0)).filter(
        Expense.user_id == user_id,
        Expense.expense_date.isnot(None),
        Expense.expense_date >= start,
        Expense.expense_date <= end,
    )
    if budget.category_id:
        query = query.filter(Expense.category_id == budget.category_id)
    return float(query.scalar() or 0)


def _budget_limit(budget: Budget) -> float:
    for attr in (
        "budget_limit",
        "limit_amount",
        "amount",
        "target_amount",
        "allocated_amount",
        "monthly_limit",
    ):
        value = getattr(budget, attr, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 0.0


def _budget_threshold_percent(budget: Budget) -> int:
    for attr in (
        "threshold_percent",
        "warning_threshold_percent",
        "alert_threshold_percent",
        "notify_percentage",
    ):
        value = getattr(budget, attr, None)
        if value is not None:
            try:
                return max(1, min(100, int(value)))
            except (TypeError, ValueError):
                pass
    return 80


def _budget_is_active(budget: Budget) -> bool:
    for attr in ("is_active", "active"):
        value = getattr(budget, attr, None)
        if value is not None:
            return bool(value)
    status = getattr(budget, "status", None)
    if status is None:
        return True
    return str(status).lower() not in {"inactive", "disabled", "archived", "deleted"}


def build_budget_insights(db: Session, user_id: str) -> list[BudgetInsight]:
    budgets = db.query(Budget).filter(Budget.user_id == user_id).all()
    insights: list[BudgetInsight] = []

    for budget in budgets:
        if not _budget_is_active(budget):
            continue

        start_date, end_date = _period_bounds(budget)
        budget_limit = _budget_limit(budget)
        spent_amount = _budget_spent(db, user_id, budget, start_date, end_date)
        threshold_percent = _budget_threshold_percent(budget)

        if budget_limit > 0:
            progress_percent = int(round((spent_amount / budget_limit) * 100))
            remaining_amount = budget_limit - spent_amount
            crossed = spent_amount >= budget_limit
            warning = (not crossed) and progress_percent >= threshold_percent
        else:
            progress_percent = 0
            remaining_amount = 0.0
            crossed = False
            warning = False

        insights.append(
            BudgetInsight(
                budget_id=str(budget.id),
                category_name=_budget_category_name(db, budget),
                period=str(getattr(budget, "period", "monthly")).lower(),
                budget_limit=budget_limit,
                spent_amount=spent_amount,
                threshold_percent=threshold_percent,
                progress_percent=progress_percent,
                crossed=crossed,
                warning=warning,
                start_date=start_date,
                end_date=end_date,
                remaining_amount=remaining_amount,
            )
        )

    insights.sort(key=lambda x: (x.crossed, x.warning, x.progress_percent), reverse=True)
    return insights


def _user_summary_enabled(db: Session, user_id: str, kind: str) -> bool:
    setting = db.scalar(select(UserSetting).where(UserSetting.user_id == user_id))
    if not setting:
        return True

    weekly = bool(getattr(setting, "weekly_email_enabled", getattr(setting, "weekly_summary_enabled", True)))
    monthly = bool(getattr(setting, "monthly_email_enabled", getattr(setting, "monthly_summary_enabled", True)))
    alerts = bool(getattr(setting, "budget_alerts_enabled", getattr(setting, "email_summary_enabled", True)))

    if kind == "weekly":
        return weekly and alerts
    if kind == "monthly":
        return monthly and alerts
    return alerts


def _email_log_exists(db: Session, user_id: str, email_type: str) -> bool:
    row = db.scalar(
        select(EmailLog).where(
            EmailLog.user_id == user_id,
            EmailLog.email_type == email_type,
            EmailLog.status == "SENT",
        )
    )
    return row is not None


def _notification_exists(
    db: Session,
    user_id: str,
    type_: str,
    title: str,
    message: str,
    action_url: str | None = None,
) -> bool:
    stmt = select(Notification).where(
        Notification.user_id == user_id,
        Notification.type == type_,
        Notification.title == title,
        Notification.message == message,
        Notification.is_read.is_(False),
    )
    if action_url is None:
        stmt = stmt.where(Notification.action_url.is_(None))
    else:
        stmt = stmt.where(Notification.action_url == action_url)
    row = db.scalar(stmt)
    return row is not None


def create_notification(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    type_: str,
    action_url: str | None = None,
) -> None:
    if _notification_exists(db, user_id, type_, title, message, action_url):
        return

    db.execute(
        insert(Notification).values(
            id=str(uuid4()),
            user_id=user_id,
            title=title,
            message=message,
            type=type_,
            action_url=action_url,
            is_read=False,
        )
    )


def _fmt_money(value: Any) -> str:
    try:
        return f"₹{float(value or 0):,.2f}"
    except Exception:
        return "₹0.00"


def _fallback_summary_text(name: str, insight: BudgetInsight, context: dict[str, Any]) -> str:
    status = "Budget crossed." if insight.crossed else "Budget warning." if insight.warning else "Within budget."
    current_week = _fmt_money(context.get("current_week_expense", 0))
    current_month = _fmt_money(context.get("current_month_expense", 0))
    savings = _fmt_money(context.get("savings", 0))
    vendors = ", ".join(x["name"] for x in context.get("top_vendors", [])[:3]) or "No vendors found"
    items = ", ".join(x["name"] for x in context.get("top_items", [])[:3]) or "No items found"
    categories = ", ".join(x["name"] for x in context.get("top_categories", [])[:3]) or "No categories found"
    most_day = context.get("most_expensive_day") or {}
    day_text = (
        f"{most_day.get('day')} ({_fmt_money(most_day.get('value', 0))})"
        if most_day.get("day")
        else "Not available"
    )

    tips = []
    if insight.crossed:
        tips.append("Cut non-essential spending in this category for the rest of the period.")
        tips.append("Choose lower-cost alternatives and postpone large purchases.")
    elif insight.warning:
        tips.append("Slow down spending for the rest of the week to stay under the limit.")
        tips.append("Keep today's purchases small and focus on essentials.")
    else:
        tips.append("You are on track. Keep the same spending discipline.")
        tips.append("Watch the highest-cost vendors before making the next purchase.")

    return (
        f"{status}\n"
        f"Budget: {_fmt_money(insight.budget_limit)} | Spent: {_fmt_money(insight.spent_amount)} | Remaining/Over: {_fmt_money(insight.remaining_amount)}.\n"
        f"This week: {current_week} | This month: {current_month} | Savings: {savings}.\n"
        f"Most expensive day: {day_text}.\n"
        f"Top categories: {categories}.\n"
        f"Top vendors: {vendors}.\n"
        f"Top items: {items}.\n"
        f"Suggestions: {' '.join(tips)}"
    )


def _sanitize_ai_summary(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    cleaned = cleaned.replace("$", "₹")
    cleaned = re.sub(r"\bUSD\b", "₹", cleaned, flags=re.I)
    cleaned = re.sub(r"(?im)^\s*subject\s*:\s*.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(hi|hello|dear)\b.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(warm regards|best regards|regards|thanks|thank you)\b.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*here is your summary\b.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*summary\s*:\s*$", "", cleaned)

    lines: list[str] = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"(?i)^(subject|hi|hello|dear|warm regards|best regards|regards|thanks|thank you|summary|here is your summary)\b", line):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _build_context_for_budget(db: Session, user_id: str, budget: Budget, start: date, end: date) -> dict[str, Any]:
    q = (
        db.query(
            Expense.vendor_name,
            Expense.expense_date,
            Expense.total_amount,
            ExpenseItem.item_name,
            ExpenseItem.total_price,
            Category.name.label("category_name"),
        )
        .select_from(Expense)
        .outerjoin(Category, Expense.category_id == Category.id)
        .outerjoin(ExpenseItem, ExpenseItem.expense_id == Expense.id)
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
    )
    if budget.category_id:
        q = q.filter(Expense.category_id == budget.category_id)

    rows = q.all()

    category_totals: dict[str, float] = defaultdict(float)
    vendor_totals: dict[str, float] = defaultdict(float)
    item_totals: dict[str, float] = defaultdict(float)
    day_totals: dict[str, float] = defaultdict(float)

    for r in rows:
        amount = float(r.total_amount or 0)
        category = str(r.category_name or "OTHER")
        vendor = str(r.vendor_name or "Unknown")
        day = r.expense_date.isoformat() if r.expense_date else None
        category_totals[category] += amount
        vendor_totals[vendor] += amount
        if day:
            day_totals[day] += amount
        if r.item_name:
            item_totals[str(r.item_name)] += float(r.total_price or 0)

    top_categories = [{"name": k, "value": v} for k, v in sorted(category_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]]
    top_vendors = [{"name": k, "value": v} for k, v in sorted(vendor_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]]
    top_items = [{"name": k, "value": v} for k, v in sorted(item_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]]
    top_days = [{"day": k, "value": v} for k, v in sorted(day_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]]
    most_expensive_day = top_days[0] if top_days else None

    dashboard = build_dashboard_summary(db, user_id)
    dashboard_map = dashboard if isinstance(dashboard, dict) else {}

    current_week_start, current_week_end = _week_bounds(_today())
    current_month_start = _today().replace(day=1)
    current_month_end = _month_end(_today())

    current_week_expense = float(
        db.query(func.coalesce(func.sum(Expense.total_amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
            Expense.expense_date >= current_week_start,
            Expense.expense_date <= current_week_end,
        )
        .scalar()
        or 0
    )
    current_month_expense = float(
        db.query(func.coalesce(func.sum(Expense.total_amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
            Expense.expense_date >= current_month_start,
            Expense.expense_date <= current_month_end,
        )
        .scalar()
        or 0
    )

    period_spent = float(
        db.query(func.coalesce(func.sum(Expense.total_amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date.isnot(None),
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .scalar()
        or 0
    )

    return {
        "budget_period_start": start.isoformat(),
        "budget_period_end": end.isoformat(),
        "budget_period_spend": period_spent,
        "current_week_expense": float(dashboard_map.get("weekly_expense", current_week_expense) or current_week_expense),
        "current_month_expense": float(dashboard_map.get("monthly_expense", current_month_expense) or current_month_expense),
        "savings": float(dashboard_map.get("savings", 0) or 0),
        "top_categories": top_categories,
        "top_vendors": top_vendors,
        "top_items": top_items,
        "top_days": top_days,
        "most_expensive_day": most_expensive_day,
        "dashboard": dashboard,
    }


def _budget_subject_prefix(insight: BudgetInsight) -> str:
    if insight.crossed:
        return "Budget exceeded"
    if insight.warning:
        return "Budget warning"
    return "Budget summary"


def _budget_state_key(insight: BudgetInsight) -> str:
    return (
        f"{insight.budget_id}:"
        f"{insight.start_date.isoformat()}:"
        f"{insight.end_date.isoformat()}:"
        f"{round(float(insight.spent_amount or 0), 2)}:"
        f"{int(bool(insight.crossed))}:"
        f"{int(bool(insight.warning))}"
    )


def _safe_email_type(prefix: str, key: str) -> str:
    raw = f"{prefix}:{key}"
    if len(raw) <= 50:
        return raw
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}:{digest}"


def _build_ai_email_summary(user: User, insight: BudgetInsight, context: dict[str, Any]) -> str:
    if not settings.openrouter_api_key.strip():
        return _fallback_summary_text(user.full_name, insight, context)

    prompt = f"""
Write a short professional budget email summary in plain text only.
Do not use greeting lines like "Here is your summary".
Do not add a subject line.
Do not use markdown or bullets.
Do not mention the user's name.
Use INR/₹ only.
Keep it concise: 5 to 7 lines.
Include:
- category name
- total spent in this category for the budget period
- budget limit
- remaining or over amount
- top merchants or top items if available
- most expensive day if available
- one short suggestion

Use this exact context:
Budget category: {insight.category_name}
Budget period: {insight.period}
Budget limit: {_fmt_money(insight.budget_limit)}
Spent amount: {_fmt_money(insight.spent_amount)}
Remaining/Over: {_fmt_money(insight.remaining_amount)}
Threshold percent: {insight.threshold_percent}
Progress percent: {insight.progress_percent}

Context JSON:
{json.dumps(context, ensure_ascii=False)}
""".strip()

    try:
        with OpenRouter(api_key=settings.openrouter_api_key) as client:
            response = client.chat.send(
                model=settings.openrouter_chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write concise financial email summaries. "
                            "Do not include greetings, sign-offs, bullets, markdown, or subject lines."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        content = response.choices[0].message.content or ""
        cleaned = _sanitize_ai_summary(content)
        return cleaned or _fallback_summary_text(user.full_name, insight, context)
    except Exception as exc:
        logger.warning("[Notifications] AI summary failed: %s", exc)
        return _fallback_summary_text(user.full_name, insight, context)


def _render_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<tr><td style='padding:10px 0;color:#64748b'>No data yet.</td></tr>"

    out = []
    for item in items[:5]:
        out.append(
            f"""
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;">{html.escape(str(item.get('name') or item.get('day') or 'Unknown'))}</td>
              <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{_fmt_money(item.get('value') or item.get('amount') or 0)}</td>
            </tr>
            """
        )
    return "".join(out)


def _render_email_html(
    user: User,
    insight: BudgetInsight,
    context: dict[str, Any],
    ai_summary: str,
    title: str,
    badge: str,
    accent: str,
) -> str:
    summary_text = (ai_summary or "").strip() or _fallback_summary_text(user.full_name, insight, context)
    summary_html = html.escape(summary_text).replace("\n", "<br/>")

    top_vendors = context.get("top_vendors", [])
    top_items = context.get("top_items", [])
    most_day = context.get("most_expensive_day") or {}

    period_start = context.get("budget_period_start", "")
    period_end = context.get("budget_period_end", "")

    return f"""
    <div style="margin:0;padding:0;background:#eef2ff;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0f172a;">
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#eef2ff;">
        <tr>
          <td align="center" style="padding:24px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width:860px;border-collapse:collapse;background:#ffffff;border-radius:24px;overflow:hidden;box-shadow:0 20px 50px rgba(15,23,42,.12);border:1px solid #e2e8f0;">
              <tr>
                <td style="padding:24px 28px;background:linear-gradient(135deg,{accent},#0f172a);color:#fff;">
                  <div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;opacity:.82;">Spendly budget alert</div>
                  <div style="font-size:28px;font-weight:800;margin-top:8px;line-height:1.15;">{html.escape(insight.category_name)} budget update</div>
                  <div style="margin-top:12px;display:inline-block;padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.16);font-weight:700;font-size:13px;">{html.escape(badge)}</div>
                </td>
              </tr>

              <tr>
                <td style="padding:26px 28px 10px 28px;">
                  <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:12px;">
                    <tr>
                      <td style="width:25%;background:#f8fafc;border:1px solid #e2e8f0;border-radius:18px;padding:16px;">
                        <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">Budget</div>
                        <div style="margin-top:8px;font-size:18px;font-weight:800;color:#0f172a;">{_fmt_money(insight.budget_limit)}</div>
                      </td>
                      <td style="width:25%;background:#f8fafc;border:1px solid #e2e8f0;border-radius:18px;padding:16px;">
                        <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">Spent</div>
                        <div style="margin-top:8px;font-size:18px;font-weight:800;color:#0f172a;">{_fmt_money(insight.spent_amount)}</div>
                      </td>
                      <td style="width:25%;background:#f8fafc;border:1px solid #e2e8f0;border-radius:18px;padding:16px;">
                        <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">Remaining / Over</div>
                        <div style="margin-top:8px;font-size:18px;font-weight:800;color:#0f172a;">{_fmt_money(insight.remaining_amount)}</div>
                      </td>
                      <td style="width:25%;background:#f8fafc;border:1px solid #e2e8f0;border-radius:18px;padding:16px;">
                        <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">Progress</div>
                        <div style="margin-top:8px;font-size:18px;font-weight:800;color:#0f172a;">{insight.progress_percent}%</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <tr>
                <td style="padding:0 28px 8px 28px;">
                  <div style="font-size:16px;font-weight:800;color:#0f172a;margin:12px 0 12px;">Summary</div>
                  <div style="border:1px solid #e2e8f0;background:#f8fafc;border-radius:20px;padding:22px 22px 18px 22px;">
                    <div style="font-size:15px;line-height:1.8;color:#334155;white-space:normal;">{summary_html}</div>
                  </div>
                </td>
              </tr>

              <tr>
                <td style="padding:0 28px 8px 28px;">
                  <div style="font-size:16px;font-weight:800;color:#0f172a;margin:12px 0 12px;">Top merchants</div>
                  <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;overflow:hidden;">
                    <tr>
                      <td style="padding:12px 14px;font-size:12px;color:#64748b;font-weight:700;border-bottom:1px solid #e2e8f0;">Merchant</td>
                      <td style="padding:12px 14px;font-size:12px;color:#64748b;font-weight:700;border-bottom:1px solid #e2e8f0;text-align:right;">Amount</td>
                    </tr>
                    {_render_rows(top_vendors)}
                  </table>
                </td>
              </tr>

              <tr>
                <td style="padding:0 28px 8px 28px;">
                  <div style="font-size:16px;font-weight:800;color:#0f172a;margin:12px 0 12px;">Top items</div>
                  <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;overflow:hidden;">
                    <tr>
                      <td style="padding:12px 14px;font-size:12px;color:#64748b;font-weight:700;border-bottom:1px solid #e2e8f0;">Item</td>
                      <td style="padding:12px 14px;font-size:12px;color:#64748b;font-weight:700;border-bottom:1px solid #e2e8f0;text-align:right;">Amount</td>
                    </tr>
                    {_render_rows(top_items)}
                  </table>
                </td>
              </tr>

              <tr>
                <td style="padding:0 28px 8px 28px;">
                  <div style="font-size:16px;font-weight:800;color:#0f172a;margin:12px 0 12px;">Most expensive day</div>
                  <div style="border:1px solid #e2e8f0;background:#f8fafc;border-radius:18px;padding:16px 18px;">
                    <div style="font-size:14px;color:#334155;">
                      {html.escape(str(most_day.get('day') or 'Not available'))}
                      <span style="float:right;font-weight:800;">{_fmt_money(most_day.get('value', 0))}</span>
                    </div>
                  </div>
                </td>
              </tr>

              <tr>
                <td style="padding:0 28px 8px 28px;">
                  <div style="font-size:16px;font-weight:800;color:#0f172a;margin:12px 0 12px;">Budget period</div>
                  <div style="border:1px solid #e2e8f0;background:#f8fafc;border-radius:18px;padding:16px 18px;font-size:14px;color:#334155;">
                    {html.escape(period_start)} to {html.escape(period_end)}
                  </div>
                </td>
              </tr>

              <tr>
                <td style="padding:0 28px 24px 28px;">
                  <div style="font-size:12px;color:#64748b;line-height:1.7;">
                    This mail is generated automatically from your tracked expenses and budget settings.
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
    """


def _send_resend_email(to_email: str, subject: str, html_body: str) -> bool:
    return send_email(to_email, subject, html_body)


def _log_email(db: Session, user_id: str, email_type: str, subject: str, status: str) -> None:
    db.execute(
        insert(EmailLog).values(
            id=str(uuid4()),
            user_id=user_id,
            email_type=email_type,
            subject=subject,
            status=status,
        )
    )


def send_budget_notifications_and_emails(
    db: Session,
    user_id: str,
    periodic_check: bool = False,
) -> list[BudgetInsight]:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        return []

    insights = build_budget_insights(db, user_id)
    today = _today()

    for insight in insights:
        try:
            budget = db.scalar(select(Budget).where(Budget.id == insight.budget_id))
            if not budget:
                continue

            budget_key = _budget_state_key(insight)

            if insight.crossed or insight.warning:
                notification_type = "BUDGET_EXCEEDED" if insight.crossed else "BUDGET_WARNING"
                title = f"{'⚠️' if insight.crossed else 'ℹ️'} {notification_type.replace('_', ' ').title()}: {insight.category_name}"
                message = (
                    f"You {'crossed' if insight.crossed else 'reached'} your {insight.period} budget for {insight.category_name}. "
                    f"Spent {_fmt_money(insight.spent_amount)} out of {_fmt_money(insight.budget_limit)}. "
                    f"Remaining/Over: {_fmt_money(insight.remaining_amount)}."
                )
                create_notification(
                    db,
                    user_id,
                    title,
                    message,
                    notification_type,
                    action_url=f"/dashboard?budget_state={budget_key}",
                )

                email_type = _safe_email_type(notification_type, budget_key)
                if user.email and not _email_log_exists(db, user_id, email_type):
                    context = _build_context_for_budget(db, user_id, budget, insight.start_date, insight.end_date)
                    ai_summary = _build_ai_email_summary(user, insight, context)
                    subject = f"{_budget_subject_prefix(insight)} — {insight.category_name}"
                    html_body = _render_email_html(
                        user=user,
                        insight=insight,
                        context=context,
                        ai_summary=ai_summary,
                        title=subject,
                        badge="Budget crossed" if insight.crossed else "Budget warning",
                        accent="#dc2626" if insight.crossed else "#d97706",
                    )
                    sent = _send_resend_email(user.email, subject, html_body)
                    _log_email(db, user_id, email_type, subject, "SENT" if sent else "FAILED")

            period_ended = today >= insight.end_date
            summary_enabled = _user_summary_enabled(
                db,
                user_id,
                insight.period if insight.period in {"weekly", "monthly"} else "monthly",
            )

            if period_ended and summary_enabled and not insight.crossed:
                summary_type = _safe_email_type("SUMMARY", budget_key)
                title = f"📊 {insight.period.title()} summary — {insight.category_name}"
                message = f"Your {insight.period} budget summary for {insight.category_name} is ready."

                if not _notification_exists(db, user_id, "BUDGET_SUMMARY", title, message, "/dashboard"):
                    create_notification(
                        db,
                        user_id,
                        title,
                        message,
                        "BUDGET_SUMMARY",
                        action_url=f"/dashboard?budget_state={budget_key}&summary=1",
                    )

                if user.email and not _email_log_exists(db, user_id, summary_type):
                    context = _build_context_for_budget(db, user_id, budget, insight.start_date, insight.end_date)
                    ai_summary = _build_ai_email_summary(user, insight, context)
                    subject = f"✅ {insight.period.title()} summary — {insight.category_name}"
                    html_body = _render_email_html(
                        user=user,
                        insight=insight,
                        context=context,
                        ai_summary=ai_summary,
                        title=subject,
                        badge="Within budget",
                        accent="#16a34a",
                    )
                    sent = _send_resend_email(user.email, subject, html_body)
                    _log_email(db, user_id, summary_type, subject, "SENT" if sent else "FAILED")

        except Exception as exc:
            logger.exception(
                "[Notifications] budget processing failed for user %s budget %s: %s",
                user_id,
                insight.budget_id,
                exc,
            )

    db.commit()
    return insights


def sync_notifications_for_user(db: Session, user_id: str) -> list[BudgetInsight]:
    return send_budget_notifications_and_emails(db, user_id, periodic_check=False)


def run_budget_watch_for_all_users(db: Session) -> None:
    user_ids = [row[0] for row in db.query(Budget.user_id).distinct().all()]
    for uid in user_ids:
        try:
            send_budget_notifications_and_emails(db, str(uid), periodic_check=True)
        except Exception as exc:
            logger.exception("[Notifications] budget watcher failed for user %s: %s", uid, exc)


def get_user_notifications(db: Session, user_id: str) -> list[Notification]:
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
    ).all()


def mark_notifications_read(db: Session, user_id: str, ids: list[str]) -> int:
    if not ids:
        return 0

    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.id.in_(ids),
        )
    ).all()

    for item in rows:
        item.is_read = True

    db.commit()
    return len(rows)


def mark_all_notifications_read(db: Session, user_id: str) -> int:
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    ).all()

    for item in rows:
        item.is_read = True

    db.commit()
    return len(rows)