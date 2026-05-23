from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.notification import NotificationOut, MarkReadRequest
from app.services.notifications import (
    get_user_notifications,
    mark_notifications_read,
    mark_all_notifications_read,
    sync_notifications_for_user,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_notifications(db, str(current_user.id))


@router.post("/read")
def mark_read(
    payload: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = mark_notifications_read(db, str(current_user.id), payload.ids)
    return {"message": "Notifications updated", "updated": updated}


@router.post("/mark-read")
def mark_read_alias(
    payload: MarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = mark_notifications_read(db, str(current_user.id), payload.ids)
    return {"message": "Notifications updated", "updated": updated}


@router.post("/mark-all-read")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = mark_all_notifications_read(db, str(current_user.id))
    return {"message": "All notifications marked read", "updated": updated}


@router.post("/sync")
def sync_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insights = sync_notifications_for_user(db, str(current_user.id))
    return {"message": "Notifications synced", "insights": len(insights)}