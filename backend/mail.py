import logging

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from config import settings
from services.member_emails import notify_email_verify

logger = logging.getLogger(__name__)

EMAIL_VERIFY_EXPIRE_HOURS = 24


async def send_verification_email(db: Session, email: str, token: str) -> tuple[bool, str | None]:
    verification_url = f"{settings.FRONTEND_URL.rstrip('/')}/verify/{token}"
    expires_at = datetime.utcnow() + timedelta(hours=EMAIL_VERIFY_EXPIRE_HOURS)
    ok, err = notify_email_verify(
        db,
        email=email,
        verify_url=verification_url,
        expires_at=expires_at,
        force=True,
    )
    if ok:
        logger.info("Email sent successfully to %s", email)
    return ok, err
