from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.ai_chat_history import AIChatHistory
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.analytics import build_chat_context
from app.services.llm import llm_chat_response

try:
    from app.services.notifications import build_budget_insights
except Exception:  # pragma: no cover
    build_budget_insights = None  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _recent_chat_history(db: Session, user_id: str, limit: int = 8) -> list[dict[str, str]]:
    rows = db.scalars(
        select(AIChatHistory)
        .where(AIChatHistory.user_id == user_id)
        .order_by(desc(AIChatHistory.created_at))
        .limit(limit)
    ).all()

    rows.reverse()
    history: list[dict[str, str]] = []
    for row in rows:
        if getattr(row, "user_message", None):
            history.append({"role": "user", "content": str(row.user_message)})
        if getattr(row, "ai_response", None):
            history.append({"role": "assistant", "content": str(row.ai_response)})
    return history[-12:]


def _safe_context(db: Session, user_id: str) -> dict:
    context: dict = {
        "summary": {},
        "monthly_totals": [],
        "item_totals": [],
        "recent_expenses": [],
        "budget_insights": [],
    }

    try:
        context.update(build_chat_context(db, user_id))
    except Exception as exc:
        logger.exception("[Chat] context build failed: %s", exc)
        try:
            from app.services.analytics import build_dashboard_summary
            context["summary"] = build_dashboard_summary(db, user_id)
        except Exception as summary_exc:
            logger.warning("[Chat] summary fallback failed: %s", summary_exc)

    if build_budget_insights is not None:
        try:
            insights = build_budget_insights(db, user_id)
            context["budget_insights"] = [
                {
                    "budget_id": str(x.budget_id),
                    "category_name": x.category_name,
                    "period": x.period,
                    "budget_limit": float(x.budget_limit),
                    "spent_amount": float(x.spent_amount),
                    "threshold_percent": int(x.threshold_percent),
                    "progress_percent": int(x.progress_percent),
                    "crossed": bool(x.crossed),
                    "warning": bool(x.warning),
                    "remaining_amount": float(x.remaining_amount),
                    "start_date": x.start_date.isoformat(),
                    "end_date": x.end_date.isoformat(),
                }
                for x in insights
            ]
        except Exception as exc:
            logger.warning("[Chat] budget insights failed: %s", exc)

    return context


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = str(current_user.id)
    context = _safe_context(db, user_id)
    history = _recent_chat_history(db, user_id)

    logger.info("[Chat] request user_id=%s history_turns=%d question=%r", user_id, len(history), payload.message[:200])
    result = llm_chat_response(payload.message, context, history=history)
    logger.info("[Chat] response_preview=%s sql_present=%s", result.get("answer", "")[:250], bool(result.get("sql")))

    try:
        db.add(
            AIChatHistory(
                id=str(uuid4()),
                user_id=user_id,
                user_message=payload.message,
                ai_response=result["answer"],
                expense_context=context,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("[Chat] history save failed: %s", exc)

    return ChatResponse(answer=result["answer"], sql=result.get("sql"))
