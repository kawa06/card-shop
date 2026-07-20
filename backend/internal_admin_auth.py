"""Admin auth via trusted Vercel proxy (Clerk verified on Next.js)."""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from admin_emails import ensure_admin, normalize_email
import models
import models_admin

# Must match frontend/app/api/admin/[...path]/route.ts (do not fall back to AUTH_SYNC_SECRET).
INTERNAL_ADMIN_SECRET = (
    os.getenv("ADMIN_PROXY_SECRET") or "card-shop-internal-admin-v1"
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
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if user is None:
        return None

    admin_user = (
        db.query(models_admin.AdminUser)
        .filter(models_admin.AdminUser.user_id == user.id)
        .first()
    )
    if admin_user is None:
        return None

    user = ensure_admin(user, db)
    return user
