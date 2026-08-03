"""Shipping/delivery transactional emails."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload

import models
from services.carrier_registry import resolve_carrier_id
from services.email_delivery import render_template_string, send_templated_email
from services.email_order_layout import SHIPPING_EMAIL_BODY_SKELETON
from services.shipping_email_registry import get_shipping_email_event, resolve_shipping_template_key
from services.shipping_email_variables import (
    RAW_SHIPPING_VARIABLE_KEYS,
    build_shipping_email_variables,
)
from services.tracking_urls import is_trackable_shipping_method

logger = logging.getLogger(__name__)


def _load_order_for_email(db: Session, order_id: int) -> Optional[models.Order]:
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.user), joinedload(models.Order.items))
        .filter(models.Order.id == order_id)
        .first()
    )


def _dispatch_shipping_email(
    db: Session,
    *,
    template_key: str,
    to_email: str,
    variables: dict,
    fallback_subject: str,
    fallback_html: str,
    reference_id: str,
    text_body: str | None = None,
) -> tuple[bool, str | None]:
    clean_vars = {k: v for k, v in variables.items() if not str(k).startswith("_")}
    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=to_email,
        variables=clean_vars,
        fallback_subject=fallback_subject,
        fallback_html=fallback_html,
        fallback_text=text_body or variables.get("_text_body"),
        reference_type="order",
        reference_id=reference_id,
        raw_variable_keys=RAW_SHIPPING_VARIABLE_KEYS,
    )
    return result.ok, result.error


def send_shipping_event_email(
    db: Session,
    order_id: int,
    event_key: str,
    *,
    force: bool = False,
    delivery_date: Optional[str] = None,
    shipping_status: Optional[str] = None,
    inquiry_no: Optional[str] = None,
    update_order_on_shipped: bool = True,
) -> tuple[bool, str | None]:
    """Send a shipping/delivery email for the given event."""
    order = _load_order_for_email(db, order_id)
    if not order:
        return False, "注文が見つかりません"

    if order.payment_status != "paid":
        return False, "支払い済みの注文のみ送信できます"

    if not order.order_number:
        return False, "注文番号が未発行です"

    event = get_shipping_email_event(event_key)
    if not event:
        return False, f"不明な配送メールイベント: {event_key}"

    tracking = (order.tracking_number or "").strip()
    if event_key in {"shipping_shipped", "shipping_tracking_issued", "shipping_handed_to_carrier"}:
        if is_trackable_shipping_method(order.shipping_method) and not tracking:
            return False, "追跡番号を入力してから送信してください"

    if event_key == "shipping_shipped" and order.shipping_email_sent_at and not force:
        return True, None

    buyer = order.user
    if not buyer or not buyer.email:
        return False, "購入者メールアドレスがありません"

    template_key = resolve_shipping_template_key(
        event_key,
        resolve_carrier_id(order.shipping_method, order.shipping_carrier),
    )
    variables = build_shipping_email_variables(
        db,
        order,
        event_key,
        delivery_date=delivery_date,
        shipping_status=shipping_status,
        inquiry_no=inquiry_no,
    )
    fallback_html = render_template_string(
        SHIPPING_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_SHIPPING_VARIABLE_KEYS,
    )
    fallback_subject = f"【{variables.get('shopName', 'KRX TCG')}】{event.description}（{order.order_number}）"

    ok, err = _dispatch_shipping_email(
        db,
        template_key=template_key,
        to_email=buyer.email,
        variables=variables,
        fallback_subject=fallback_subject,
        fallback_html=fallback_html,
        reference_id=str(order.id),
    )

    now = datetime.utcnow()
    if ok and event_key == "shipping_shipped" and update_order_on_shipped:
        order.shipping_email_sent_at = now
        order.email_send_status = event.status_flag or "shipping_ok"
        if order.shipping_status not in ("shipped", "delivered"):
            order.shipping_status = "shipped"
            if not order.shipped_at:
                order.shipped_at = now
            order.status = models.OrderStatus.shipped
    elif ok and event.status_flag:
        order.email_send_status = event.status_flag
    elif not ok:
        order.email_send_status = f"shipping_failed:{err or 'unknown'}"

    db.commit()
    return ok, err


def send_shipping_completion_email(
    db: Session,
    order_id: int,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    """Backward-compatible wrapper for shipped notification."""
    return send_shipping_event_email(
        db,
        order_id,
        "shipping_shipped",
        force=force,
    )
