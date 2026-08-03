"""Transactional emails for points, coupons, member rank, and campaigns."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_email
from services.email_delivery import render_template_string, send_templated_email
from services.email_order_layout import LOYALTY_EMAIL_BODY_SKELETON
from services.loyalty_email_auto_send import should_auto_send
from services.loyalty_email_registry import get_loyalty_email_event, resolve_loyalty_template_key
from services.loyalty_email_variables import (
    RAW_LOYALTY_VARIABLE_KEYS,
    LoyaltyEmailSnapshot,
    build_loyalty_email_variables,
)
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


def send_loyalty_event_email(
    db: Session,
    event_key: str,
    *,
    user: models.User | None = None,
    to_email: str | None = None,
    snapshot: LoyaltyEmailSnapshot | None = None,
    force: bool = False,
    send_email: bool | None = None,
    reference_type: str = "user",
    reference_id: str | None = None,
    fallback_subject: str | None = None,
    extra: dict | None = None,
) -> tuple[bool, str | None]:
    """Central loyalty email dispatcher — displays snapshot only, no point/rank calculation."""
    if not should_auto_send(db, event_key, explicit=send_email):
        return True, None

    event = get_loyalty_email_event(event_key)
    template_key = resolve_loyalty_template_key(event_key)
    recipient = to_email or (user.email if user else None)
    if not recipient:
        return False, "recipient_missing"

    ref_id = reference_id or (str(user.id) if user else recipient)

    if _notification_already_sent(db, template_key, ref_id, reference_type=reference_type) and not force:
        return True, None

    variables = build_loyalty_email_variables(
        db,
        user,
        event_key,
        to_email=recipient,
        snapshot=snapshot,
        extra=extra,
    )
    subject = fallback_subject or f"【{variables.get('shopName', 'KRX TCG')}】{event.description if event else event_key}"
    fallback_html = render_template_string(
        LOYALTY_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_LOYALTY_VARIABLE_KEYS,
    )

    if not email_configured():
        from config import settings

        if settings.DEBUG:
            logger.info("[LOYALTY EMAIL MOCK] to=%s event=%s", recipient, event_key)
        return True, None

    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=recipient,
        variables=variables,
        fallback_subject=subject,
        fallback_html=fallback_html,
        raw_variable_keys=RAW_LOYALTY_VARIABLE_KEYS,
        reference_type=reference_type,
        reference_id=ref_id,
        force=force,
    )
    if not result.ok:
        logger.error("Loyalty email failed event=%s to=%s error=%s", event_key, recipient, result.error)
    return result.ok, result.error


def notify_point_granted(
    db: Session,
    user: models.User,
    *,
    snapshot: LoyaltyEmailSnapshot,
    reference_id: str | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_loyalty_event_email(
        db,
        "point_granted",
        user=user,
        snapshot=snapshot,
        send_email=send_email,
        reference_id=reference_id or f"{user.id}:grant:{datetime.utcnow().strftime('%Y%m%d%H%M')}",
    )


def notify_coupon_distributed(
    db: Session,
    user: models.User,
    *,
    snapshot: LoyaltyEmailSnapshot,
    reference_id: str | None = None,
    force: bool = False,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_loyalty_event_email(
        db,
        "coupon_distributed",
        user=user,
        snapshot=snapshot,
        reference_id=reference_id or f"{user.id}:coupon:{datetime.utcnow().strftime('%Y%m%d%H%M')}",
        force=force,
        send_email=send_email,
    )


def notify_rank_up(
    db: Session,
    user: models.User,
    *,
    snapshot: LoyaltyEmailSnapshot,
    reference_id: str | None = None,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    return send_loyalty_event_email(
        db,
        "rank_up",
        user=user,
        snapshot=snapshot,
        send_email=send_email,
        reference_id=reference_id or f"{user.id}:rank-up",
    )


def resend_loyalty_email(
    db: Session,
    *,
    event_key: str,
    user: models.User,
    snapshot: LoyaltyEmailSnapshot | None = None,
    **kwargs,
) -> tuple[bool, str | None]:
    return send_loyalty_event_email(
        db,
        event_key,
        user=user,
        snapshot=snapshot,
        force=True,
        send_email=True,
        **kwargs,
    )
