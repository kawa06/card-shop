"""Transactional emails for identity verification and guardian consent."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.email_delivery import render_template_string, send_templated_email
from services.email_order_layout import KYC_EMAIL_BODY_SKELETON
from services.kyc_email_auto_send import should_auto_send
from services.kyc_email_registry import (
    get_kyc_email_event,
    resolve_kyc_template_key,
)
from services.kyc_email_variables import (
    RAW_KYC_VARIABLE_KEYS,
    build_guardian_email_variables,
    build_identity_email_variables,
)
from services.verification import email_configured

logger = logging.getLogger(__name__)


def kyc_notification_already_sent(
    db: Session,
    template_key: str,
    reference_id: str,
    *,
    reference_type: str,
) -> bool:
    row = (
        db.query(models_buyback.NotificationDelivery)
        .filter(
            models_buyback.NotificationDelivery.template_key == template_key,
            models_buyback.NotificationDelivery.reference_type == reference_type,
            models_buyback.NotificationDelivery.reference_id == str(reference_id),
            models_buyback.NotificationDelivery.status == "sent",
        )
        .first()
    )
    return row is not None


def _record_delivery(
    db: Session,
    *,
    user_id: int | None,
    template_key: str,
    reference_id: str,
    ok: bool,
    error: str | None = None,
    reference_type: str,
) -> None:
    try:
        db.add(
            models_buyback.NotificationDelivery(
                user_id=user_id,
                channel="email",
                template_key=template_key,
                reference_type=reference_type,
                reference_id=reference_id,
                status="sent" if ok else "failed",
                error_message=error,
                sent_at=datetime.utcnow() if ok else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record KYC email delivery")


def send_kyc_event_email(
    db: Session,
    event_key: str,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification | None = None,
    consent: models_buyback.GuardianConsent | None = None,
    raw_token: str | None = None,
    reason: str | None = None,
    force: bool = False,
    send_email: bool | None = None,
    to_email: str | None = None,
    recipient_name: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> tuple[bool, str | None]:
    """Central KYC email dispatcher with dedupe, auto-send prefs, and privacy-safe variables."""
    if not should_auto_send(db, event_key, explicit=send_email):
        return True, None

    event = get_kyc_email_event(event_key)
    template_key = resolve_kyc_template_key(event_key)

    if consent is not None:
        ref_type = reference_type or "guardian_consent"
        ref_id = reference_id or str(consent.id)
        recipient = to_email or consent.guardian_email
        variables = build_guardian_email_variables(
            db, consent, user, event_key, raw_token=raw_token, recipient_name=recipient_name, reason=reason
        )
        user_id = user.id
    elif verification is not None:
        ref_type = reference_type or "identity_verification"
        ref_id = reference_id or str(verification.id)
        recipient = to_email or user.email
        variables = build_identity_email_variables(
            db, user, verification, event_key, reason=reason, consent_url=None
        )
        user_id = user.id
    else:
        ref_type = reference_type or "kyc"
        ref_id = reference_id or str(user.id)
        recipient = to_email or user.email
        variables = {
            "name": user.name or "お客",
            "ユーザー名": user.name or "お客",
            "authNo": f"KYC-{user.id:06d}",
            "bodyTitle": "（本文タイトル）",
            "bodyDescription": "（本文説明を入力してください）",
            "shopName": settings.SITE_NAME or "KRX TCG",
        }
        user_id = user.id

    if not recipient:
        return False, "recipient_missing"

    if kyc_notification_already_sent(db, template_key, ref_id, reference_type=ref_type) and not force:
        return True, None

    subject = f"【{variables.get('shopName', 'KRX TCG')}】{event.description if event else event_key}"
    fallback_html = render_template_string(
        KYC_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_KYC_VARIABLE_KEYS,
    )

    if not email_configured():
        if settings.DEBUG:
            logger.info("[KYC EMAIL MOCK] to=%s event=%s", recipient, event_key)
            _record_delivery(
                db,
                user_id=user_id,
                template_key=template_key,
                reference_id=ref_id,
                ok=True,
                reference_type=ref_type,
            )
        return True, None

    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=recipient,
        variables=variables,
        fallback_subject=subject,
        fallback_html=fallback_html,
        raw_variable_keys=RAW_KYC_VARIABLE_KEYS,
        reference_type=ref_type,
        reference_id=ref_id,
        force=force,
    )
    _record_delivery(
        db,
        user_id=user_id,
        template_key=template_key,
        reference_id=ref_id,
        ok=result.ok,
        error=result.error,
        reference_type=ref_type,
    )
    if not result.ok:
        logger.error(
            "KYC email failed event=%s to=%s error=%s",
            event_key,
            recipient,
            result.error,
        )
    return result.ok, result.error


def notify_identity_received(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_received",
        user=user,
        verification=verification,
        send_email=send_email,
        force=force,
    )


def notify_identity_upload_completed(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_upload_completed",
        user=user,
        verification=verification,
        send_email=send_email,
        force=force,
    )


def notify_identity_review_started(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_review_started",
        user=user,
        verification=verification,
        send_email=send_email,
        force=force,
    )


def notify_identity_approved(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_approved",
        user=user,
        verification=verification,
        send_email=send_email,
        force=force,
    )


def notify_identity_rejected(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    reason: str,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_rejected",
        user=user,
        verification=verification,
        reason=reason,
        send_email=send_email,
        force=force,
    )


def notify_identity_returned(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    reason: str,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_returned",
        user=user,
        verification=verification,
        reason=reason,
        send_email=send_email,
        force=force,
    )


def notify_identity_resubmit_requested(
    db: Session,
    *,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    reason: str,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_identity_resubmit_requested",
        user=user,
        verification=verification,
        reason=reason,
        send_email=send_email,
        force=force,
    )


def notify_guardian_consent_requested(
    db: Session,
    consent: models_buyback.GuardianConsent,
    user: models.User,
    raw_token: str,
    *,
    send_email: bool | None = None,
    force: bool = True,
) -> tuple[bool, str | None, str | None, str | None]:
    """Returns ok, technical_error, error_code, user_message."""
    if not email_configured():
        return (
            False,
            "RESEND_API_KEY is not configured",
            "mail_not_configured",
            "メール送信が設定されていません。ショップ管理者へお問い合わせください。",
        )

    ok, err = send_kyc_event_email(
        db,
        "kyc_guardian_consent_requested",
        user=user,
        consent=consent,
        raw_token=raw_token,
        recipient_name="保護者",
        send_email=send_email if send_email is not None else True,
        force=force,
        to_email=consent.guardian_email,
    )
    if not ok:
        return (
            False,
            err,
            "mail_send_failed",
            "メールの送信に失敗しました。メールアドレスを確認して再度お試しください。",
        )
    return ok, err, None, None


def notify_guardian_consent_received(
    db: Session,
    *,
    user: models.User,
    consent: models_buyback.GuardianConsent,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_guardian_consent_received",
        user=user,
        consent=consent,
        send_email=send_email,
        force=force,
    )


def notify_guardian_consent_completed(
    db: Session,
    *,
    user: models.User,
    consent: models_buyback.GuardianConsent,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_guardian_consent_completed",
        user=user,
        consent=consent,
        send_email=send_email,
        force=force,
    )


def notify_guardian_identity_upload_completed(
    db: Session,
    *,
    user: models.User,
    consent: models_buyback.GuardianConsent,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        "kyc_guardian_identity_upload_completed",
        user=user,
        consent=consent,
        send_email=send_email,
        force=force,
    )


def resend_kyc_email(
    db: Session,
    *,
    event_key: str,
    user: models.User,
    verification: models_buyback.IdentityVerification | None = None,
    consent: models_buyback.GuardianConsent | None = None,
    raw_token: str | None = None,
    reason: str | None = None,
) -> tuple[bool, str | None]:
    return send_kyc_event_email(
        db,
        event_key,
        user=user,
        verification=verification,
        consent=consent,
        raw_token=raw_token,
        reason=reason,
        force=True,
        send_email=True,
    )
