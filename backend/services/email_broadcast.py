"""Batch email broadcast for announcements and campaign management."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

import models
import models_email
from config import settings
from services.broadcast_audience_registry import (
    DEFAULT_AUDIENCE_KEY,
    parse_audience_params,
    resolve_audience,
)
from services.broadcast_email_registry import (
    DEFAULT_BROADCAST_TEMPLATE_KEY,
    get_broadcast_email_event,
    normalize_template_key,
    resolve_broadcast_template_key,
)
from services.broadcast_email_variables import RAW_BROADCAST_VARIABLE_KEYS, build_broadcast_email_variables
from services.email_delivery import preview_draft, render_template_string, send_templated_email
from services.email_events import get_event_by_template
from services.email_order_layout import BROADCAST_EMAIL_BODY_SKELETON
from services.email_rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS_MINUTES = (5, 15, 60)
BROADCAST_BATCH_SIZE = 50


def _load_announcement(db: Session, announcement_id: int) -> models.Announcement | None:
    return (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .filter(models.Announcement.id == announcement_id)
        .first()
    )


def _announcement_template_key(announcement: models.Announcement) -> str:
    raw = getattr(announcement, "email_template_key", None) or DEFAULT_BROADCAST_TEMPLATE_KEY
    return resolve_broadcast_template_key(raw)


def _announcement_audience_key(announcement: models.Announcement) -> str:
    return getattr(announcement, "email_audience_key", None) or DEFAULT_AUDIENCE_KEY


def _announcement_audience_params(announcement: models.Announcement) -> dict[str, Any]:
    return parse_audience_params(getattr(announcement, "email_audience_params_json", None))


def _resolve_recipients_for_announcement(db: Session, announcement: models.Announcement) -> tuple[list[models.User], str]:
    return resolve_audience(
        db,
        _announcement_audience_key(announcement),
        _announcement_audience_params(announcement),
    )


def _template_display_name(template_key: str) -> str:
    event = get_broadcast_email_event(template_key)
    return event.description if event else template_key


def build_announcement_email_preview(
    db: Session,
    announcement: models.Announcement,
    *,
    audience_key: str | None = None,
    audience_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template_key = _announcement_template_key(announcement)
    aud_key = audience_key or _announcement_audience_key(announcement)
    aud_params = audience_params if audience_params is not None else _announcement_audience_params(announcement)
    recipients, target_label = resolve_audience(db, aud_key, aud_params)

    variables = build_broadcast_email_variables(
        db,
        template_key=template_key,
        user=None,
        announcement=announcement,
        to_email="sample@example.com",
    )
    title = announcement.title_ja or announcement.title or ""
    sample = preview_draft(
        db,
        template_key=template_key,
        subject=f"【{settings.SITE_NAME}】{title}",
        html_body=BROADCAST_EMAIL_BODY_SKELETON,
        variables=variables,
        raw_variable_keys=RAW_BROADCAST_VARIABLE_KEYS,
    )

    image_urls: list[str] = []
    if announcement.thumbnail:
        image_urls.append(announcement.thumbnail)
    for img in announcement.images or []:
        if img.image_url:
            image_urls.append(img.image_url)

    return {
        "subject": sample["subject"],
        "html": sample["html"],
        "text": variables.get("_text_body", ""),
        "recipient_count": len(recipients),
        "target_description": target_label,
        "recipients_sample": [u.email for u in recipients[:5]],
        "template_key": template_key,
        "template_name": _template_display_name(template_key),
        "audience_key": aud_key,
        "image_urls": image_urls,
    }


def create_announcement_campaign(
    db: Session,
    announcement: models.Announcement,
    *,
    admin_user_id: int,
    send_mode: str = "immediate",
    scheduled_at: Optional[datetime] = None,
    idempotency_key: Optional[str] = None,
    audience_key: str | None = None,
    audience_params: dict[str, Any] | None = None,
    template_key: str | None = None,
) -> models_email.EmailCampaign:
    if not announcement.send_email:
        raise ValueError("このお知らせはメール配信が有効になっていません")

    if announcement.email_send_status in {"sending", "sent", "scheduled"}:
        raise ValueError("このお知らせは既にメール配信済みまたは予約済みです")

    tpl_key = resolve_broadcast_template_key(template_key or _announcement_template_key(announcement))
    aud_key = audience_key or _announcement_audience_key(announcement)
    aud_params = audience_params if audience_params is not None else _announcement_audience_params(announcement)
    recipients, target_label = resolve_audience(db, aud_key, aud_params)
    if not recipients:
        raise ValueError("配信対象の会員が見つかりません")

    title = announcement.title_ja or announcement.title or ""
    subject = f"【{settings.SITE_NAME}】{title}"

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

    variables = build_broadcast_email_variables(
        db,
        template_key=tpl_key,
        announcement=announcement,
    )
    fallback_html = render_template_string(
        BROADCAST_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_BROADCAST_VARIABLE_KEYS,
    )

    campaign = models_email.EmailCampaign(
        template_key=tpl_key,
        subject=subject,
        html_body=fallback_html,
        reference_type="announcement",
        reference_id=str(announcement.id),
        target_description=target_label,
        audience_key=aud_key,
        audience_params_json=json.dumps(aud_params, ensure_ascii=False) if aud_params else None,
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


def _campaign_recipients(db: Session, campaign: models_email.EmailCampaign) -> tuple[list[models.User], str]:
    if campaign.audience_key:
        params = parse_audience_params(campaign.audience_params_json)
        return resolve_audience(db, campaign.audience_key, params)
    return resolve_audience(db, DEFAULT_AUDIENCE_KEY, {})


def execute_campaign(db: Session, campaign: models_email.EmailCampaign) -> None:
    if campaign.status in {"completed", "cancelled"}:
        return

    campaign.status = "sending"
    campaign.started_at = datetime.utcnow()
    db.flush()

    announcement: models.Announcement | None = None
    if campaign.reference_type == "announcement" and campaign.reference_id:
        announcement = _load_announcement(db, int(campaign.reference_id))
        if announcement:
            announcement.email_send_status = "sending"

    recipients, _ = _campaign_recipients(db, campaign)
    success = 0
    failed = 0
    template_key = normalize_template_key(campaign.template_key)

    for user in recipients:
        rl = check_rate_limit("global", limit_key="global_minute")
        if not rl.allowed:
            logger.warning("Global email rate limit hit during campaign %s", campaign.id)
            break

        variables = build_broadcast_email_variables(
            db,
            template_key=template_key,
            user=user if user.id else None,
            announcement=announcement,
            to_email=user.email,
        )
        result = send_templated_email(
            db,
            template_key=template_key,
            to_email=user.email,
            variables=variables,
            reference_type=campaign.reference_type,
            reference_id=campaign.reference_id,
            campaign_id=campaign.id,
            sent_by_user_id=campaign.created_by_user_id,
            fallback_subject=campaign.subject,
            fallback_html=campaign.html_body,
            raw_variable_keys=RAW_BROADCAST_VARIABLE_KEYS,
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

    if announcement:
        announcement.email_send_status = "sent" if success > 0 else "failed"

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
        raw_keys = event.raw_html_variables if event else RAW_BROADCAST_VARIABLE_KEYS

        html_body = log.html_body_snapshot or "<p>{{content}}</p>"
        subject = log.subject

        result = send_templated_email(
            db,
            template_key=log.template_key or DEFAULT_BROADCAST_TEMPLATE_KEY,
            to_email=log.recipient,
            variables={},
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
