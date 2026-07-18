"""Transactional emails for orders (purchase confirmation, etc.)."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session, joinedload

import models
from config import settings
from services.verification import email_configured
from services.tracking_urls import (
    build_tracking_url,
    carrier_display_name,
    is_trackable_shipping_method,
)

logger = logging.getLogger(__name__)

MAIL_REPLY_TO = "oripakawa@gmail.com"

SHIPPING_METHOD_LABELS: dict[str, str] = {
    "click_post": "クリックポスト",
    "teikei_post": "定形郵便",
    "teigai_post": "定形外郵便",
    "letter_pack_light": "レターパックライト",
    "letter_pack_plus": "レターパックプラス",
    "yu_pack_60": "ゆうパック 60サイズ",
    "yu_pack_80": "ゆうパック 80サイズ",
    "yu_pack_100": "ゆうパック 100サイズ",
    "takkyubin_compact": "宅急便コンパクト",
    "takkyubin_60": "宅急便 60サイズ",
    "takkyubin_80": "宅急便 80サイズ",
    "ems": "EMS",
    "yamato_global": "ヤマトグローバル",
}

PAYMENT_METHOD_LABELS: dict[str, str] = {
    "stripe_card": "クレジットカード（Stripe）",
    "stripe_bank_transfer": "銀行振込（Stripe）",
}


def _format_jpy(amount: float | int) -> str:
    return f"¥{int(round(float(amount))):,}"


def _format_datetime_jst(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y/%m/%d %H:%M") + " (UTC)"


def _order_subtotal(order: models.Order) -> float:
    return sum(item.unit_price * item.quantity for item in order.items)


def _send_html_email(*, to: str, subject: str, html: str) -> tuple[bool, str | None]:
    if not email_configured():
        if settings.DEBUG:
            logger.info("[EMAIL MOCK] to=%s subject=%s", to, subject)
            return True, None
        return False, "RESEND_API_KEY is not configured"

    from_address = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    reply_to = (settings.MAIL_REPLY_TO or MAIL_REPLY_TO).strip()

    payload: dict = {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code in (200, 201):
            return True, None
        return False, f"Resend error ({response.status_code}): {response.text}"
    except Exception as exc:
        logger.exception("Failed to send order email")
        return False, str(exc)


def _build_purchase_confirmation_html(order: models.Order, buyer_name: str) -> str:
    subtotal = _order_subtotal(order)
    shipping_fee = order.shipping_fee or 0
    method_label = SHIPPING_METHOD_LABELS.get(order.shipping_method or "", order.shipping_method or "—")
    rows = ""
    for item in order.items:
        name = item.card.name if item.card else f"商品 #{item.card_id}"
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{name}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{item.quantity}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{_format_jpy(item.unit_price)}</td>
        </tr>"""

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG — ご購入ありがとうございます</h2>
      <p>{buyer_name} 様</p>
      <p>お支払いが確認できました。以下の内容でご注文を承りました。</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
        <tr><td style="padding:6px 0;color:#666;">注文番号</td><td style="padding:6px 0;font-weight:bold;">{order.order_number or '—'}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">注文日時</td><td style="padding:6px 0;">{_format_datetime_jst(order.paid_at or order.created_at)}</td></tr>
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
        <tr><td style="padding:4px 0;color:#666;">商品小計</td><td style="text-align:right;">{_format_jpy(subtotal)}</td></tr>
        <tr><td style="padding:4px 0;color:#666;">送料</td><td style="text-align:right;">{_format_jpy(shipping_fee)}</td></tr>
        <tr><td style="padding:8px 0;font-weight:bold;">お支払総額</td><td style="text-align:right;font-weight:bold;color:#ca8a04;">{_format_jpy(order.total_amount)}</td></tr>
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
    html = _build_purchase_confirmation_html(order, buyer_name)
    subject = f"【KRX TCG】ご購入ありがとうございます（注文番号: {order.order_number}）"

    ok, err = _send_html_email(to=buyer.email, subject=subject, html=html)
    now = datetime.utcnow()
    if ok:
        order.purchase_email_sent_at = now
        order.email_send_status = "purchase_ok"
    else:
        order.email_send_status = f"purchase_failed:{err or 'unknown'}"
    db.commit()
    return ok, err


