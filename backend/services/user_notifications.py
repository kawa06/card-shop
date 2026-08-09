"""Core user notification create/list/read with dedupe and failure isolation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import models_notifications
from services.notification_settings import allows_email, allows_in_app, get_or_create_settings

logger = logging.getLogger(__name__)


def _to_out(row: models_notifications.UserNotification) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "category": row.category,
        "title": row.title,
        "body": row.body,
        "related_entity_type": row.related_entity_type,
        "related_entity_id": row.related_entity_id,
        "action_url": row.action_url,
        "priority": row.priority or "normal",
        "channel": row.channel or "in_app",
        "is_read": bool(row.is_read),
        "read_at": row.read_at,
        "email_status": row.email_status,
        "created_at": row.created_at,
    }


def create_user_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    body: str,
    dedupe_key: str,
    category: str = "order",
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str | int] = None,
    action_url: Optional[str] = None,
    priority: str = "normal",
    metadata: Optional[dict[str, Any]] = None,
    send_email: bool = False,
    email_sender: Optional[Any] = None,
) -> Optional[models_notifications.UserNotification]:
    """
    Create an in-app notification if settings allow.
    Never raises to callers — failures are logged.
    Email is optional and isolated; existing transactional emails should not use this path.
    """
    try:
        settings = get_or_create_settings(db, user_id)
        if not allows_in_app(settings, category):
            return None

        existing = (
            db.query(models_notifications.UserNotification)
            .filter(models_notifications.UserNotification.dedupe_key == dedupe_key)
            .first()
        )
        if existing:
            return existing

        entity_id = str(related_entity_id) if related_entity_id is not None else None
        row = models_notifications.UserNotification(
            user_id=user_id,
            type=type,
            category=category,
            title=title,
            body=body,
            related_entity_type=related_entity_type,
            related_entity_id=entity_id,
            action_url=action_url,
            priority=priority,
            channel="in_app",
            is_read=False,
            metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
            dedupe_key=dedupe_key,
            email_status="none",
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            return (
                db.query(models_notifications.UserNotification)
                .filter(models_notifications.UserNotification.dedupe_key == dedupe_key)
                .first()
            )

        if send_email and email_sender is not None and allows_email(settings, category):
            try:
                email_sender()
                row.email_status = "sent"
                row.sent_at = datetime.utcnow()
            except Exception:
                logger.exception("notification email failed user=%s type=%s", user_id, type)
                row.email_status = "failed"
            db.flush()
        elif send_email and not allows_email(settings, category):
            row.email_status = "skipped"
            db.flush()

        return row
    except Exception:
        logger.exception("create_user_notification failed user=%s type=%s", user_id, type)
        return None


def safe_notify(db: Session, **kwargs) -> Optional[models_notifications.UserNotification]:
    """Alias that never raises."""
    try:
        return create_user_notification(db, **kwargs)
    except Exception:
        logger.exception("safe_notify failed")
        return None


def list_notifications(
    db: Session,
    *,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[models_notifications.UserNotification], int, int]:
    q = db.query(models_notifications.UserNotification).filter(
        models_notifications.UserNotification.user_id == user_id
    )
    if unread_only:
        q = q.filter(models_notifications.UserNotification.is_read.is_(False))
    total = q.count()
    items = (
        q.order_by(models_notifications.UserNotification.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    unread = unread_count(db, user_id=user_id)
    return items, total, unread


def unread_count(db: Session, *, user_id: int) -> int:
    return (
        db.query(models_notifications.UserNotification)
        .filter(
            models_notifications.UserNotification.user_id == user_id,
            models_notifications.UserNotification.is_read.is_(False),
        )
        .count()
    )


def mark_read(
    db: Session,
    *,
    user_id: int,
    notification_id: int,
) -> Optional[models_notifications.UserNotification]:
    row = (
        db.query(models_notifications.UserNotification)
        .filter(
            models_notifications.UserNotification.id == notification_id,
            models_notifications.UserNotification.user_id == user_id,
        )
        .first()
    )
    if not row:
        return None
    if not row.is_read:
        row.is_read = True
        row.read_at = datetime.utcnow()
        db.flush()
    return row


def mark_all_read(db: Session, *, user_id: int) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(models_notifications.UserNotification)
        .filter(
            models_notifications.UserNotification.user_id == user_id,
            models_notifications.UserNotification.is_read.is_(False),
        )
        .all()
    )
    for row in rows:
        row.is_read = True
        row.read_at = now
    db.flush()
    return len(rows)


def get_owned_notification(
    db: Session,
    *,
    user_id: int,
    notification_id: int,
) -> Optional[models_notifications.UserNotification]:
    return (
        db.query(models_notifications.UserNotification)
        .filter(
            models_notifications.UserNotification.id == notification_id,
            models_notifications.UserNotification.user_id == user_id,
        )
        .first()
    )


def fanout_to_all_users(
    db: Session,
    *,
    type: str,
    title: str,
    body: str,
    category: str = "campaign",
    action_url: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str | int] = None,
    dedupe_prefix: str,
    limit_users: Optional[int] = None,
) -> int:
    """Create notifications for users. Failures per-user are isolated."""
    q = db.query(models.User.id).order_by(models.User.id.asc())
    if limit_users:
        q = q.limit(limit_users)
    created = 0
    for (uid,) in q.all():
        key = f"{dedupe_prefix}:user:{uid}"
        row = create_user_notification(
            db,
            user_id=int(uid),
            type=type,
            title=title,
            body=body,
            category=category,
            action_url=action_url,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            dedupe_key=key,
        )
        if row:
            created += 1
    return created
