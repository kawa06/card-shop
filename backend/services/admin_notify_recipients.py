"""Resolve admin notification recipients — extensible routing."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

import models
import models_admin
from admin_emails import is_admin_email
from config import settings
from services.admin_auth import load_permissions
from services.admin_notify_settings import RecipientConfig, get_recipient_config_for_event


@dataclass
class AdminNotifyRecipient:
    email: str
    admin_user_id: int | None = None
    user_id: int | None = None
    name: str | None = None


def _fallback_email() -> str | None:
    return settings.MAIL_REPLY_TO or None


def resolve_admin_notify_recipients(
    db: Session,
    event_key: str,
    *,
    assignee_admin_id: int | None = None,
    override_config: RecipientConfig | None = None,
) -> list[AdminNotifyRecipient]:
    config = override_config or get_recipient_config_for_event(db, event_key)
    mode = config.get("mode", "all_admins")

    if mode == "custom_emails":
        emails = [e.strip() for e in (config.get("custom_emails") or []) if e and "@" in e]
        if not emails:
            fb = _fallback_email()
            return [AdminNotifyRecipient(email=fb)] if fb else []
        return [AdminNotifyRecipient(email=e) for e in emails]

    if mode == "assignee_only":
        if assignee_admin_id:
            admin = (
                db.query(models_admin.AdminUser)
                .options(joinedload(models_admin.AdminUser.user))
                .filter(
                    models_admin.AdminUser.is_active.is_(True),
                    or_(
                        models_admin.AdminUser.id == assignee_admin_id,
                        models_admin.AdminUser.user_id == assignee_admin_id,
                    ),
                )
                .first()
            )
            if admin and admin.user and admin.user.email:
                return [
                    AdminNotifyRecipient(
                        email=admin.user.email,
                        admin_user_id=admin.id,
                        user_id=admin.user_id,
                        name=admin.user.name,
                    )
                ]
        fb = _fallback_email()
        return [AdminNotifyRecipient(email=fb)] if fb else []

    admins = (
        db.query(models_admin.AdminUser)
        .options(joinedload(models_admin.AdminUser.user), joinedload(models_admin.AdminUser.role))
        .filter(models_admin.AdminUser.is_active.is_(True))
        .all()
    )

    if mode == "by_permission":
        required = set(config.get("permission_codes") or [])
        filtered: list[AdminNotifyRecipient] = []
        for admin in admins:
            if not admin.user or not admin.user.email:
                continue
            perms = load_permissions(admin)
            if required and not required.intersection(perms):
                continue
            filtered.append(
                AdminNotifyRecipient(
                    email=admin.user.email,
                    admin_user_id=admin.id,
                    user_id=admin.user_id,
                    name=admin.user.name,
                )
            )
        if filtered:
            return filtered
        fb = _fallback_email()
        return [AdminNotifyRecipient(email=fb)] if fb else []

    # all_admins
    recipients: list[AdminNotifyRecipient] = []
    for admin in admins:
        if admin.user and admin.user.email:
            recipients.append(
                AdminNotifyRecipient(
                    email=admin.user.email,
                    admin_user_id=admin.id,
                    user_id=admin.user_id,
                    name=admin.user.name,
                )
            )
    if recipients:
        return recipients

    # legacy allowlist fallback
    legacy = (
        db.query(models.User)
        .filter(models.User.email.isnot(None))
        .all()
    )
    for user in legacy:
        if user.email and is_admin_email(user.email):
            recipients.append(AdminNotifyRecipient(email=user.email, user_id=user.id, name=user.name))
    if recipients:
        return recipients

    fb = _fallback_email()
    return [AdminNotifyRecipient(email=fb)] if fb else []
