"""Admin auth via trusted Vercel proxy (Clerk verified on Next.js)."""

from __future__ import annotations

import os
import secrets
from typing import Optional

import bcrypt
from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from admin_emails import ensure_admin, is_admin_email, normalize_email
import models

INTERNAL_ADMIN_SECRET = (
    os.getenv("ADMIN_PROXY_SECRET")
    or os.getenv("CLERK_SECRET_KEY")
    or os.getenv("AUTH_SYNC_SECRET")
    or "card-shop-internal-admin-v1"
).strip()


def authenticate_internal_admin(request: Request, db: Session) -> Optional[models.User]:
    if not INTERNAL_ADMIN_SECRET:
        return None

    header_secret = (request.headers.get("X-Internal-Admin-Secret") or "").strip()
    email_raw = (request.headers.get("X-Admin-Email") or "").strip()
    if not header_secret or not email_raw:
        return None
    if not secrets.compare_digest(header_secret, INTERNAL_ADMIN_SECRET):
        return None

    email = normalize_email(email_raw)
    if not is_admin_email(email):
        return None

    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if user:
        return ensure_admin(user, db)

    local_part = email.split("@")[0]
    user = models.User(
        email=email,
        name=local_part,
        password_hash=bcrypt.hashpw(
            secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8"),
        is_admin=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
