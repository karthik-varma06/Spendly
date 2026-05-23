from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime
from typing import Any

from openrouter import OpenRouter

from app.core.config import get_settings

logger = logging.getLogger("ai_finance_tracker.llm")
settings = get_settings()

ALLOWED_CATEGORIES = {
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
}

SCHEMA_CONTEXT = """
Database schema overview (PostgreSQL):

users(id, full_name, email, password_hash, profile_image, currency, timezone, is_verified, is_active, created_at, updated_at)
user_settings(id, user_id, theme, weekly_email_enabled, monthly_email_enabled, budget_alerts_enabled, ai_chat_enabled, created_at, updated_at)
categories(id, name, icon, color, created_at)
budgets(id, user_id, category_id, budget_limit, spent_amount, period, start_date, end_date, notify_percentage, is_active, created_at)
expenses(id, user_id, category_id, uploaded_file_id, vendor_name, vendor_phone, vendor_email, vendor_address, invoice_number, expense_date, expense_time, subtotal, cgst, sgst, igst, tax_amount, discount_amount, total_amount, currency, payment_method, notes, extraction_confidence, is_reviewed, is_manual, status, created_at, updated_at)
expense_items(id, expense_id, item_name, item_category, quantity, unit_price, total_price, created_at)
income(id, user_id, source, amount, income_date, notes, created_at)
notifications(id, user_id, title, message, type, action_url, is_read, created_at)
ai_chat_history(id, user_id, user_message, ai_response, expense_context, created_at)
email_logs(id, user_id, email_type, subject, status, sent_at)
uploaded_files(id, user_id, original_filename, stored_filename, file_type, file_size, mime_type, extracted_text, extraction_status, ocr_engine, llm_model, upload_source, created_at)
recurring_expenses(id, user_id, category_id, title, amount, frequency, next_due_date, last_generated_at, is_active, created_at)

Important relationships:
- expenses.category_id -> categories.id
- budgets.category_id -> categories.id
- expense_items.expense_id -> expenses.id
- all financial rows are scoped by user_id
- expense totals are in expenses.total_amount
- item totals are in expense_items.total_price
""".strip()


def money(value: Any) -> str:
    try:
        return f"₹{float(value or 0):,.2f}"
    except Exception:
        return "₹0.00"


