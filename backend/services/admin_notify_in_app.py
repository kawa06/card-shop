"""In-app admin notifications."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import models_email
from services.admin_notify_email_registry import get_admin_notify_email_event


def create_admin_in_app_notification(
    db: Session,
    *,
    admin_user_id: int,
    event_key: str,
    title: str,
    body: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> models_email.AdminInAppNotification:
    row = models_email.AdminInAppNotification(
        admin_user_id=admin_user_id,
        event_key=event_key,
        title=title[:255],
        body=body[:2000],
        reference_type=reference_type,
        reference_id=reference_id,
        is_read=False,
    )
    db.add(row)
    db.flush()
    return row


def notify_admins_in_app(
    db: Session,
    *,
    event_key: str,
    admin_user_ids: list[int],
    title: str | None = None,
    body: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> int:
    event = get_admin_notify_email_event(event_key)
    default_title = event.description if event else event_key
    safe_title = title or default_title
    safe_body = (body or default_title)[:2000]
    count = 0
    for admin_id in admin_user_ids:
        if not admin_id:
            continue
        create_admin_in_app_notification(
            db,
            admin_user_id=admin_id,
            event_key=event_key,
            title=safe_title,
            body=safe_body,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        count += 1
    return count


def list_admin_notifications(
    db: Session,
    admin_user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[models_email.AdminInAppNotification]:
    q = (
        db.query(models_email.AdminInAppNotification)
        .filter(models_email.AdminInAppNotification.admin_user_id == admin_user_id)
        .order_by(models_email.AdminInAppNotification.created_at.desc())
    )
    if unread_only:
        q = q.filter(models_email.AdminInAppNotification.is_read.is_(False))
    return q.limit(limit).all()


def mark_notification_read(db: Session, notification_id: int, admin_user_id: int) -> bool:
    row = (
        db.query(models_email.AdminInAppNotification)
        .filter(
            models_email.AdminInAppNotification.id == notification_id,
            models_email.AdminInAppNotification.admin_user_id == admin_user_id,
        )
        .first()
    )
    if not row:
        return False
    row.is_read = True
    row.read_at = datetime.utcnow()
    return True


def count_unread_notifications(db: Session, admin_user_id: int) -> int:
    return (
        db.query(models_email.AdminInAppNotification)
        .filter(
            models_email.AdminInAppNotification.admin_user_id == admin_user_id,
            models_email.AdminInAppNotification.is_read.is_(False),
        )
        .count()
    )
