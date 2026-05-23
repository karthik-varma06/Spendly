from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.user_setting import UserSetting

router = APIRouter(prefix="/settings", tags=["settings"])


def _serialize(setting: UserSetting) -> dict:
    weekly = bool(
        getattr(setting, "weekly_email_enabled", getattr(setting, "weekly_summary_enabled", True))
    )
    monthly = bool(
        getattr(setting, "monthly_email_enabled", getattr(setting, "monthly_summary_enabled", True))
    )
    budget_alerts = bool(getattr(setting, "budget_alerts_enabled", getattr(setting, "email_summary_enabled", True)))
    ai_chat = bool(getattr(setting, "ai_chat_enabled", True))

    return {
        "id": setting.id,
        "user_id": setting.user_id,
        "theme": getattr(setting, "theme", "LIGHT"),
        "weekly_email_enabled": weekly,
        "monthly_email_enabled": monthly,
        "budget_alerts_enabled": budget_alerts,
        "ai_chat_enabled": ai_chat,
        # Backwards-compatible aliases used by older frontend code
        "weekly_summary_enabled": weekly,
        "monthly_summary_enabled": monthly,
        "email_summary_enabled": budget_alerts,
        "created_at": getattr(setting, "created_at", None),
        "updated_at": getattr(setting, "updated_at", None),
    }


@router.get("")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    setting = db.scalar(select(UserSetting).where(UserSetting.user_id == current_user.id))
    if not setting:
        return {
            "theme": "LIGHT",
            "weekly_email_enabled": True,
            "monthly_email_enabled": True,
            "budget_alerts_enabled": True,
            "ai_chat_enabled": True,
            "weekly_summary_enabled": True,
            "monthly_summary_enabled": True,
            "email_summary_enabled": True,
        }
    return _serialize(setting)


@router.put("")
def update_settings(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    setting = db.scalar(select(UserSetting).where(UserSetting.user_id == current_user.id))
    if not setting:
        setting = UserSetting(id=str(uuid4()), user_id=str(current_user.id))
        db.add(setting)

    mapping = {
        "weekly_summary_enabled": "weekly_email_enabled",
        "monthly_summary_enabled": "monthly_email_enabled",
        "email_summary_enabled": "budget_alerts_enabled",
    }

    for key, value in payload.items():
        target_key = mapping.get(key, key)
        if hasattr(setting, target_key):
            setattr(setting, target_key, value)

    db.commit()
    db.refresh(setting)
    return {"message": "Settings updated", "settings": _serialize(setting)}
