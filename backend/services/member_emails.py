"""Transactional emails for member registration, login, password, and security."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_email
from config import settings
from services.email_delivery import render_template_string, send_templated_email
from services.email_order_layout import MEMBER_EMAIL_BODY_SKELETON
from services.member_email_auto_send import should_auto_send
from services.member_email_registry import get_member_email_event, resolve_member_template_key
from services.member_email_variables import RAW_MEMBER_VARIABLE_KEYS, build_member_email_variables
from services.verification import email_configured

logger = logging.getLogger(__name__)


def _notification_already_sent(
    db: Session,
    template_key: str,
    reference_id: str,
    *,
    reference_type: str,
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


def send_member_event_email(
    db: Session,
    event_key: str,
    *,
    user: models.User | None = None,
    to_email: str | None = None,
    force: bool = False,
    send_email: bool | None = None,
    reference_type: str = "user",
    reference_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    region: str | None = None,
    verify_url: str | None = None,
    reset_url: str | None = None,
    expires_at: datetime | None = None,
    fallback_subject: str | None = None,
    extra: dict | None = None,
) -> tuple[bool, str | None]:
    """Central member email dispatcher with dedupe, auto-send prefs, and privacy-safe variables."""
    if not should_auto_send(db, event_key, explicit=send_email):
        return True, None

    event = get_member_email_event(event_key)
    template_key = resolve_member_template_key(event_key)
    recipient = to_email or (user.email if user else None)
    if not recipient:
        return False, "recipient_missing"

    ref_id = reference_id or (str(user.id) if user else recipient)

    if _notification_already_sent(db, template_key, ref_id, reference_type=reference_type) and not force:
        return True, None

    variables = build_member_email_variables(
        db,
        user,
        event_key,
        to_email=recipient,
        ip_address=ip_address,
        user_agent=user_agent,
        region=region,
        verify_url=verify_url,
        reset_url=reset_url,
        expires_at=expires_at,
        extra=extra,
    )
    subject = fallback_subject or f"【{variables.get('shopName', 'KRX TCG')}】{event.description if event else event_key}"
    fallback_html = render_template_string(
        MEMBER_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_MEMBER_VARIABLE_KEYS,
    )

    if not email_configured():
        if settings.DEBUG:
            logger.info("[MEMBER EMAIL MOCK] to=%s event=%s", recipient, event_key)
        return True, None

    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=recipient,
        variables=variables,
        fallback_subject=subject,
        fallback_html=fallback_html,
        raw_variable_keys=RAW_MEMBER_VARIABLE_KEYS,
        reference_type=reference_type,
        reference_id=ref_id,
        force=force,
    )
    if not result.ok:
        logger.error("Member email failed event=%s to=%s error=%s", event_key, recipient, result.error)
    return result.ok, result.error


def notify_register_completed(db: Session, *, user: models.User, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(db, "member_register_completed", user=user, send_email=send_email, reference_id=str(user.id))


def notify_email_verify(
    db: Session,
    *,
    email: str,
    verify_url: str,
    expires_at: datetime | None = None,
    user: models.User | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_member_event_email(
        db,
        "member_email_verify",
        user=user,
        to_email=email,
        verify_url=verify_url,
        expires_at=expires_at,
        reference_type="user",
        reference_id=email,
        force=force,
        send_email=True,
    )


def notify_email_verify_completed(db: Session, *, user: models.User, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(db, "member_email_verify_completed", user=user, send_email=send_email, reference_id=str(user.id))


def notify_login_success(
    db: Session,
    user: models.User,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    send_email: bool | None = None,
    new_device: bool = False,
) -> tuple[bool, str | None]:
    event = "login_new_device" if new_device else "login_success"
    return send_member_event_email(
        db,
        event,
        user=user,
        ip_address=ip,
        user_agent=user_agent,
        send_email=send_email,
        reference_id=f"{user.id}:{datetime.utcnow().strftime('%Y%m%d%H%M')}",
    )


def notify_login_failed(
    db: Session,
    user: models.User,
    *,
    ip: str | None = None,
    repeated: bool = False,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    event = "login_failed_repeated" if repeated else "login_failed"
    return send_member_event_email(
        db,
        event,
        user=user,
        ip_address=ip,
        send_email=send_email,
        reference_id=f"{user.id}:fail:{datetime.utcnow().strftime('%Y%m%d%H')}",
    )


def notify_account_locked(
    db: Session,
    user: models.User,
    *,
    locked_until: datetime | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_member_event_email(
        db,
        "login_account_locked",
        user=user,
        expires_at=locked_until,
        send_email=send_email,
        reference_id=f"{user.id}:locked",
    )


def notify_account_unlocked(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(
        db, "login_account_unlocked", user=user, send_email=send_email, reference_id=f"{user.id}:unlocked"
    )


def notify_2fa_otp_sent(
    db: Session,
    user: models.User,
    *,
    verify_url: str,
    expires_at: datetime,
    challenge_id: int,
    force: bool = True,
) -> tuple[bool, str | None]:
    return send_member_event_email(
        db,
        "security_2fa_otp_sent",
        user=user,
        verify_url=verify_url,
        expires_at=expires_at,
        reference_type="otp_challenge",
        reference_id=str(challenge_id),
        force=force,
        send_email=True,
    )


def notify_password_changed(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(db, "password_changed", user=user, send_email=send_email, reference_id=f"{user.id}:pwd")


def notify_profile_updated(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(db, "member_profile_updated", user=user, send_email=send_email, reference_id=f"{user.id}:profile")


def notify_phone_verify_completed(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(
        db, "member_phone_verify_completed", user=user, send_email=send_email, reference_id=f"{user.id}:phone"
    )


def notify_withdrawal_received(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(
        db, "member_withdrawal_received", user=user, send_email=send_email, reference_id=f"{user.id}:withdraw"
    )


def notify_withdrawal_completed(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(
        db, "member_withdrawal_completed", user=user, send_email=send_email, reference_id=f"{user.id}:withdrawn"
    )


def notify_2fa_enabled(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(db, "security_2fa_enabled", user=user, send_email=send_email, reference_id=f"{user.id}:2fa-on")


def notify_2fa_disabled(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(db, "security_2fa_disabled", user=user, send_email=send_email, reference_id=f"{user.id}:2fa-off")


def notify_password_reset_received(
    db: Session,
    *,
    user: models.User,
    reset_url: str,
    expires_at: datetime | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_member_event_email(
        db,
        "password_reset_received",
        user=user,
        reset_url=reset_url,
        expires_at=expires_at,
        reference_type="user",
        reference_id=f"{user.id}:reset",
        force=force,
        send_email=True,
    )


def notify_password_reset_completed(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(
        db, "password_reset_completed", user=user, send_email=send_email, reference_id=f"{user.id}:reset-done"
    )


def notify_email_change_received(
    db: Session,
    *,
    email: str,
    verify_url: str,
    expires_at: datetime | None = None,
    user: models.User | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_member_event_email(
        db,
        "member_email_change_received",
        user=user,
        to_email=email,
        verify_url=verify_url,
        expires_at=expires_at,
        reference_type="user",
        reference_id=email,
        force=force,
        send_email=True,
    )


def notify_email_change_completed(db: Session, user: models.User, *, send_email: bool | None = None) -> tuple[bool, str | None]:
    return send_member_event_email(
        db, "member_email_change_completed", user=user, send_email=send_email, reference_id=f"{user.id}:email-changed"
    )


def notify_phone_verify(
    db: Session,
    user: models.User,
    *,
    verify_url: str | None = None,
    expires_at: datetime | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_member_event_email(
        db,
        "member_phone_verify",
        user=user,
        verify_url=verify_url,
        expires_at=expires_at,
        reference_type="user",
        reference_id=f"{user.id}:phone-pending",
        force=force,
        send_email=True,
    )


def resend_member_email(db: Session, *, event_key: str, user: models.User, **kwargs) -> tuple[bool, str | None]:
    return send_member_event_email(db, event_key, user=user, force=True, send_email=True, **kwargs)
