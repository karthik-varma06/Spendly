import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.services.ocr import is_tesseract_available, resolve_tesseract_cmd

logger = logging.getLogger("ai_finance_tracker.health")
router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("")
def health():
    db_connected = False
    db_error = None

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_connected = True
    except Exception as exc:
        db_error = str(exc)
        logger.exception("[Health] DB check failed")

    openrouter_configured = bool(settings.openrouter_api_key.strip())
    tesseract_ok = is_tesseract_available()

    # Backward-compatible fields for older frontend code
    result = {
        "status": "ok" if db_connected else "degraded",
        "database_connected": db_connected,
        "database_error": db_error,
        "openrouter_connected": openrouter_configured,
        "openrouter_configured": openrouter_configured,
        "openrouter_error": None if openrouter_configured else "OPENROUTER_API_KEY missing",
        "openrouter_sample": None,
        "openrouter_vision_model": settings.openrouter_vision_model,
        "openrouter_chat_model": settings.openrouter_chat_model,
        "openrouter_model": settings.openrouter_vision_model,  # alias for old UI code
        "ocr_engine": "Tesseract" if tesseract_ok else "Unavailable",
        "tesseract_cmd": resolve_tesseract_cmd(),
        "upload_dir": settings.upload_dir,
    }

    print("[HEALTH]", result)
    return result