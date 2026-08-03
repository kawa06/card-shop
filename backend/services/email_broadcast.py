"""Batch email broadcast for announcements and campaign management."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
import models_email
from config import settings
from services.email_delivery import preview_draft, render_template_string, send_templated_email
from services.email_events import get_event_by_template
from services.email_rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS_MINUTES = (5, 15, 60)
BROADCAST_BATCH_SIZE = 50


def _eligible_recipients(db: Session) -> list[models.User]:
    return (
        db.query(models.User)
        .filter(
            models.User.is_verified.is_(True),
            models.User.email.isnot(None),
            models.User.email != "",
        )
        .order_by(models.User.id)
        .all()
    )


def build_announcement_email_preview(
    db: Session,
    announcement: models.Announcement,
) -> dict[str, Any]:
    recipients = _eligible_recipients(db)
    title = announcement.title_ja or announcement.title or ""
    content = announcement.content_ja or announcement.content or ""
    sample = preview_draft(
        db,
        template_key="announcement_broadcast",
        subject=f"【{settings.SITE_NAME}】{title}",
        html_body=(
            "<p>{{name}} 様</p>"
            f"<h2 style=\"margin:16px 0;font-size:18px;\">{title}</h2>"
            "<div>{{content}}</div>"
        ),
        variables={
            "name": "山田 太郎",
            "title": title,
            "content": content,
            "url": f"{settings.FRONTEND_URL or ''}/mypage/announcements/{announcement.id}",
        },
        raw_variable_keys={"content"},
    )
    return {
        "subject": sample["subject"],
        "html": sample["html"],
        "recipient_count": len(recipients),
        "target_description": "メール認証済み会員全員",
        "recipients_sample": [u.email for u in recipients[:5]],
    }


def create_announcement_campaign(
    db: Session,
    announcement: models.Announcement,
    *,
    admin_user_id: int,
    send_mode: str = "immediate",
    scheduled_at: Optional[datetime] = None,
    idempotency_key: Optional[str] = None,
) -> models_email.EmailCampaign:
    if not announcement.send_email:
        raise ValueError("このお知らせはメール配信が有効になっていません")

    if announcement.email_send_status in {"sending", "sent", "scheduled"}:
        raise ValueError("このお知らせは既にメール配信済みまたは予約済みです")

    recipients = _eligible_recipients(db)
    if not recipients:
        raise ValueError("配信対象の会員が見つかりません")

    title = announcement.title_ja or announcement.title or ""
    content = announcement.content_ja or announcement.content or ""
    subject = f"【{settings.SITE_NAME}】{title}"
    html_body = (
        "<p>{{name}} 様</p>"
        f"<h2 style=\"margin:16px 0;font-size:18px;\">{title}</h2>"
        "<div>{{content}}</div>"
    )

    if idempotency_key:
        existing = (
            db.query(models_email.EmailCampaign)
            .filter(models_email.EmailCampaign.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    if not idempotency_key:
        idempotency_key = hashlib.sha256(
            f"announcement:{announcement.id}:{announcement.updated_at}".encode()
        ).hexdigest()[:32]

    campaign = models_email.EmailCampaign(
        template_key="announcement_broadcast",
        subject=subject,
        html_body=html_body,
        reference_type="announcement",
        reference_id=str(announcement.id),
        target_description="メール認証済み会員全員",
        recipient_count=len(recipients),
        status="scheduled" if send_mode == "scheduled" and scheduled_at else "pending",
        send_mode=send_mode,
        scheduled_at=scheduled_at,
        created_by_user_id=admin_user_id,
        idempotency_key=idempotency_key,
    )
    db.add(campaign)
    db.flush()

    announcement.email_campaign_id = campaign.id
    announcement.email_send_status = "scheduled" if send_mode == "scheduled" else "pending"
    announcement.email_scheduled_at = scheduled_at

    if send_mode == "immediate":
        execute_campaign(db, campaign)
    return campaign


def execute_campaign(db: Session, campaign: models_email.EmailCampaign) -> None:
    if campaign.status in {"completed", "cancelled"}:
        return

    campaign.status = "sending"
    campaign.started_at = datetime.utcnow()
    db.flush()

    if campaign.reference_type == "announcement" and campaign.reference_id:
        ann = (
            db.query(models.Announcement)
            .filter(models.Announcement.id == int(campaign.reference_id))
            .first()
        )
        if ann:
            ann.email_send_status = "sending"

    recipients = _eligible_recipients(db)
    success = 0
    failed = 0
    title = ""
    content = ""

    if campaign.reference_type == "announcement" and campaign.reference_id:
        ann = (
            db.query(models.Announcement)
            .filter(models.Announcement.id == int(campaign.reference_id))
            .first()
        )
        if ann:
            title = ann.title_ja or ann.title or ""
            content = ann.content_ja or ann.content or ""

    for user in recipients:
        rl = check_rate_limit("global", limit_key="global_minute")
        if not rl.allowed:
            logger.warning("Global email rate limit hit during campaign %s", campaign.id)
            break

        variables = {
            "name": user.name or user.email,
            "email": user.email,
            "title": title,
            "content": content,
            "url": f"{settings.FRONTEND_URL or ''}/mypage/announcements/{campaign.reference_id or ''}",
        }
        result = send_templated_email(
            db,
            template_key=campaign.template_key,
            to_email=user.email,
            variables=variables,
            reference_type=campaign.reference_type,
            reference_id=campaign.reference_id,
            campaign_id=campaign.id,
            sent_by_user_id=campaign.created_by_user_id,
            fallback_subject=campaign.subject,
            fallback_html=campaign.html_body,
            raw_variable_keys={"content"},
            html_snapshot=True,
        )
        if result.ok:
            success += 1
        else:
            failed += 1

    campaign.success_count = success
    campaign.failed_count = failed
    campaign.recipient_count = len(recipients)
    campaign.completed_at = datetime.utcnow()
    campaign.status = "completed" if failed == 0 else ("completed" if success > 0 else "failed")

    if campaign.reference_type == "announcement" and campaign.reference_id:
        ann = (
            db.query(models.Announcement)
            .filter(models.Announcement.id == int(campaign.reference_id))
            .first()
        )
        if ann:
            ann.email_send_status = "sent" if success > 0 else "failed"

    db.flush()
    logger.info(
        "Campaign %s finished success=%s failed=%s",
        campaign.id,
        success,
        failed,
    )


def retry_failed_sends(db: Session, *, campaign_id: Optional[int] = None) -> int:
    """Retry failed email logs with exponential backoff."""
    now = datetime.utcnow()
    q = db.query(models_email.EmailSendLog).filter(
        models_email.EmailSendLog.status == "failed",
        models_email.EmailSendLog.retry_count < MAX_RETRIES,
        models_email.EmailSendLog.is_test.is_(False),
    )
    if campaign_id:
        q = q.filter(models_email.EmailSendLog.campaign_id == campaign_id)
    else:
        q = q.filter(
            (models_email.EmailSendLog.next_retry_at.is_(None))
            | (models_email.EmailSendLog.next_retry_at <= now)
        )

    logs = q.limit(BROADCAST_BATCH_SIZE).all()
    retried = 0
    for log in logs:
        rl = check_rate_limit(log.recipient, limit_key="recipient")
        if not rl.allowed:
            continue

        event = get_event_by_template(log.template_key or "")
        raw_keys = event.raw_html_variables if event else frozenset()

        variables: dict[str, Any] = {}
        if log.html_body_snapshot:
            html_body = log.html_body_snapshot
            subject = log.subject
        else:
            html_body = "<p>{{content}}</p>"
            subject = log.subject

        result = send_templated_email(
            db,
            template_key=log.template_key or "announcement_broadcast",
            to_email=log.recipient,
            variables=variables,
            reference_type=log.reference_type,
            reference_id=log.reference_id,
            campaign_id=log.campaign_id,
            sent_by_user_id=log.sent_by_user_id,
            fallback_subject=subject,
            fallback_html=html_body,
            raw_variable_keys=set(raw_keys),
            force=True,
        )
        log.retry_count += 1
        if result.ok:
            log.status = "sent"
            log.error_message = None
            log.next_retry_at = None
        else:
            delay_idx = min(log.retry_count - 1, len(RETRY_DELAYS_MINUTES) - 1)
            log.next_retry_at = now + timedelta(minutes=RETRY_DELAYS_MINUTES[delay_idx])
            log.error_message = result.error
        retried += 1
    return retried


def process_due_scheduled_campaigns(db: Session) -> int:
    now = datetime.utcnow()
    due = (
        db.query(models_email.EmailCampaign)
        .filter(
            models_email.EmailCampaign.status == "scheduled",
            models_email.EmailCampaign.scheduled_at <= now,
        )
        .limit(5)
        .all()
    )
    count = 0
    for campaign in due:
        execute_campaign(db, campaign)
        count += 1
    return count
