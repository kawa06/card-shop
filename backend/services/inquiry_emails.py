"""Email notifications for inquiries."""

from __future__ import annotations

import logging

import models
from config import settings
from services.order_emails import _send_html_email
from services.verification import email_configured

logger = logging.getLogger(__name__)

FRONTEND_BASE = settings.FRONTEND_URL.rstrip("/")


def _snippet(text: str, limit: int = 120) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _inquiry_link(inquiry_id: int, *, admin: bool = False) -> str:
    if admin:
        return f"{FRONTEND_BASE}/admin/inquiries/{inquiry_id}"
    return f"{FRONTEND_BASE}/mypage/inquiries/{inquiry_id}"


def _send(subject: str, to: str, inner_html: str) -> None:
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
    _send_html_email(to=to, subject=subject, html=html)


def notify_inquiry_received(inquiry: models.Inquiry, user: models.User) -> None:
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
        f"【KRX TCG】お問い合わせを受け付けました（{inquiry.inquiry_number}）",
        inquiry.reply_email,
        body,
    )


def notify_admin_new_inquiry(inquiry: models.Inquiry, user: models.User, first_message: str) -> None:
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
    _send(f"【KRX TCG 管理】新規問い合わせ {inquiry.inquiry_number}", admin_email, body)


def notify_customer_admin_reply(inquiry: models.Inquiry, reply_text: str) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>お問い合わせ（{inquiry.inquiry_number}）への返信が届きました。</p>
      <p>件名：{inquiry.subject}</p>
      <p>概要：{_snippet(reply_text)}</p>
      <p><a href="{link}">返信を確認</a></p>
    """
    _send(
        f"【KRX TCG】お問い合わせへの返信（{inquiry.inquiry_number}）",
        inquiry.reply_email,
        body,
    )


def notify_admin_customer_reply(inquiry: models.Inquiry, user: models.User, reply_text: str) -> None:
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
    _send(f"【KRX TCG 管理】購入者返信 {inquiry.inquiry_number}", admin_email, body)


def notify_customer_inquiry_resolved(inquiry: models.Inquiry, note: str | None = None) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>お問い合わせ（{inquiry.inquiry_number}）を解決済みにしました。</p>
      <p>件名：{inquiry.subject}</p>
      {f'<p>コメント：{_snippet(note)}</p>' if note else ''}
      <p>追加のご質問がある場合は、問い合わせ詳細から再度メッセージをお送りください。</p>
      <p><a href="{link}">問い合わせ詳細を確認</a></p>
    """
    _send(
        f"【KRX TCG】お問い合わせ解決のお知らせ（{inquiry.inquiry_number}）",
        inquiry.reply_email,
        body,
    )


def notify_customer_inquiry_closed(inquiry: models.Inquiry, note: str | None = None) -> None:
    link = _inquiry_link(inquiry.id)
    body = f"""
      <p>お問い合わせ（{inquiry.inquiry_number}）を終了しました。</p>
      <p>件名：{inquiry.subject}</p>
      {f'<p>コメント：{_snippet(note)}</p>' if note else ''}
      <p>この問い合わせへの返信はできません。新しいご用件は再度お問い合わせください。</p>
      <p><a href="{link}">問い合わせ詳細を確認</a></p>
    """
    _send(
        f"【KRX TCG】お問い合わせ終了のお知らせ（{inquiry.inquiry_number}）",
        inquiry.reply_email,
        body,
    )


def notify_inquiry_status_change(
    inquiry: models.Inquiry,
    *,
    old_status: str,
    new_status: str,
    reply_text: str | None = None,
) -> None:
    if new_status == old_status:
        return
    if new_status == "resolved":
        notify_customer_inquiry_resolved(inquiry, reply_text)
    elif new_status == "closed":
        notify_customer_inquiry_closed(inquiry, reply_text)
