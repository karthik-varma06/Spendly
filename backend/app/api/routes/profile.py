from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "currency": current_user.currency,
        "timezone": current_user.timezone,
        "profile_image": current_user.profile_image,
        "created_at": current_user.created_at,
    }
