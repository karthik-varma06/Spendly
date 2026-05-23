from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger("ai_finance_tracker.emailer")
settings = get_settings()


def send_email(to_email: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key.strip():
        logger.info("[Emailer] Resend API key is missing; skipping email to %s", to_email)
        return False

    from_email = (settings.resend_from_email or "").strip()
    if not from_email:
        logger.warning("[Emailer] Resend from address is missing; skipping email to %s", to_email)
        return False

    try:
        import resend

        resend.api_key = settings.resend_api_key.strip()
        response = resend.Emails.send(
            {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
        )
        logger.info("[Emailer] Resend accepted email for %s: %s", to_email, response)
        return True
    except Exception as exc:
        logger.warning("[Emailer] Resend failed: %s", exc, exc_info=True)
        return False
