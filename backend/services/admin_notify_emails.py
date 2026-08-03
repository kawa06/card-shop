"""Admin notification dispatcher — email, in-app, campaign logging."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models_email
from config import settings
from services.email_delivery import render_template_string, send_templated_email
from services.email_order_layout import ADMIN_NOTIFY_EMAIL_BODY_SKELETON
from services.admin_notify_email_registry import get_admin_notify_email_event, resolve_admin_notify_template_key
from services.admin_notify_email_variables import RAW_ADMIN_NOTIFY_VARIABLE_KEYS, build_admin_notify_email_variables
from services.admin_notify_in_app import notify_admins_in_app
from services.admin_notify_recipients import resolve_admin_notify_recipients
from services.admin_notify_settings import get_channel_for_event, should_auto_send_email
from services.verification import email_configured

logger = logging.getLogger(__name__)


def _notification_already_sent(
    db: Session,
    template_key: str,
    reference_id: str,
    *,
    recipient: str,
) -> bool:
    row = (
        db.query(models_email.EmailSendLog)
        .filter(
            models_email.EmailSendLog.template_key == template_key,
            models_email.EmailSendLog.reference_type == "admin_notify",
            models_email.EmailSendLog.reference_id == reference_id,
            models_email.EmailSendLog.recipient == recipient,
            models_email.EmailSendLog.status == "sent",
            models_email.EmailSendLog.is_test.is_(False),
        )
        .first()
    )
    return row is not None


def send_admin_notify_event(
    db: Session,
    event_key: str,
    *,
    reference_type: str | None = None,
    reference_id: str | None = None,
    assignee_admin_id: int | None = None,
    force: bool = False,
    send_email: bool | None = None,
    sent_by_user_id: int | None = None,
    in_app_title: str | None = None,
    in_app_body: str | None = None,
    include_error: bool = False,
    include_log: bool = False,
    error_message: str | None = None,
    log_snippet: str | None = None,
    extra: dict | None = None,
) -> tuple[bool, str | None, int, int]:
    """Returns ok, error, success_count, failed_count."""
    event = get_admin_notify_email_event(event_key)
    template_key = resolve_admin_notify_template_key(event_key)
    channel = get_channel_for_event(db, event_key)
    ref_id = reference_id or f"{event_key}:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    recipients = resolve_admin_notify_recipients(
        db, event_key, assignee_admin_id=assignee_admin_id
    )
    if not recipients:
        return False, "no_recipients", 0, 0

    variables = build_admin_notify_email_variables(
        db,
        event_key,
        include_error=include_error,
        include_log=include_log,
        error_message=error_message,
        log_snippet=log_snippet,
        extra=extra,
    )
    subject = f"【{variables.get('shopName', 'KRX TCG')} 管理】{event.description if event else event_key}"
    fallback_html = render_template_string(
        ADMIN_NOTIFY_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_ADMIN_NOTIFY_VARIABLE_KEYS,
    )

    campaign = models_email.EmailCampaign(
        template_key=template_key,
        subject=subject,
        html_body=fallback_html,
        reference_type=reference_type or "admin_notify",
        reference_id=ref_id,
        target_description=f"admin_notify:{event_key}",
        recipient_count=len(recipients),
        status="running",
        started_at=datetime.utcnow(),
        created_by_user_id=sent_by_user_id,
    )
    db.add(campaign)
    db.flush()

    success_count = 0
    failed_count = 0
    last_error: str | None = None

    admin_ids_for_in_app = [
        r.admin_user_id for r in recipients if r.admin_user_id
    ]

    if channel in ("in_app", "both"):
        notify_admins_in_app(
            db,
            event_key=event_key,
            admin_user_ids=admin_ids_for_in_app,
            title=in_app_title,
            body=in_app_body or variables.get("bodyTitle", ""),
            reference_type=reference_type,
            reference_id=ref_id,
        )

    email_enabled = channel in ("email", "both") and should_auto_send_email(db, event_key, explicit=send_email)

    if email_enabled:
        if not email_configured():
            if settings.DEBUG:
                logger.info("[ADMIN NOTIFY MOCK] event=%s recipients=%s", event_key, len(recipients))
            success_count = len(recipients)
        else:
            for recipient in recipients:
                dedupe_ref = f"{ref_id}:{recipient.email}"
                if _notification_already_sent(db, template_key, dedupe_ref, recipient=recipient.email) and not force:
                    success_count += 1
                    continue
                result = send_templated_email(
                    db,
                    template_key=template_key,
                    to_email=recipient.email,
                    variables=variables,
                    fallback_subject=subject,
                    fallback_html=fallback_html,
                    raw_variable_keys=RAW_ADMIN_NOTIFY_VARIABLE_KEYS,
                    reference_type="admin_notify",
                    reference_id=dedupe_ref,
                    campaign_id=campaign.id,
                    force=force,
                    sent_by_user_id=sent_by_user_id,
                )
                if result.ok:
                    success_count += 1
                else:
                    failed_count += 1
                    last_error = result.error

    elif channel == "in_app":
        success_count = len(admin_ids_for_in_app) or len(recipients)

    campaign.success_count = success_count
    campaign.failed_count = failed_count
    campaign.status = "completed" if failed_count == 0 else ("partial" if success_count else "failed")
    campaign.completed_at = datetime.utcnow()
    if last_error:
        campaign.error_message = last_error

    ok = failed_count == 0 or success_count > 0 or channel == "in_app"
    return ok, last_error, success_count, failed_count


def resend_admin_notify_event(
    db: Session,
    event_key: str,
    **kwargs,
) -> tuple[bool, str | None, int, int]:
    return send_admin_notify_event(db, event_key, force=True, send_email=True, **kwargs)
