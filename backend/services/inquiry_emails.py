"""Email notifications for inquiries."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

import models
from config import settings
from services.email_delivery import send_templated_email
from services.verification import email_configured

logger = logging.getLogger(__name__)

FRONTEND_BASE = settings.FRONTEND_URL.rstrip("/")

TEMPLATE_KEYS = {
    "received": "inquiry_received",
    "admin_new": "inquiry_received",
    "admin_reply": "inquiry_reply",
    "customer_reply_admin": "inquiry_reply",
    "resolved": "inquiry_reply",
    "closed": "inquiry_reply",
}


def _snippet(text: str, limit: int = 120) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _inquiry_link(inquiry_id: int, *, admin: bool = False) -> str:
    if admin:
        return f"{FRONTEND_BASE}/admin/inquiries/{inquiry_id}"
    return f"{FRONTEND_BASE}/mypage/inquiries/{inquiry_id}"


def _send(
    db: Session,
    *,
    template_key: str,
    subject: str,
    to: str,
    inner_html: str,
    variables: dict | None = None,
    reference_id: str | None = None,
) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG</h2>
      {inner_html}
      <p style="font-size:11px;color:#999;margin-top:24px;">&copy; KRX TCG</p>
    </div>
    """
    if not email_configured():
        if settings.DEBUG:
            logger.info("[INQUIRY EMAIL MOCK] to=%s subject=%s", to, subject)
        return

    merged = {"content": inner_html, **(variables or {})}
    send_templated_email(
        db,
        template_key=template_key,
        to_email=to,
        variables=merged,
        fallback_subject=subject,
        fallback_html=html,
        reference_type="inquiry",
        reference_id=reference_id,
        raw_variable_keys={"content"},
    )


def notify_inquiry_received(db: Session, inquiry: models.Inquiry, user: models.User) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>お問い合わせを受け付けました。</p>
      <ul>
        <li>問い合わせ番号：{inquiry.inquiry_number}</li>
        <li>件名：{inquiry.subject}</li>
      </ul>
      <p><a href="{link}">問い合わせ詳細を確認</a></p>
    """
    _send(
        db,
        template_key="inquiry_received",
        subject=f"【KRX TCG】お問い合わせを受け付けました（{inquiry.inquiry_number}）",
        to=inquiry.reply_email,
        inner_html=body,
        variables={"name": user.name or "お客", "email": user.email, "inquiryNo": inquiry.inquiry_number},
        reference_id=str(inquiry.id),
    )


def notify_admin_new_inquiry(
    db: Session, inquiry: models.Inquiry, user: models.User, first_message: str
) -> None:
    admin_email = settings.MAIL_REPLY_TO or "oripakawa@gmail.com"
    link = _inquiry_link(inquiry.id, admin=True)
    body = f"""
      <p>新しいお問い合わせが届きました。</p>
      <ul>
        <li>問い合わせ番号：{inquiry.inquiry_number}</li>
        <li>件名：{inquiry.subject}</li>
        <li>購入者：{user.name}（{user.email}）</li>
        <li>関連注文：{inquiry.related_order_number or '—'}</li>
      </ul>
      <p>概要：{_snippet(first_message)}</p>
      <p><a href="{link}">管理画面で確認</a></p>
    """
    _send(
        db,
        template_key="inquiry_received",
        subject=f"【KRX TCG 管理】新規問い合わせ {inquiry.inquiry_number}",
        to=admin_email,
        inner_html=body,
        reference_id=str(inquiry.id),
    )


def notify_customer_admin_reply(db: Session, inquiry: models.Inquiry, reply_text: str) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>お問い合わせ（{inquiry.inquiry_number}）への返信が届きました。</p>
      <p>件名：{inquiry.subject}</p>
      <p>概要：{_snippet(reply_text)}</p>
      <p><a href="{link}">返信を確認</a></p>
    """
    _send(
        db,
        template_key="inquiry_reply",
        subject=f"【KRX TCG】お問い合わせへの返信（{inquiry.inquiry_number}）",
        to=inquiry.reply_email,
        inner_html=body,
        variables={"inquiryNo": inquiry.inquiry_number},
        reference_id=str(inquiry.id),
    )


def notify_admin_customer_reply(
    db: Session, inquiry: models.Inquiry, user: models.User, reply_text: str
) -> None:
    admin_email = settings.MAIL_REPLY_TO or "oripakawa@gmail.com"
    link = _inquiry_link(inquiry.id, admin=True)
    body = f"""
      <p>購入者から追加返信がありました。</p>
      <ul>
        <li>問い合わせ番号：{inquiry.inquiry_number}</li>
        <li>購入者：{user.name}</li>
      </ul>
      <p>概要：{_snippet(reply_text)}</p>
      <p><a href="{link}">管理画面で確認</a></p>
    """
    _send(
        db,
        template_key="inquiry_reply",
        subject=f"【KRX TCG 管理】購入者返信 {inquiry.inquiry_number}",
        to=admin_email,
        inner_html=body,
        reference_id=str(inquiry.id),
    )


def notify_customer_inquiry_resolved(
    db: Session, inquiry: models.Inquiry, note: str | None = None
) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>お問い合わせ（{inquiry.inquiry_number}）を解決済みにしました。</p>
      <p>件名：{inquiry.subject}</p>
      {f'<p>コメント：{_snippet(note)}</p>' if note else ''}
      <p>追加のご質問がある場合は、問い合わせ詳細から再度メッセージをお送りください。</p>
      <p><a href="{link}">問い合わせ詳細を確認</a></p>
    """
    _send(
        db,
        template_key="inquiry_reply",
        subject=f"【KRX TCG】お問い合わせ解決のお知らせ（{inquiry.inquiry_number}）",
        to=inquiry.reply_email,
        inner_html=body,
        reference_id=str(inquiry.id),
    )


def notify_customer_inquiry_closed(
    db: Session, inquiry: models.Inquiry, note: str | None = None
) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>お問い合わせ（{inquiry.inquiry_number}）を終了しました。</p>
      <p>件名：{inquiry.subject}</p>
      {f'<p>コメント：{_snippet(note)}</p>' if note else ''}
      <p>この問い合わせへの返信はできません。新しいご用件は再度お問い合わせください。</p>
      <p><a href="{link}">問い合わせ詳細を確認</a></p>
    """
    _send(
        db,
        template_key="inquiry_reply",
        subject=f"【KRX TCG】お問い合わせ終了のお知らせ（{inquiry.inquiry_number}）",
        to=inquiry.reply_email,
        inner_html=body,
        reference_id=str(inquiry.id),
    )


def notify_inquiry_status_change(
    db: Session,
    inquiry: models.Inquiry,
    *,
    old_status: str,
    new_status: str,
    reply_text: str | None = None,
) -> None:
    if new_status == old_status:
        return
    if new_status == "resolved":
        notify_customer_inquiry_resolved(db, inquiry, reply_text)
    elif new_status == "closed":
        notify_customer_inquiry_closed(db, inquiry, reply_text)
