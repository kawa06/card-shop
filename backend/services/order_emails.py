"""Transactional emails for orders (purchase confirmation, etc.)."""

from __future__ import annotations

import html
import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

import models
from config import settings
from services.email_delivery import send_templated_email
from services.email_order_layout import ORDER_EMAIL_BODY_SKELETON
from services.order_email_utils import (
    BANK_TRANSFER_METHODS,
    SHIPPING_METHOD_LABELS,
    format_datetime_jst,
    format_jpy,
    order_subtotal,
    payment_method_label,
)
from services.order_email_variables import RAW_ORDER_VARIABLE_KEYS, build_order_email_variables
from services.payment_email_registry import resolve_order_template_key
from services.shipping_emails import send_shipping_completion_email

logger = logging.getLogger(__name__)


def _email_send_status(value: str) -> str:
    return value[:50]

MAIL_REPLY_TO = "oripakawa@gmail.com"


def _build_order_items_table_html(order: models.Order) -> str:
    rows = ""
    for item in order.items:
        name = html.escape(item.card.name if item.card else f"商品 #{item.card_id}")
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{name}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{item.quantity}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{format_jpy(item.unit_price)}</td>
        </tr>"""
    return rows


def _dispatch_order_email(
    db: Session,
    *,
    template_key: str,
    to_email: str,
    variables: dict,
    fallback_subject: str,
    fallback_html: str,
    reference_id: str,
    raw_variable_keys: set[str] | None = None,
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
        raw_variable_keys=raw_variable_keys or RAW_ORDER_VARIABLE_KEYS,
    )
    return result.ok, result.error


def _send_order_event_email(
    db: Session,
    order: models.Order,
    event_key: str,
    *,
    fallback_subject: str,
) -> tuple[bool, str | None]:
    template_key = resolve_order_template_key(event_key, order.payment_method)
    variables = build_order_email_variables(order, event_key, db=db)
    from services.email_delivery import render_template_string

    fallback_html = render_template_string(
        ORDER_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_ORDER_VARIABLE_KEYS,
    )
    buyer = order.user
    if not buyer or not buyer.email:
        return False, "購入者メールアドレスがありません"
    return _dispatch_order_email(
        db,
        template_key=template_key,
        to_email=buyer.email,
        variables=variables,
        fallback_subject=fallback_subject,
        fallback_html=fallback_html,
        reference_id=str(order.id),
        text_body=variables.get("_text_body"),
    )


def _build_purchase_confirmation_html(order: models.Order, buyer_name: str) -> str:
    subtotal = order_subtotal(order)
    shipping_fee = order.shipping_fee or 0
    method_label = SHIPPING_METHOD_LABELS.get(order.shipping_method or "", order.shipping_method or "—")
    rows = _build_order_items_table_html(order)
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG — ご購入ありがとうございます</h2>
      <p>{buyer_name} 様</p>
      <p>お支払いが確認できました。以下の内容でご注文を承りました。</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
        <tr><td style="padding:6px 0;color:#666;">注文番号</td><td style="padding:6px 0;font-weight:bold;">{order.order_number or '—'}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">注文日時</td><td style="padding:6px 0;">{format_datetime_jst(order.paid_at or order.created_at)}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">お支払方法</td><td style="padding:6px 0;">{payment_method_label(order)}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">発送方法</td><td style="padding:6px 0;">{method_label}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">配送先</td><td style="padding:6px 0;">{(order.shipping_address or '').replace(chr(10), '<br>')}</td></tr>
      </table>
      <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
        <thead>
          <tr style="background:#f9fafb;">
            <th style="padding:8px;text-align:left;">商品名</th>
            <th style="padding:8px;text-align:center;">数量</th>
            <th style="padding:8px;text-align:right;">単価</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <table style="width:100%;font-size:14px;margin-top:8px;">
        <tr><td style="padding:4px 0;color:#666;">商品小計</td><td style="text-align:right;">{format_jpy(subtotal)}</td></tr>
        <tr><td style="padding:4px 0;color:#666;">送料</td><td style="text-align:right;">{format_jpy(shipping_fee)}</td></tr>
        <tr><td style="padding:8px 0;font-weight:bold;">お支払総額</td><td style="text-align:right;font-weight:bold;color:#ca8a04;">{format_jpy(order.total_amount)}</td></tr>
      </table>
      <p style="font-size:13px;color:#444;margin-top:24px;">
        入金確認後、順次発送準備を進めます。発送完了時には別途メールでお知らせします。
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="font-size:12px;color:#666;">
        お問い合わせ: <a href="mailto:{MAIL_REPLY_TO}">{MAIL_REPLY_TO}</a><br>
        ※お問い合わせの際は注文番号（{order.order_number or ''}）をお書き添えください。
      </p>
      <p style="font-size:11px;color:#999;">&copy; KRX TCG</p>
    </div>
    """