def try_auto_purchase_email_after_payment(db: Session, order: models.Order) -> None:
    """Best-effort automatic email after payment; failures are logged, not raised."""
    if order.purchase_email_sent_at:
        return
    ok, err = send_purchase_confirmation_email(db, order.id, force=False)
    if not ok and err:
        logger.warning("Purchase confirmation email failed for order %s: %s", order.id, err)


def _build_shipping_completion_html(order: models.Order, buyer_name: str) -> str:
    carrier_label = carrier_display_name(order.shipping_method, order.shipping_carrier)
    tracking = (order.tracking_number or "").strip()
    tracking_url = build_tracking_url(
        tracking,
        shipping_method=order.shipping_method,
        shipping_carrier=order.shipping_carrier,
    )
    method_label = SHIPPING_METHOD_LABELS.get(order.shipping_method or "", order.shipping_method or "—")

    tracking_block = ""
    if tracking:
        if tracking_url:
            tracking_block = f"""
            <p style="font-size:15px;margin:16px 0;">
              <strong>追跡番号：</strong>
              <a href="{tracking_url}" style="color:#ca8a04;font-weight:bold;">{tracking}</a>
            </p>
            <p style="font-size:13px;color:#444;">
              上記リンクから配送状況をご確認いただけます。
            </p>"""
        else:
            tracking_block = f"""
            <p style="font-size:15px;margin:16px 0;">
              <strong>追跡番号：</strong>{tracking}
            </p>"""

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG — 商品を発送しました</h2>
      <p>{buyer_name} 様</p>
      <p>ご注文の商品を発送いたしました。到着まで今しばらくお待ちください。</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
        <tr><td style="padding:6px 0;color:#666;">注文番号</td><td style="padding:6px 0;font-weight:bold;">{order.order_number or '—'}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">発送日時</td><td style="padding:6px 0;">{_format_datetime_jst(order.shipped_at or datetime.utcnow())}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">配送方法</td><td style="padding:6px 0;">{method_label}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">配送業者</td><td style="padding:6px 0;">{carrier_label}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">配送先</td><td style="padding:6px 0;">{(order.shipping_address or '').replace(chr(10), '<br>')}</td></tr>
      </table>
      {tracking_block}
      <p style="font-size:13px;color:#444;margin-top:24px;">
        商品到着後、問題がございましたら注文番号を添えてお問い合わせください。
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="font-size:12px;color:#666;">
        お問い合わせ: <a href="mailto:{MAIL_REPLY_TO}">{MAIL_REPLY_TO}</a><br>
        ※お問い合わせの際は注文番号（{order.order_number or ''}）をお書き添えください。
      </p>
      <p style="font-size:11px;color:#999;">&copy; KRX TCG</p>
    </div>
    """


def send_shipping_completion_email(
    db: Session,
    order_id: int,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    """
    Send shipping completion email with tracking info.
    Requires tracking_number for trackable shipping methods.
    """
    order = _load_order_for_email(db, order_id)
    if not order:
        return False, "注文が見つかりません"

    if order.payment_status != "paid":
        return False, "支払い済みの注文のみ送信できます"

    if not order.order_number:
        return False, "注文番号が未発行です"

    tracking = (order.tracking_number or "").strip()
    if is_trackable_shipping_method(order.shipping_method) and not tracking:
        return False, "追跡番号を入力してから送信してください"

    if order.shipping_email_sent_at and not force:
        return True, None

    buyer = order.user
    if not buyer or not buyer.email:
        return False, "購入者メールアドレスがありません"

    buyer_name = buyer.name or buyer.email.split("@")[0]
    html = _build_shipping_completion_html(order, buyer_name)
    subject = f"【KRX TCG】商品を発送しました（注文番号: {order.order_number}）"

    ok, err = _send_html_email(to=buyer.email, subject=subject, html=html)
    now = datetime.utcnow()
    if ok:
        order.shipping_email_sent_at = now
        order.email_send_status = "shipping_ok"
        if order.shipping_status not in ("shipped", "delivered"):
            order.shipping_status = "shipped"
            if not order.shipped_at:
                order.shipped_at = now
            order.status = models.OrderStatus.shipped
    else:
        order.email_send_status = f"shipping_failed:{err or 'unknown'}"
    db.commit()
    return ok, err
