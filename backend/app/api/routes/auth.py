from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_db
from app.core.config import get_settings
from app.models.session import SessionModel
from app.models.user import User
from app.models.user_setting import UserSetting
from app.schemas.auth import AuthMeResponse, LoginRequest, RegisterRequest, UserOut
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")


@router.post("/register", response_model=UserOut)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        user = User(
            id=str(uuid4()),
            full_name=payload.full_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            currency="INR",
            timezone="Asia/Kolkata",
            is_verified=False,
            is_active=True,
        )
        db.add(user)
        db.flush()

        db.add(
            UserSetting(
                id=str(uuid4()),
                user_id=str(user.id),
            )
        )

        token = create_access_token(subject=str(user.id), extra={"email": user.email})

        db.add(
            SessionModel(
                id=str(uuid4()),
                user_id=str(user.id),
                refresh_token=token,
                ip_address=None,
                user_agent=None,
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=settings.access_token_expire_minutes),
                is_revoked=False,
            )
        )

        db.commit()
        db.refresh(user)

        set_auth_cookie(response, token)
        return UserOut.model_validate(user)

    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {exc}")


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == payload.email))

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(subject=str(user.id), extra={"email": user.email})

    db.add(
        SessionModel(
            id=str(uuid4()),
            user_id=str(user.id),
            refresh_token=token,
            ip_address=None,
            user_agent=None,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.access_token_expire_minutes),
            is_revoked=False,
        )
    )
    db.commit()

    set_auth_cookie(response, token)
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")

    if token:
        session = db.scalar(select(SessionModel).where(SessionModel.refresh_token == token))
        if session:
            session.is_revoked = True
            db.commit()

    clear_auth_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=AuthMeResponse)
def me(current_user: User | None = Depends(get_current_user_optional)):
    if not current_user:
        return AuthMeResponse(authenticated=False, user=None)

    return AuthMeResponse(
        authenticated=True,
        user=UserOut.model_validate(current_user),
    )