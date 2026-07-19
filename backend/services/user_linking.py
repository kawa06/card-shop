"""Link Clerk users to existing card-shop users (additive, safe linking rules)."""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import bcrypt
from sqlalchemy import func
from sqlalchemy.orm import Session

from admin_emails import ensure_admin, is_admin_email, normalize_email
import models
import models_buyback

logger = logging.getLogger(__name__)


class LinkResult(str, Enum):
    linked_existing = "linked_existing"
    found_by_clerk_id = "found_by_clerk_id"
    created = "created"
    email_ambiguous = "email_ambiguous"
    clerk_id_conflict = "clerk_id_conflict"


@dataclass
class LinkOutcome:
    user: Optional[models.User]
    result: LinkResult
    message: str = ""


def _audit(
    db: Session,
    *,
    action: str,
    clerk_user_id: str,
    user_id: Optional[int],
    details: dict,
) -> None:
    try:
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=user_id,
                action=action,
                entity_type="user_link",
                entity_id=clerk_user_id,
                details_json=json.dumps(details, ensure_ascii=False),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to write buyback audit log: %s", exc)


def resolve_clerk_user(
    db: Session,
    *,
    clerk_user_id: str,
    email: str,
    name: Optional[str] = None,
) -> LinkOutcome:
    """
    Safe linking algorithm (Phase 3):
    1. Exact clerk_user_id match
    2. Single email match when clerk_user_id unset on that row
    3. Never merge duplicates; never overwrite password_hash or existing clerk_user_id
    """
    clerk_user_id = clerk_user_id.strip()
    email = normalize_email(email)

    if not clerk_user_id or not email:
        return LinkOutcome(None, LinkResult.clerk_id_conflict, "Missing clerk_user_id or email")

    by_clerk = (
        db.query(models.User)
        .filter(models.User.clerk_user_id == clerk_user_id)
        .first()
    )
    if by_clerk:
        return LinkOutcome(ensure_admin(by_clerk, db), LinkResult.found_by_clerk_id)

    email_matches = (
        db.query(models.User)
        .filter(func.lower(models.User.email) == email)
        .order_by(models.User.id.asc())
        .all()
    )

    if len(email_matches) > 1:
        _audit(
            db,
            action="link_email_ambiguous",
            clerk_user_id=clerk_user_id,
            user_id=None,
            details={"email": email, "match_count": len(email_matches)},
        )
        return LinkOutcome(
            None,
            LinkResult.email_ambiguous,
            "複数の既存アカウントが同じメールアドレスに紐づいています。管理者にお問い合わせください。",
        )

    if len(email_matches) == 1:
        user = email_matches[0]
        if user.clerk_user_id and user.clerk_user_id != clerk_user_id:
            _audit(
                db,
                action="link_clerk_id_conflict",
                clerk_user_id=clerk_user_id,
                user_id=user.id,
                details={
                    "email": email,
                    "existing_clerk_user_id": user.clerk_user_id,
                },
            )
            return LinkOutcome(
                None,
                LinkResult.clerk_id_conflict,
                "このメールアドレスは別のClerkアカウントに紐づいています。",
            )

        if not user.clerk_user_id:
            user.clerk_user_id = clerk_user_id
            if name and name.strip():
                user.name = name.strip()
            user.is_verified = True
            db.commit()
            db.refresh(user)
            _audit(
                db,
                action="link_email_matched",
                clerk_user_id=clerk_user_id,
                user_id=user.id,
                details={"email": email},
            )
            return LinkOutcome(ensure_admin(user, db), LinkResult.linked_existing)

        return LinkOutcome(ensure_admin(user, db), LinkResult.found_by_clerk_id)

    display_name = (name or "").strip() or email.split("@")[0]
    user = models.User(
        email=email,
        name=display_name,
        password_hash=bcrypt.hashpw(
            secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8"),
        is_admin=is_admin_email(email),
        is_verified=True,
        clerk_user_id=clerk_user_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit(
        db,
        action="link_created_user",
        clerk_user_id=clerk_user_id,
        user_id=user.id,
        details={"email": email},
    )
    return LinkOutcome(user, LinkResult.created)