def _load_order_for_email(db: Session, order_id: int) -> models.Order | None:
    return (
        db.query(models.Order)
        .options(
            joinedload(models.Order.items).joinedload(models.OrderItem.card),
            joinedload(models.Order.user),
        )
        .filter(models.Order.id == order_id)
        .first()
    )


def send_purchase_confirmation_email(
    db: Session,
    order_id: int,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    """
    Send purchase confirmation email when payment is complete.
    Returns (success, error_message).
    """
    order = _load_order_for_email(db, order_id)
    if not order:
        return False, "注文が見つかりません"

    if order.payment_status != "paid":
        return False, "支払い済みの注文のみメール送信できます"

    if not order.order_number:
        return False, "注文番号が未発行です"

    if order.purchase_email_sent_at and not force:
        return True, None

    buyer = order.user
    if not buyer or not buyer.email:
        return False, "購入者メールアドレスがありません"

    buyer_name = buyer.name or buyer.email.split("@")[0]
    subject = f"【KRX TCG】ご購入ありがとうございます（注文番号: {order.order_number}）"
    ok, err = _send_order_event_email(
        db,
        order,
        "payment_success",
        fallback_subject=subject,
    )
    now = datetime.utcnow()
    if ok:
        order.purchase_email_sent_at = now
        order.email_send_status = "purchase_ok"
    else:
        order.email_send_status = _email_send_status(f"purchase_failed:{err or 'unknown'}")
    db.commit()
    return ok, err


def try_auto_purchase_email_after_payment(db: Session, order: models.Order) -> None:
    """Best-effort automatic email after payment; failures are logged, not raised."""
    if order.purchase_email_sent_at:
        return
    ok, err = send_purchase_confirmation_email(db, order.id, force=False)
    if not ok and err:
        logger.warning("Purchase confirmation email failed for order %s: %s", order.id, err)


def _build_bank_transfer_pending_html(order: models.Order, buyer_name: str) -> str:
    subtotal = order_subtotal(order)
    shipping_fee = order.shipping_fee or 0
    deadline_text = format_datetime_jst(order.payment_deadline)
    method_label = SHIPPING_METHOD_LABELS.get(order.shipping_method or "", order.shipping_method or "—")
    rows = _build_order_items_table_html(order)
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG — 銀行振込のご案内</h2>
      <p>{buyer_name} 様</p>
      <p>銀行振込によるご注文を受け付けました。Stripeの決済画面に表示された<strong>振込先口座</strong>へ、<strong>指定金額</strong>をお振り込みください。</p>
      <p style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px;font-size:14px;">
        振込先・振込コード・参照番号などの詳細は、Stripe Checkout完了画面でご確認ください。<br>
        本メールではセキュリティ上、口座情報は記載していません。
      </p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
        <tr><td style="padding:6px 0;color:#666;">受付ID</td><td style="padding:6px 0;font-weight:bold;">#{order.id}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">お支払方法</td><td style="padding:6px 0;">{payment_method_label(order)}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">お支払期限</td><td style="padding:6px 0;color:#b45309;font-weight:bold;">{deadline_text or '—'}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">発送方法</td><td style="padding:6px 0;">{method_label}</td></tr>
      </table>
      <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
        <thead>
          <tr style="background:#f9fafb;">
            <th style="padding:8px;text-align:left;">商品名</th>
            <th style="padding:8px;text-align:center;">数量</th>
            <th style="padding:8px;text-align:right;">単価</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <table style="width:100%;font-size:14px;margin-top:8px;">
        <tr><td style="padding:4px 0;color:#666;">商品小計</td><td style="text-align:right;">{format_jpy(subtotal)}</td></tr>
        <tr><td style="padding:4px 0;color:#666;">送料</td><td style="text-align:right;">{format_jpy(shipping_fee)}</td></tr>
        <tr><td style="padding:8px 0;font-weight:bold;">お振込金額</td><td style="text-align:right;font-weight:bold;color:#ca8a04;">{format_jpy(order.total_amount)}</td></tr>
      </table>
      <p style="font-size:13px;color:#444;margin-top:24px;">
        商品は取り置き済みです。入金確認後に注文番号を発行し、発送準備を進めます。入金確認後、別途ご購入完了メールをお送りします。
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="font-size:12px;color:#666;">
        お問い合わせ: <a href="mailto:{MAIL_REPLY_TO}">{MAIL_REPLY_TO}</a><br>
        ※お問い合わせの際は受付ID（#{order.id}）をお書き添えください。
      </p>
      <p style="font-size:11px;color:#999;">&copy; KRX TCG</p>
    </div>
    """


def _build_bank_transfer_cancelled_html(
    order: models.Order,
    buyer_name: str,
    *,
    as_expired: bool,
) -> str:
    reason = "お支払期限を過ぎたため" if as_expired else "決済が完了しなかったため"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG — ご注文について</h2>
      <p>{buyer_name} 様</p>
      <p>{reason}、ご注文（受付ID #{order.id}）はキャンセルとなりました。取り置き在庫は解放済みです。</p>
      <p style="font-size:13px;color:#444;">
        再度ご購入をご希望の場合は、ショップよりお手続きください。
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="font-size:12px;color:#666;">
        お問い合わせ: <a href="mailto:{MAIL_REPLY_TO}">{MAIL_REPLY_TO}</a>
      </p>
      <p style="font-size:11px;color:#999;">&copy; KRX TCG</p>
    </div>
    """


def send_bank_transfer_pending_email(
    db: Session,
    order_id: int,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    order = _load_order_for_email(db, order_id)
    if not order:
        return False, "注文が見つかりません"
    if order.payment_status != "awaiting_payment":
        return False, "入金待ちの注文のみ送信できます"
    if order.payment_method not in BANK_TRANSFER_METHODS:
        return False, "銀行振込の注文ではありません"
    if order.email_send_status == "bank_transfer_pending_ok" and not force:
        return True, None

    buyer = order.user
    if not buyer or not buyer.email:
        return False, "購入者メールアドレスがありません"

    buyer_name = buyer.name or buyer.email.split("@")[0]
    subject = f"【KRX TCG】銀行振込のご案内（受付ID: #{order.id}）"
    ok, err = _send_order_event_email(
        db,
        order,
        "payment_pending",
        fallback_subject=subject,
    )
    if ok:
        order.email_send_status = "bank_transfer_pending_ok"
    else:
        order.email_send_status = _email_send_status(f"bank_transfer_pending_failed:{err or 'unknown'}")
    db.commit()
    return ok, err


def send_bank_transfer_cancelled_email(
    db: Session,
    order_id: int,
    *,
    as_expired: bool,
    force: bool = False,
) -> tuple[bool, str | None]:
    order = _load_order_for_email(db, order_id)
    if not order:
        return False, "注文が見つかりません"
    if order.payment_method not in BANK_TRANSFER_METHODS:
        return False, "銀行振込の注文ではありません"
    status_key = "bank_transfer_expired_ok" if as_expired else "bank_transfer_cancelled_ok"
    if order.email_send_status == status_key and not force:
        return True, None

    buyer = order.user
    if not buyer or not buyer.email:
        return False, "購入者メールアドレスがありません"

    buyer_name = buyer.name or buyer.email.split("@")[0]
    subject = f"【KRX TCG】ご注文キャンセルのお知らせ（受付ID: #{order.id}）"
    event_key = "payment_expired" if as_expired else "order_cancelled"
    ok, err = _send_order_event_email(
        db,
        order,
        event_key,
        fallback_subject=subject,
    )
    if ok:
        order.email_send_status = status_key
    else:
        order.email_send_status = _email_send_status(f"{status_key}_failed:{err or 'unknown'}")
    db.commit()
    return ok, err


def try_auto_bank_transfer_pending_email(db: Session, order: models.Order) -> None:
    if order.email_send_status == "bank_transfer_pending_ok":
        return
    ok, err = send_bank_transfer_pending_email(db, order.id, force=False)
    if not ok and err:
        logger.warning("Bank transfer pending email failed for order %s: %s", order.id, err)


def try_auto_bank_transfer_cancelled_email(
    db: Session,
    order: models.Order,
    *,
    as_expired: bool,
) -> None:
    status_key = "bank_transfer_expired_ok" if as_expired else "bank_transfer_cancelled_ok"
    if order.email_send_status == status_key:
        return
    ok, err = send_bank_transfer_cancelled_email(db, order.id, as_expired=as_expired, force=False)
    if not ok and err:
        logger.warning("Bank transfer cancelled email failed for order %s: %s", order.id, err)
