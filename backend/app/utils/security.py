from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.hash import pbkdf2_sha256

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    return pbkdf2_sha256.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return pbkdf2_sha256.verify(plain_password, password_hash)
    except Exception:
        return False


def create_access_token(subject, extra=None):
    payload = {
        "sub": str(subject),
        **(extra or {}),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])