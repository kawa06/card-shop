"""Admin auth via trusted Vercel proxy (Clerk verified on Next.js)."""

from __future__ import annotations

import os
import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from admin_emails import normalize_email
import models
from services.admin_auth import get_admin_user_for_user

ADMIN_PROXY_MAX_SKEW_SECONDS = 60


def _admin_proxy_secret() -> str:
    """Return the configured proxy secret. Missing configuration always disables proxy auth."""
    return (os.getenv("ADMIN_PROXY_SECRET") or "").strip()


def build_admin_proxy_signature(*, secret: str, email: str, timestamp: str) -> str:
    message = f"{timestamp}\n{normalize_email(email)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def authenticate_internal_admin(request: Request, db: Session) -> Optional[models.User]:
    secret = _admin_proxy_secret()
    if not secret:
        return None

    email_raw = (request.headers.get("X-Admin-Email") or "").strip()
    timestamp = (request.headers.get("X-Admin-Timestamp") or "").strip()
    signature = (request.headers.get("X-Admin-Signature") or "").strip()
    if not email_raw or not timestamp or not signature:
        return None

    try:
        signed_at = int(timestamp)
    except ValueError:
        return None
    if abs(int(time.time()) - signed_at) > ADMIN_PROXY_MAX_SKEW_SECONDS:
        return None

    expected = build_admin_proxy_signature(
        secret=secret,
        email=email_raw,
        timestamp=timestamp,
    )
    if not secrets.compare_digest(signature, expected):
        return None

    email = normalize_email(email_raw)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if user is None:
        return None

    # Allow inactive admins through proxy auth only on login so the route can return 403.
    is_login_request = request.url.path.rstrip("/") == "/api/admin/security/session/login"
    if get_admin_user_for_user(db, user, require_active=not is_login_request) is None:
        return None

    return user
