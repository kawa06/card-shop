"""Transactional emails for customer inquiries."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_email
from config import settings
from services.email_delivery import preview_draft, render_template_string, send_templated_email
from services.email_order_layout import INQUIRY_EMAIL_BODY_SKELETON
from services.inquiry_email_auto_send import should_auto_send
from services.inquiry_email_registry import (
    get_inquiry_email_event,
    resolve_event_for_status,
    resolve_inquiry_template_key,
)
from services.inquiry_email_variables import RAW_INQUIRY_VARIABLE_KEYS, build_inquiry_email_variables
from services.verification import email_configured

logger = logging.getLogger(__name__)


def _notification_already_sent(
    db: Session,
    template_key: str,
    reference_id: str,
    *,
    reference_type: str = "inquiry",
) -> bool:
    row = (
        db.query(models_email.EmailSendLog)
        .filter(
            models_email.EmailSendLog.template_key == template_key,
            models_email.EmailSendLog.reference_type == reference_type,
            models_email.EmailSendLog.reference_id == str(reference_id),
            models_email.EmailSendLog.status == "sent",
            models_email.EmailSendLog.is_test.is_(False),
        )
        .first()
    )
    return row is not None


def _attachment_meta(attachments: list[models.InquiryAttachment] | None) -> list[dict]:
    if not attachments:
        return []
    return [
        {"filename": a.original_filename, "size": a.file_size or 0}
        for a in attachments
    ]


def send_inquiry_event_email(
    db: Session,
    event_key: str,
    *,
    inquiry: models.Inquiry,
    user: models.User | None = None,
    admin: models.User | None = None,
    to_email: str | None = None,
    reply_text: str | None = None,
    include_inquiry_content: bool = False,
    include_reply_content: bool = False,
    attachments: list[models.InquiryAttachment] | None = None,
    force: bool = False,
    send_email: bool | None = None,
    reference_suffix: str = "",
    sent_by_user_id: int | None = None,
) -> tuple[bool, str | None]:
    if not should_auto_send(db, event_key, explicit=send_email):
        return True, None

    event = get_inquiry_email_event(event_key)
    template_key = resolve_inquiry_template_key(event_key)
    recipient = to_email or inquiry.reply_email
    if not recipient:
        return False, "recipient_missing"

    ref_id = f"{inquiry.id}{reference_suffix}"

    if _notification_already_sent(db, template_key, ref_id) and not force:
        return True, None

    variables = build_inquiry_email_variables(
        db,
        inquiry,
        event_key,
        user=user or inquiry.user,
        admin=admin,
        to_email=recipient,
        reply_text=reply_text,
        include_inquiry_content=include_inquiry_content,
        include_reply_content=include_reply_content,
        attachments=_attachment_meta(attachments),
    )
    subject = f"【{variables.get('shopName', 'KRX TCG')}】{event.description if event else event_key}"
    fallback_html = render_template_string(
        INQUIRY_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_INQUIRY_VARIABLE_KEYS,
    )

    if not email_configured():
        if settings.DEBUG:
            logger.info("[INQUIRY EMAIL MOCK] to=%s event=%s", recipient, event_key)
        return True, None

    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=recipient,
        variables=variables,
        fallback_subject=subject,
        fallback_html=fallback_html,
        raw_variable_keys=RAW_INQUIRY_VARIABLE_KEYS,
        reference_type="inquiry",
        reference_id=ref_id,
        force=force,
        sent_by_user_id=sent_by_user_id,
    )
    if not result.ok:
        logger.error("Inquiry email failed event=%s inquiry=%s error=%s", event_key, inquiry.id, result.error)
    return result.ok, result.error


def preview_inquiry_email(
    db: Session,
    *,
    inquiry: models.Inquiry,
    event_key: str,
    user: models.User | None = None,
    admin: models.User | None = None,
    reply_text: str | None = None,
    include_reply_content: bool = False,
    attachments: list[models.InquiryAttachment] | None = None,
    force_dark: bool = False,
) -> dict:
    template_key = resolve_inquiry_template_key(event_key)
    variables = build_inquiry_email_variables(
        db,
        inquiry,
        event_key,
        user=user or inquiry.user,
        admin=admin,
        reply_text=reply_text,
        include_reply_content=include_reply_content,
        attachments=_attachment_meta(attachments),
    )
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key, models_email.EmailTemplate.is_active.is_(True))
        .first()
    )
    subject = tpl.subject if tpl else f"【{variables.get('shopName', 'KRX TCG')}】プレビュー"
    html_body = tpl.html_body if tpl else INQUIRY_EMAIL_BODY_SKELETON
    preheader = tpl.preheader if tpl else ""
    return preview_draft(
        db,
        template_key=template_key,
        subject=subject,
        html_body=html_body,
        preheader=preheader or "",
        variables=variables,
        raw_variable_keys=RAW_INQUIRY_VARIABLE_KEYS,
        force_dark=force_dark,
    )


def resend_inquiry_email(
    db: Session,
    *,
    event_key: str,
    inquiry: models.Inquiry,
    admin: models.User | None = None,
    reply_text: str | None = None,
    include_reply_content: bool = False,
    sent_by_user_id: int | None = None,
) -> tuple[bool, str | None]:
    return send_inquiry_event_email(
        db,
        event_key,
        inquiry=inquiry,
        admin=admin,
        reply_text=reply_text,
        include_reply_content=include_reply_content,
        force=True,
        send_email=True,
        reference_suffix=f":resend:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        sent_by_user_id=sent_by_user_id,
    )


def notify_inquiry_received(db: Session, inquiry: models.Inquiry, user: models.User) -> None:
    send_inquiry_event_email(
        db,
        "inquiry_received",
        inquiry=inquiry,
        user=user,
        reference_suffix=":received",
    )


def notify_admin_new_inquiry(
    db: Session, inquiry: models.Inquiry, user: models.User, first_message: str
) -> None:
    from services.admin_notify_emails import send_admin_notify_event

    base = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""
    send_admin_notify_event(
        db,
        "admin_notify_inquiry_new",
        reference_type="inquiry",
        reference_id=str(inquiry.id),
        assignee_admin_id=inquiry.assigned_admin_id,
        extra={
            "inquiryNo": inquiry.inquiry_number,
            "userName": user.name or "お客",
            "url": f"{base}/admin/inquiries/{inquiry.id}" if base else "",
        },
    )


def notify_customer_admin_reply(
    db: Session,
    inquiry: models.Inquiry,
    reply_text: str,
    *,
    admin: models.User | None = None,
    email_template_key: str | None = None,
    send_email: bool | None = None,
    sent_by_user_id: int | None = None,
) -> tuple[bool, str | None]:
    event_key = resolve_event_for_status(inquiry.status, explicit_template_key=email_template_key) or "inquiry_admin_reply"
    return send_inquiry_event_email(
        db,
        event_key,
        inquiry=inquiry,
        admin=admin,
        reply_text=reply_text,
        include_reply_content=True,
        send_email=send_email,
        reference_suffix=f":reply:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        sent_by_user_id=sent_by_user_id,
    )


def notify_admin_customer_reply(
    db: Session, inquiry: models.Inquiry, user: models.User, reply_text: str
) -> None:
    from services.admin_notify_emails import send_admin_notify_event

    base = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""
    send_admin_notify_event(
        db,
        "admin_notify_inquiry_reply_pending",
        reference_type="inquiry",
        reference_id=f"{inquiry.id}:customer-reply",
        assignee_admin_id=inquiry.assigned_admin_id,
        extra={
            "inquiryNo": inquiry.inquiry_number,
            "userName": user.name or "お客",
            "assignee": inquiry.assigned_admin.name if inquiry.assigned_admin else "—",
            "url": f"{base}/admin/inquiries/{inquiry.id}" if base else "",
        },
    )


def notify_customer_inquiry_resolved(
    db: Session,
    inquiry: models.Inquiry,
    note: str | None = None,
    *,
    admin: models.User | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_inquiry_event_email(
        db,
        "inquiry_resolved",
        inquiry=inquiry,
        admin=admin,
        reply_text=note,
        include_reply_content=bool(note),
        send_email=send_email,
        reference_suffix=":resolved",
    )


def notify_customer_inquiry_closed(
    db: Session,
    inquiry: models.Inquiry,
    note: str | None = None,
    *,
    admin: models.User | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_inquiry_event_email(
        db,
        "inquiry_closed",
        inquiry=inquiry,
        admin=admin,
        reply_text=note,
        include_reply_content=bool(note),
        send_email=send_email,
        reference_suffix=":closed",
    )


def notify_inquiry_attachment_received(
    db: Session,
    inquiry: models.Inquiry,
    attachments: list[models.InquiryAttachment],
    *,
    user: models.User | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_inquiry_event_email(
        db,
        "inquiry_attachment_received",
        inquiry=inquiry,
        user=user,
        attachments=attachments,
        send_email=send_email,
        reference_suffix=f":attach:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
    )


def notify_inquiry_status_change(
    db: Session,
    inquiry: models.Inquiry,
    *,
    old_status: str,
    new_status: str,
    reply_text: str | None = None,
    admin: models.User | None = None,
    email_template_key: str | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    if new_status == old_status:
        return True, None

    if new_status in ("resolved", "closed"):
        if new_status == "resolved":
            return notify_customer_inquiry_resolved(
                db, inquiry, reply_text, admin=admin, send_email=send_email
            )
        return notify_customer_inquiry_closed(
            db, inquiry, reply_text, admin=admin, send_email=send_email
        )

    if new_status in ("waiting_admin", "waiting_customer", "in_progress") and old_status in ("resolved", "closed"):
        return send_inquiry_event_email(
            db,
            "inquiry_reopened",
            inquiry=inquiry,
            admin=admin,
            send_email=send_email,
            reference_suffix=":reopened",
        )

    event_key = resolve_event_for_status(new_status, explicit_template_key=email_template_key)
    if not event_key:
        return True, None

    return send_inquiry_event_email(
        db,
        event_key,
        inquiry=inquiry,
        admin=admin,
        reply_text=reply_text,
        include_reply_content=bool(reply_text),
        send_email=send_email,
        reference_suffix=f":status:{new_status}",
    )
