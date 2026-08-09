"""User notification settings helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models_notifications

CATEGORIES = ("order", "shipping", "appraisal", "live", "auction", "campaign")


def get_or_create_settings(db: Session, user_id: int) -> models_notifications.UserNotificationSettings:
    row = (
        db.query(models_notifications.UserNotificationSettings)
        .filter(models_notifications.UserNotificationSettings.user_id == user_id)
        .first()
    )
    if row:
        return row
    row = models_notifications.UserNotificationSettings(user_id=user_id)
    db.add(row)
    db.flush()
    return row


def update_settings(
    db: Session,
    user_id: int,
    **fields,
) -> models_notifications.UserNotificationSettings:
    row = get_or_create_settings(db, user_id)
    allowed = {
        "in_app_enabled",
        "email_enabled",
        "order_in_app",
        "order_email",
        "shipping_in_app",
        "shipping_email",
        "appraisal_in_app",
        "appraisal_email",
        "live_in_app",
        "live_email",
        "auction_in_app",
        "auction_email",
        "campaign_in_app",
        "campaign_email",
    }
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(row, key, bool(value))
    row.updated_at = datetime.utcnow()
    db.flush()
    return row


def allows_in_app(settings: Optional[models_notifications.UserNotificationSettings], category: str) -> bool:
    if settings is None:
        return True
    if not settings.in_app_enabled:
        return False
    attr = f"{category}_in_app"
    if hasattr(settings, attr):
        return bool(getattr(settings, attr))
    return True


def allows_email(settings: Optional[models_notifications.UserNotificationSettings], category: str) -> bool:
    if settings is None:
        return True
    if not settings.email_enabled:
        return False
    attr = f"{category}_email"
    if hasattr(settings, attr):
        return bool(getattr(settings, attr))
    return True
