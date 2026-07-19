"""Transactional emails for buyback requests (Phase 5)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.order_emails import _send_html_email
from services.verification import email_configured

logger = logging.getLogger(__name__)

BUYLIST_BASE = settings.BUYLIST_URL.rstrip("/")
ADMIN_EMAIL = settings.MAIL_REPLY_TO or "oripakawa@gmail.com"

STATUS_LABELS: dict[str, str] = {
    "draft": "下書き",
    "submitted": "申込受付",
    "received": "商品到着",
    "assessing": "査定中",
    "assessed": "査定完了",
    "awaiting_customer": "ご確認待ち",
    "accepted": "買取成立",
    "rejected": "買取不可",
    "payout_pending": "振込準備中",
    "paid": "振込完了",
    "returned": "返送",
    "cancelled": "キャンセル",
}


def _format_jpy(amount: int | None) -> str:
    return f"¥{int(amount or 0):,}"


def _request_link(request_id: int) -> str:
    return f"{BUYLIST_BASE}/request.html?id={request_id}"


def _items_table_html(request: models_buyback.BuybackRequest) -> str:
    rows = []
    for item in request.items:
        line_total = item.listed_unit_price * item.quantity
        rows.append(
            "<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;'>{item.product_name_snapshot}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;'>{item.condition_code}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{_format_jpy(line_total)}</td>"
            "</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>商品</th>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>状態</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>数量</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>参考小計</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _wrap_email(inner_html: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG オンライン買取</h2>
      {inner_html}
      <p style="font-size:11px;color:#999;margin-top:24px;">&copy; KRX TCG</p>
    </div>
    """


def _record_delivery(
    db: Session,
    *,
    user_id: int | None,
    template_key: str,
    reference_id: str,
    ok: bool,
    error: str | None = None,
) -> None:
    try:
        db.add(
            models_buyback.NotificationDelivery(
                user_id=user_id,
                channel="email",
                template_key=template_key,
                reference_type="buyback_request",
                reference_id=reference_id,
                status="sent" if ok else "failed",
                error_message=error,
                sent_at=datetime.utcnow() if ok else None,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to record notification delivery: %s", exc)


def notify_buyback_request_submitted(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
) -> None:
    """Send customer confirmation and admin alert (best-effort)."""
    request_number = request.request_number or str(request.id)
    link = _request_link(request.id)
    status_label = STATUS_LABELS.get(request.status, request.status)

    customer_body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>買取申込を受け付けました。</p>
      <ul>
        <li>申込番号：{request_number}</li>
        <li>ステータス：{status_label}</li>
        <li>参考合計：{_format_jpy(request.estimated_total)}</li>
      </ul>
      <p>申込内容（掲載価格ベース）：</p>
      {_items_table_html(request)}
      <p style="font-size:13px;color:#555;margin-top:16px;">
        ※正式な買取金額は商品到着・査定後に確定します。
      </p>
      <p>商品の発送準備ができましたら、同梱の申込番号を記載のうえ発送してください。</p>
      <p><a href="{link}">申込詳細を確認</a></p>
    """
    customer_html = _wrap_email(customer_body)
    customer_subject = f"【KRX TCG】買取申込を受け付けました（{request_number}）"

    if not email_configured():
        if settings.DEBUG:
            logger.info("[BUYBACK EMAIL MOCK] to=%s subject=%s", user.email, customer_subject)
            _record_delivery(
                db,
                user_id=user.id,
                template_key="buyback_request_submitted",
                reference_id=str(request.id),
                ok=True,
            )
        return

    ok, err = _send_html_email(to=user.email, subject=customer_subject, html=customer_html)
    _record_delivery(
        db,
        user_id=user.id,
        template_key="buyback_request_submitted",
        reference_id=str(request.id),
        ok=ok,
        error=err,
    )

    admin_body = f"""
      <p>新しい買取申込が届きました。</p>
      <ul>
        <li>申込番号：{request_number}</li>
        <li>申込者：{user.name}（{user.email}）</li>
        <li>参考合計：{_format_jpy(request.estimated_total)}</li>
        <li>発送方法：{request.shipping_method or '—'}</li>
      </ul>
      {f'<p>備考：{request.customer_note}</p>' if request.customer_note else ''}
      {_items_table_html(request)}
    """
    admin_html = _wrap_email(admin_body)
    admin_subject = f"【KRX TCG 管理】新規買取申込 {request_number}"

    admin_ok, admin_err = _send_html_email(
        to=ADMIN_EMAIL, subject=admin_subject, html=admin_html
    )
    _record_delivery(
        db,
        user_id=None,
        template_key="buyback_request_admin_alert",
        reference_id=str(request.id),
        ok=admin_ok,
        error=admin_err,
    )


def notify_guardian_consent_requested(
    consent: models_buyback.GuardianConsent,
    user: models.User,
    raw_token: str,
) -> None:
    link = f"{BUYLIST_BASE}/guardian-consent.html?token={raw_token}"
    body = f"""
      <p>{consent.guardian_name} 様</p>
      <p>{user.name or 'お子様'} 様のオンライン買取利用について、保護者同意が必要です。</p>
      <p>以下のリンクから同意内容をご確認のうえ、同意手続きを完了してください。</p>
      <p><a href="{link}">保護者同意ページを開く</a></p>
      <p style="font-size:12px;color:#666;">リンクの有効期限があります。心当たりがない場合は破棄してください。</p>
    """
    subject = "【KRX TCG】保護者同意のお願い"
    html = _wrap_email(body)

    if not email_configured():
        if settings.DEBUG:
            logger.info("[GUARDIAN EMAIL MOCK] to=%s link=%s", consent.guardian_email, link)
        return

    _send_html_email(to=consent.guardian_email, subject=subject, html=html)