def _extract_json_block(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        cleaned = match.group(0)

    return json.loads(cleaned)


def _normalize_answer(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    cleaned = cleaned.replace("$", "₹")
    cleaned = re.sub(r"\bUSD\b", "₹", cleaned, flags=re.I)
    cleaned = re.sub(r"(?im)^\s*subject\s*:\s*.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(hi|hello|dear)\b.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(warm regards|best regards|regards|thanks|thank you)\b.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*p\.s\..*$", "", cleaned)

    lines: list[str] = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"(?i)^(subject|hi|hello|dear|warm regards|best regards|regards|thanks|thank you)\b", line):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _top_rows(items: list[dict[str, Any]], key: str = "name", val: str = "value", limit: int = 5) -> str:
    if not items:
        return "No data yet."
    parts = []
    for item in items[:limit]:
        label = item.get(key) or item.get("day") or item.get("month") or "Unknown"
        amount = item.get(val) or item.get("amount") or 0
        parts.append(f"{label}: {money(amount)}")
    return "; ".join(parts)


def _build_context_summary(context: dict[str, Any]) -> str:
    summary = context.get("summary") or {}
    lines = [
        f"Monthly expense: {money(summary.get('monthly_expense', 0))}",
        f"Yearly expense: {money(summary.get('yearly_expense', 0))}",
        f"Savings: {money(summary.get('savings', 0))}",
        f"Top categories: {_top_rows(summary.get('category_breakdown', []))}",
        f"Top merchants: {_top_rows(summary.get('top_merchants', []))}",
        f"Top items: {_top_rows(summary.get('top_items', []))}",
        f"Most expensive month: {json.dumps(summary.get('most_expensive_month', None), ensure_ascii=False)}",
        f"Budget insights: {json.dumps(context.get('budget_insights', [])[:10], ensure_ascii=False)}",
        f"Recent expenses: {json.dumps(context.get('recent_expenses', [])[:10], ensure_ascii=False)}",
        f"Monthly totals: {json.dumps(context.get('monthly_totals', [])[:12], ensure_ascii=False)}",
        f"Item totals: {json.dumps(context.get('item_totals', [])[:10], ensure_ascii=False)}",
    ]
    return "\n".join(lines)


def _conversation_block(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return "No prior conversation."

    lines: list[str] = []
    for msg in history[-10:]:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", "")).strip().replace("\n", " ")
        if not content:
            continue
        tag = "User" if role == "user" else "Assistant"
        lines.append(f"{tag}: {content}")
    return "\n".join(lines) if lines else "No prior conversation."


def _history_text(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return "No prior conversation."

    lines: list[str] = []
    for msg in history[-10:]:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", "")).strip().replace("\n", " ")
        if not content:
            continue
        tag = "User" if role == "user" else "Assistant"
        lines.append(f"{tag}: {content}")
    return "\n".join(lines) if lines else "No prior conversation."


def _question_is_reasoning_query(message: str) -> bool:
    msg = (message or "").lower()
    return any(
        phrase in msg
        for phrase in [
            "biggest reason",
            "why did",
            "why is",
            "reason my spending",
            "overspending",
            "overspend",
            "overspending right now",
            "what was the main driver",
            "what made it go up",
        ]
    )


def _best_budget_insight(context: dict[str, Any]) -> dict[str, Any] | None:
    insights = context.get("budget_insights") or []
    if not insights:
        return None

    def score(item: dict[str, Any]) -> tuple[int, int, float]:
        return (
            1 if item.get("crossed") else 0,
            1 if item.get("warning") else 0,
            float(item.get("progress_percent") or 0),
        )

    return sorted(insights, key=score, reverse=True)[0]


def _reasoned_answer(context: dict[str, Any]) -> str:
    summary = context.get("summary") or {}
    category_breakdown = summary.get("category_breakdown") or []
    top_merchants = summary.get("top_merchants") or []
    top_items = summary.get("top_items") or []
    recent_expenses = context.get("recent_expenses") or []
    insight = _best_budget_insight(context)

    if insight:
        category_name = str(insight.get("category_name") or "your tracked spending")
        spent = money(insight.get("spent_amount", 0))
        limit = money(insight.get("budget_limit", 0))
        progress = insight.get("progress_percent")
        remaining = money(insight.get("remaining_amount", 0))
        crossed = bool(insight.get("crossed"))

        vendor_name = None
        vendor_amount = None
        for row in top_merchants[:3]:
            if row.get("name"):
                vendor_name = str(row["name"])
                vendor_amount = money(row.get("value", 0))
                break

        item_name = None
        item_amount = None
        for row in top_items[:3]:
            if row.get("name"):
                item_name = str(row["name"])
                item_amount = money(row.get("value", 0))
                break

        day_name = None
        day_amount = None
        month_like = summary.get("most_expensive_month") or {}
        if month_like.get("month"):
            day_name = str(month_like.get("month"))
            day_amount = money(month_like.get("amount", 0))

        lines = []
        if crossed:
            lines.append(
                f"Your spending went up mainly because {category_name} crossed the budget limit: you spent {spent} against {limit}."
            )
        else:
            lines.append(
                f"Your spending went up mainly because {category_name} is close to the limit: you spent {spent} out of {limit} ({progress}% used)."
            )

        if vendor_name:
            extra = f" A big share is coming from {vendor_name}"
            if vendor_amount:
                extra += f" at {vendor_amount}"
            extra += "."
            lines.append(extra)

        if item_name:
            lines.append(f"The highest item-level pressure appears to be {item_name} at {item_amount or money(0)}.")

        if day_name and day_amount:
            lines.append(f"Your highest-cost period was {day_name} at {day_amount}, which likely pushed the total up.")

        if recent_expenses:
            top_recent = sorted(
                [r for r in recent_expenses if r.get("total_amount") is not None],
                key=lambda x: float(x.get("total_amount") or 0),
                reverse=True,
            )[:2]
            if top_recent:
                vendors = ", ".join(
                    str(r.get("vendor_name") or "Unknown")
                    for r in top_recent
                    if r.get("vendor_name")
                )
                if vendors:
                    lines.append(f"Recent high-value purchases also include {vendors}.")

        lines.append("Try cutting the most frequent high-value purchases for the next few days so the budget can settle back down.")
        return " ".join(lines)

    if category_breakdown:
        top = category_breakdown[0]
        name = str(top.get("name") or "your tracked spending")
        value = money(top.get("value", 0))
        total = float(summary.get("monthly_expense") or 0)
        share = round(float(top.get("value") or 0) / total * 100, 1) if total > 0 else None
        share_text = f" ({share}% of your monthly spend)" if share is not None else ""
        return (
            f"{name} is the biggest spending area right now at {value}{share_text}. "
            f"That is the main reason your total moved up. "
            f"Focus on reducing the largest purchases in this category for a few days."
        )

    return (
        f"Monthly expense: {money(summary.get('monthly_expense', 0))}. "
        f"Yearly expense: {money(summary.get('yearly_expense', 0))}. "
        f"Savings: {money(summary.get('savings', 0))}."
    )


def _fallback_chat_response(
    message: str,
    context: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    msg = (message or "").lower()
    summary = context.get("summary") or {}
    category_breakdown = summary.get("category_breakdown") or []
    top_merchants = summary.get("top_merchants") or []
    top_items = summary.get("top_items") or []
    most_month = summary.get("most_expensive_month") or {}
    budget_insights = context.get("budget_insights") or []

    monthly_expense = money(summary.get("monthly_expense", 0))
    yearly_expense = money(summary.get("yearly_expense", 0))
    savings = money(summary.get("savings", 0))

    top_category = category_breakdown[0] if category_breakdown else None
    top_category_name = str(top_category.get("name")) if top_category else "your tracked spending"
    top_category_value = money(top_category.get("value", 0)) if top_category else money(0)

    if _question_is_reasoning_query(message):
        return {"answer": _reasoned_answer(context), "sql": None}

    if any(word in msg for word in ["which category is overspending", "which category is over spending", "budget health", "how close am i to my", "budget"]):
        if budget_insights:
            worst = _best_budget_insight(context)
            if worst:
                cat = worst.get("category_name") or top_category_name
                spent = money(worst.get("spent_amount", 0))
                limit = money(worst.get("budget_limit", 0))
                progress = worst.get("progress_percent", 0)
                crossed = bool(worst.get("crossed"))
                tail = "It is already over the limit." if crossed else "Trim spending here for the rest of the week."
                return {
                    "answer": f"{cat} is the category to watch. You have spent {spent} out of {limit} ({progress}% used). {tail}",
                    "sql": None,
                }

        if top_category:
            total = float(summary.get("monthly_expense") or 0)
            top_val = float(top_category.get("value") or 0)
            share = round(top_val / total * 100, 1) if total > 0 else 0
            return {
                "answer": f"{top_category_name} is currently your biggest spending category at {top_category_value}, which is about {share}% of your monthly spend. Try to reduce purchases in this category for the next few days.",
                "sql": None,
            }

    if "most expensive month" in msg and most_month.get("month"):
        return {
            "answer": f"Your most expensive month is {most_month['month']} with {money(most_month.get('amount', 0))} spent.",
            "sql": None,
        }

    if "food" in msg:
        for row in category_breakdown:
            if str(row.get("name", "")).upper() == "FOOD":
                return {
                    "answer": f"You spent {money(row.get('value', 0))} on FOOD. That is the category to watch if you want to slow down spending.",
                    "sql": None,
                }

    base = (
        f"Here is a quick view from your data: this month is {monthly_expense}, your yearly spend is {yearly_expense}, "
        f"and your savings are {savings}. "
    )
    if top_category:
        base += f"Your biggest category right now is {top_category_name} at {top_category_value}. "
    if most_month.get("month"):
        base += f"Your most expensive month is {most_month['month']} at {money(most_month.get('amount', 0))}. "
    base += "Ask me for a category breakdown, a spending trend, or a SQL query and I will help."

    sql = None
    if any(word in msg for word in ["sql", "query", "database", "table"]):
        sql = (
            "SELECT category_id, SUM(total_amount) "
            "FROM expenses WHERE user_id = :user_id "
            "GROUP BY category_id ORDER BY SUM(total_amount) DESC;"
        )

    return {"answer": base.strip(), "sql": sql}


def _build_prompt(message: str, context: dict[str, Any], history: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    user_message = (message or "").strip()

    system = f"""
You are a helpful AI finance assistant for a personal expense tracker.

Answer like a smart, friendly finance bot. Do not just repeat raw numbers.
Use the supplied context and the recent conversation.
If the user asks a follow-up, use the history to understand what "this", "that", "it", "why", or "now" refers to.
If asked "why spending went up" or "which category is overspending", explain the main driver, mention a top merchant or item if available, and give one short action step.
Keep the tone concise, practical, and natural. Avoid awkward caps, weird jargon, or generic filler.
Use Indian Rupees (₹) only.
If the user asks for SQL, return a PostgreSQL query in the sql field.
If the user does not ask for SQL, set sql to null.
If the data is not enough, say that clearly and suggest what to check next.
Use only the provided schema and context.
Do not invent table names or columns.
Do not reveal chain of thought.

Return valid JSON only with this shape:
{{
  "answer": "concise human-friendly response",
  "sql": "PostgreSQL query or null"
}}

The answer should be 2-5 sentences, specific, and grounded in the context.
Avoid one-word answers.

{SCHEMA_CONTEXT}
""".strip()

    user = f"""
User question:
{user_message}

Conversation history:
{_history_text(history)}

Context:
{_build_context_summary(context)}
""".strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _answer_needs_fallback(message: str, answer: str) -> tuple[bool, str]:
    text = (answer or "").strip()
    msg = (message or "").lower()
    if not text:
        return True, "empty"

    word_count = len(text.split())
    if len(text) < 18 or word_count <= 3:
        return True, "too_short"

    if any(token in msg for token in ["why", "reason", "overspending", "overspend", "overspending right now", "biggest reason"]):
        if word_count < 12:
            return True, "reason_query_too_short"

    weird_caps = sum(1 for line in text.splitlines() if line.strip() and sum(ch.isupper() for ch in line if ch.isalpha()) > max(6, len(line.strip()) * 0.6))
    if weird_caps > 0:
        return True, "weird_caps"

    return False, ""


def llm_chat_response(
    message: str,
    context: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fallback = _fallback_chat_response(message, context, history)

    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        logger.info("[LLM] provider=fallback reason=no_api_key answer=%s", fallback["answer"][:500])
        return fallback

    logger.info(
        "[LLM] chat_request model=%s history_turns=%d question=%r",
        settings.openrouter_chat_model,
        len(history or []),
        (message or "")[:200],
    )

    try:
        with OpenRouter(api_key=api_key) as client:
            response = client.chat.send(
                model=settings.openrouter_chat_model,
                messages=_build_prompt(message, context, history),
            )

        content = response.choices[0].message.content or ""
        logger.info("[LLM] openrouter_raw model=%s response=%s", settings.openrouter_chat_model, content[:1500])

        parsed: dict[str, Any] = {}
        parse_reason = ""
        try:
            parsed = _extract_json_block(content)
        except Exception as exc:
            parse_reason = f"json_parse_failed:{exc.__class__.__name__}"
            logger.warning("[LLM] json parse failed: %s", exc)
            parsed = {}

        answer_source = str(parsed.get("answer") or content or "").strip()
        answer = _normalize_answer(answer_source)
        sql = parsed.get("sql", None)

        needs_fallback, fallback_reason = _answer_needs_fallback(message, answer)
        if needs_fallback:
            logger.info(
                "[LLM] provider=openrouter fallback=true reason=%s%s",
                fallback_reason,
                f",{parse_reason}" if parse_reason else "",
            )
            answer = fallback["answer"]
            sql = fallback.get("sql", sql)
            logger.info("[LLM] fallback_answer=%s", answer[:700])
        else:
            logger.info(
                "[LLM] provider=openrouter fallback=false model=%s answer=%s sql_present=%s",
                settings.openrouter_chat_model,
                answer[:700],
                bool(sql),
            )

        if sql is not None:
            sql = str(sql).strip() or None

        return {"answer": answer, "sql": sql}

    except Exception as exc:
        logger.warning("[LLM] provider=fallback reason=openrouter_exception:%s", exc.__class__.__name__)
        logger.exception("[LLM] chat generation failed: %s", exc)
        logger.info("[LLM] fallback_answer=%s", fallback["answer"][:700])
        return fallback


def llm_chat_answer(message: str, context: dict[str, Any], history: list[dict[str, Any]] | None = None) -> str:
    return llm_chat_response(message, context, history)["answer"]
def supports_image_input(model_name: str | None = None) -> bool:
    model = (model_name or settings.openrouter_vision_model or "").lower()
    return any(token in model for token in ("-vl", "vision", "omni"))


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return default
    text = re.sub(r"[^\d.\-]", "", text)
    try:
        return float(text)
    except Exception:
        return default


def _is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip().lower()
        return s in {"", "unknown", "null", "none", "n/a", "na"}
    if isinstance(v, (int, float)):
        return v == 0
    return False


def _normalize_category(value: Any) -> str:
    if _is_missing(value):
        return "OTHER"
    text = str(value).strip().upper()
    return text if text in ALLOWED_CATEGORIES else "OTHER"


def _parse_date_any(value: str | None) -> str | None:
    if not value or _is_missing(value):
        return None

    text = str(value).strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except Exception:
            pass

    match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
        except Exception:
            pass

    return text


def _parse_time_any(value: str | None) -> str | None:
    if not value or _is_missing(value):
        return None

    text = str(value).strip()
    match = re.search(r"\b(\d{1,2}:\d{2})(?:\s?([AP]M))?\b", text, re.I)
    if match:
        base = match.group(1)
        suffix = match.group(2)
        return f"{base} {suffix}".strip() if suffix else base
    return text


def _build_text_prompt(raw_text: str) -> list[dict[str, str]]:
    system = (
        "You are an expert invoice/receipt/bill extraction engine.\n"
        "Return ONLY valid JSON. No markdown, no commentary.\n"
        "Do not invent data. If a field is not present, use null or empty string.\n"
        "Use these allowed categories only: FOOD, TRAVEL, SHOPPING, ELECTRONICS, HEALTH, UTILITIES, "
        "ENTERTAINMENT, SUBSCRIPTIONS, EDUCATION, TRANSPORT, OTHER.\n"
        "Always extract vendor name, invoice number, date, time, phone, email, address, items, taxes, subtotal, total, and payment method.\n"
        "Dates should be YYYY-MM-DD if possible.\n"
    )

    user = f"""
Extract these fields from the receipt text.

Schema:
{{
  "vendor_name": null,
  "invoice_number": null,
  "date": null,
  "time": null,
  "phone": null,
  "email": null,
  "address": null,
  "items": [
    {{
      "item_name": "",
      "quantity": 1,
      "unit_price": 0,
      "total_price": 0,
      "item_category": null
    }}
  ],
  "subtotal": 0,
  "cgst": 0,
  "sgst": 0,
  "igst": 0,
  "discount": 0,
  "total_amount": 0,
  "payment_method": null,
  "category": "OTHER"
}}

Rules:
- If item line says "1 x Chicken Biryani 290.00", quantity=1, item_name="Chicken Biryani", unit_price=290.00, total_price=290.00.
- Keep numbers as numbers, not strings.
- If payment says online or card, keep that exact method.
- If invoice/receipt number is present, store it.
- If category is food, put FOOD.

Receipt text:
{raw_text}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_image_prompt() -> str:
    return (
        "Extract structured financial data from this receipt image.\n"
        "Return ONLY valid JSON.\n"
        "Do not invent values.\n"
        "Allowed categories: FOOD, TRAVEL, SHOPPING, ELECTRONICS, HEALTH, UTILITIES, "
        "ENTERTAINMENT, SUBSCRIPTIONS, EDUCATION, TRANSPORT, OTHER.\n"
        "Output schema:\n"
        "{"
        '"vendor_name":null,"invoice_number":null,"date":null,"time":null,'
        '"phone":null,"email":null,"address":null,'
        '"items":[{"item_name":"","quantity":1,"unit_price":0,"total_price":0,"item_category":null}],'
        '"subtotal":0,"cgst":0,"sgst":0,"igst":0,"discount":0,"total_amount":0,'
        '"payment_method":null,"category":"OTHER"'
        "}"
    )


def _fallback_local_parser(raw_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    vendor_name = lines[0] if lines else None

    phone_match = re.search(r"(\+?\d[\d\s-]{8,}\d)", raw_text)
    phone = phone_match.group(1).replace("  ", " ").strip() if phone_match else None

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text)
    email = email_match.group(0) if email_match else None

    date_match = re.search(r"\b(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b", raw_text)
    date = _parse_date_any(date_match.group(1)) if date_match else None

    time_match = re.search(r"\b(\d{1,2}:\d{2}(?:\s?[AP]M)?)\b", raw_text, re.I)
    time = _parse_time_any(time_match.group(1)) if time_match else None

    invoice_match = re.search(r"(?:RECEIPT\s*NO|INVOICE\s*NO|BILL\s*NO|NO\.?)\s*[:\-]?\s*([A-Z0-9\-\/]+)", raw_text, re.I)
    invoice_number = invoice_match.group(1) if invoice_match else None

    subtotal_match = re.search(r"SUBTOTAL\s*[:\-]?\s*([0-9,]+(?:\.\d+)?)", raw_text, re.I)
    cgst_match = re.search(r"CGST.*?([0-9,]+(?:\.\d+)?)", raw_text, re.I)
    sgst_match = re.search(r"SGST.*?([0-9,]+(?:\.\d+)?)", raw_text, re.I)
    igst_match = re.search(r"IGST.*?([0-9,]+(?:\.\d+)?)", raw_text, re.I)
    total_match = re.search(r"TOTAL\s*[:\-]?\s*([0-9,]+(?:\.\d+)?)", raw_text, re.I)
    discount_match = re.search(r"DISCOUNT\s*[:\-]?\s*([0-9,]+(?:\.\d+)?)", raw_text, re.I)

    items: list[dict[str, Any]] = []
    for line in lines:
        item_match = re.match(
            r"(?P<qty>\d+(?:\.\d+)?)\s*x\s*(?P<name>.+?)\s+(?P<price>\d+(?:,\d{3})*(?:\.\d+)?)$",
            line,
            re.I,
        )
        if item_match:
            qty = _to_float(item_match.group("qty"), 1)
            price = _to_float(item_match.group("price"), 0)
            name = item_match.group("name").strip()
            items.append(
                {
                    "item_name": name,
                    "quantity": qty,
                    "unit_price": price,
                    "total_price": price * qty,
                    "item_category": None,
                }
            )

    category = "OTHER"
    text_upper = raw_text.upper()
    if any(k in text_upper for k in ["BIRYANI", "FOOD", "RESTAURANT", "MESS", "CAFE", "HOTEL"]):
        category = "FOOD"
    elif any(k in text_upper for k in ["TAXI", "CAB", "UBER", "OLA", "FLIGHT", "BUS", "TRAIN"]):
        category = "TRAVEL"
    elif any(k in text_upper for k in ["MOBILE", "LAPTOP", "ELECTRONIC", "HEADPHONE", "TV"]):
        category = "ELECTRONICS"

    payment_method = None
    if "ONLINE" in text_upper:
        payment_method = "ONLINE"
    elif "CASH" in text_upper:
        payment_method = "CASH"
    elif "CARD" in text_upper:
        payment_method = "CARD"

    return {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "date": date,
        "time": time,
        "phone": phone,
        "email": email,
        "address": None,
        "items": items,
        "subtotal": _to_float(subtotal_match.group(1), 0) if subtotal_match else 0,
        "cgst": _to_float(cgst_match.group(1), 0) if cgst_match else 0,
        "sgst": _to_float(sgst_match.group(1), 0) if sgst_match else 0,
        "igst": _to_float(igst_match.group(1), 0) if igst_match else 0,
        "discount": _to_float(discount_match.group(1), 0) if discount_match else 0,
        "total_amount": _to_float(total_match.group(1), 0) if total_match else 0,
        "payment_method": payment_method,
        "category": category,
    }


def _normalize_output(data: dict[str, Any], raw_text: str, source: str) -> dict[str, Any]:
    normalized_items = []
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue

        quantity = _to_float(item.get("quantity"), 1)
        unit_price = _to_float(item.get("unit_price"), 0)
        total_price = _to_float(item.get("total_price"), 0)

        if total_price == 0 and quantity and unit_price:
            total_price = quantity * unit_price

        normalized_items.append(
            {
                "item_name": str(item.get("item_name") or "Unknown").strip(),
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "item_category": _normalize_category(item.get("item_category")) if item.get("item_category") else None,
            }
        )

    subtotal = _to_float(data.get("subtotal"), 0)
    if subtotal == 0 and normalized_items:
        subtotal = sum(item["total_price"] for item in normalized_items)

    cgst = _to_float(data.get("cgst"), 0)
    sgst = _to_float(data.get("sgst"), 0)
    igst = _to_float(data.get("igst"), 0)
    discount = _to_float(data.get("discount"), 0)
    total_amount = _to_float(data.get("total_amount"), 0)
    if total_amount == 0 and subtotal:
        total_amount = subtotal + cgst + sgst + igst - discount

    return {
        "vendor_name": None if _is_missing(data.get("vendor_name")) else str(data.get("vendor_name")).strip(),
        "invoice_number": None if _is_missing(data.get("invoice_number")) else str(data.get("invoice_number")).strip(),
        "date": _parse_date_any(data.get("date")),
        "time": _parse_time_any(data.get("time")),
        "phone": None if _is_missing(data.get("phone")) else str(data.get("phone")).strip(),
        "email": None if _is_missing(data.get("email")) else str(data.get("email")).strip(),
        "address": None if _is_missing(data.get("address")) else str(data.get("address")).strip(),
        "items": normalized_items,
        "subtotal": subtotal,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "discount": discount,
        "total_amount": total_amount,
        "payment_method": None if _is_missing(data.get("payment_method")) else str(data.get("payment_method")).strip(),
        "category": _normalize_category(data.get("category")),
        "llm_provider": data.get("llm_provider") or "fallback",
        "llm_model": data.get("llm_model") or settings.openrouter_vision_model,
        "llm_error": data.get("llm_error"),
        "extraction_mode": source,
        "raw_text_preview": raw_text[:1200],
    }


def extract_structured_from_text(raw_text: str) -> dict[str, Any]:
    fallback = _fallback_local_parser(raw_text)

    if not settings.openrouter_api_key.strip():
        return _normalize_output(fallback, raw_text, "fallback_text")

    try:
        with OpenRouter(api_key=settings.openrouter_api_key) as client:
            response = client.chat.send(
                model=settings.openrouter_vision_model if supports_image_input(settings.openrouter_vision_model) else settings.openrouter_chat_model,
                messages=_build_text_prompt(raw_text),
            )

        content = response.choices[0].message.content or ""
        logger.info("[LLM] Text response:\n%s", content)

        parsed = _extract_json_block(content)
        merged = _normalize_output({**fallback, **parsed}, raw_text, "text_llm")
        merged["llm_provider"] = "openrouter"
        merged["llm_model"] = settings.openrouter_chat_model
        merged["llm_error"] = None
        return merged

    except Exception as exc:
        logger.warning("[LLM] OpenRouter text extraction failed: %s", exc)
        result = _normalize_output(fallback, raw_text, "fallback_text")
        result["llm_provider"] = "fallback"
        result["llm_error"] = str(exc)
        return result


def extract_structured_from_image_bytes(image_bytes: bytes, mime_type: str | None = None) -> dict[str, Any]:
    if not supports_image_input(settings.openrouter_vision_model):
        raise RuntimeError(
            f"Selected model '{settings.openrouter_vision_model}' is text-only. "
            "Use a vision model such as 'nvidia/nemotron-nano-12b-v2-vl:free'."
        )

    if not settings.openrouter_api_key.strip():
        raise RuntimeError("OPENROUTER_API_KEY missing")

    if not mime_type:
        mime_type = "image/jpeg"

    data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
    prompt = _build_image_prompt()

    with OpenRouter(api_key=settings.openrouter_api_key) as client:
        response = client.chat.send(
            model=settings.openrouter_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        )

    content = response.choices[0].message.content or ""
    logger.info("[LLM] Image response:\n%s", content)

    parsed = _extract_json_block(content)
    normalized = _normalize_output(parsed, "", "vision_llm")
    normalized["llm_provider"] = "openrouter"
    normalized["llm_model"] = settings.openrouter_vision_model
    normalized["llm_error"] = None
    return normalized
