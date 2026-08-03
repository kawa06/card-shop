"""Unified templated email delivery via Resend with logging and fallback."""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

import models_email
from config import settings
from services.email_events import normalize_variable_key, sample_variables_for_template
from services.email_html import wrap_with_brand
from services.email_order_layout import build_preheader_html
from services.shipping_email_registry import normalize_template_key as normalize_shipping_template_key
from services.buyback_email_registry import normalize_template_key as normalize_buyback_template_key
from services.kyc_email_registry import normalize_template_key as normalize_kyc_template_key
from services.member_email_registry import normalize_template_key as normalize_member_template_key
from services.verification import email_configured, smtp_configured

logger = logging.getLogger(__name__)

DARK_MODE_PREVIEW_STYLE = """
<style>
  .email-bg { background-color: #0f172a !important; }
  .email-card { background-color: #1e293b !important; border-color: #334155 !important; }
  .email-text { color: #e2e8f0 !important; }
  .email-muted { color: #94a3b8 !important; }
  .email-hr { border-color: #334155 !important; }
  body.email-bg { background-color: #0f172a !important; }
  h1, h2, h3, p, td, th, div, span, a { color-scheme: dark; }
</style>
"""

VAR_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")

MAIL_REPLY_TO_FALLBACK = "oripakawa@gmail.com"


def _effective_from_address(*, via_smtp: bool = False) -> str:
    username = (settings.MAIL_USERNAME or "").strip()
    if via_smtp and username:
        return f"{settings.MAIL_FROM_NAME} <{username}>"
    if username.endswith("@gmail.com"):
        return f"{settings.MAIL_FROM_NAME} <{username}>"
    return f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"


def _send_smtp(
    *, to: str, subject: str, html_body: str, text_body: str | None = None
) -> tuple[bool, str | None, str | None]:
    if not smtp_configured():
        return False, "SMTP is not configured", None
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from_addr = settings.MAIL_USERNAME.strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _effective_from_address(via_smtp=True)
    msg["To"] = to
    reply_to = (settings.MAIL_REPLY_TO or MAIL_REPLY_TO_FALLBACK).strip()
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

    smtp_timeout = 5 if not settings.DEBUG else 30
    try:
        if settings.MAIL_SSL:
            server = smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=smtp_timeout)
        else:
            server = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=smtp_timeout)
            if settings.MAIL_TLS:
                server.starttls()
        server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
        server.sendmail(from_addr, [to], msg.as_string())
        server.quit()
        logger.info("SMTP fallback send ok to=%s from=%s", to, from_addr)
        return True, None, "smtp"
    except Exception as exc:
        logger.exception("SMTP fallback send failed to=%s from=%s", to, from_addr)
        return False, str(exc), None


@dataclass
class SendResult:
    ok: bool
    error: Optional[str] = None
    error_code: Optional[str] = None
    user_message: Optional[str] = None
    provider_message_id: Optional[str] = None
    used_template: bool = False


def parse_resend_error(status_code: int, response_text: str) -> tuple[str, str, str]:
    """Return (user_message, error_code, technical_detail)."""
    technical = f"Resend error ({status_code}): {response_text}"
    message = response_text
    try:
        payload = json.loads(response_text)
        if isinstance(payload, dict):
            message = str(payload.get("message") or payload.get("error") or response_text)
    except Exception:
        pass

    lower = message.lower()
    if status_code == 403 and "domain" in lower and "not verified" in lower:
        return (
            "メール送信の設定に問題があります（送信元ドメインが未検証）。ショップ管理者へお問い合わせください。",
            "mail_domain_unverified",
            technical,
        )
    if status_code == 403:
        return (
            "メール送信が拒否されました。設定を確認してください。",
            "mail_forbidden",
            technical,
        )
    if status_code == 422:
        return (
            "メールアドレスが不正です。入力内容を確認してください。",
            "mail_invalid_recipient",
            technical,
        )
    if status_code >= 500:
        return (
            "メール送信サービスが一時的に利用できません。時間をおいて再度お試しください。",
            "mail_provider_error",
            technical,
        )
    return (
        "メールの送信に失敗しました。メールアドレスを確認して再度お試しください。",
        "mail_send_failed",
        technical,
    )


def _default_variables() -> dict[str, str]:
    return {
        "shopName": settings.SITE_NAME or "KRX TCG",
        "url": settings.FRONTEND_URL or "",
        "date": datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
        "contactUrl": "",
        "termsUrl": "",
        "privacyUrl": "",
    }


def render_template_string(
    template: str,
    variables: dict[str, Any],
    *,
    raw_keys: Optional[set[str]] = None,
) -> str:
    merged = {**_default_variables(), **{k: str(v if v is not None else "") for k, v in variables.items()}}
    raw_keys = raw_keys or set()

    def repl(match: re.Match) -> str:
        key = normalize_variable_key(match.group(1))
        if key in raw_keys:
            return merged.get(key, "")
        return html.escape(merged.get(key, ""), quote=True)

    return VAR_PATTERN.sub(repl, template or "")


def get_brand_settings(db: Session) -> models_email.EmailBrandSettings:
    row = db.query(models_email.EmailBrandSettings).first()
    if row is None:
        row = models_email.EmailBrandSettings()
        db.add(row)
        db.flush()
    return row


def _find_active_template(db: Session, template_key: str) -> models_email.EmailTemplate | None:
    keys: list[str] = []
    for key in (
        template_key,
        normalize_shipping_template_key(template_key),
        normalize_buyback_template_key(template_key),
        normalize_kyc_template_key(template_key),
        normalize_member_template_key(template_key),
    ):
        if key and key not in keys:
            keys.append(key)
    for key in keys:
        tpl = (
            db.query(models_email.EmailTemplate)
            .filter(
                models_email.EmailTemplate.template_key == key,
                models_email.EmailTemplate.is_active.is_(True),
            )
            .first()
        )
        if tpl:
            return tpl
    return None


def preview_draft(
    db: Session,
    *,
    template_key: Optional[str] = None,
    subject: str,
    html_body: str,
    preheader: Optional[str] = None,
    variables: Optional[dict[str, Any]] = None,
    raw_variable_keys: Optional[set[str]] = None,
    force_dark: bool = False,
) -> dict[str, str]:
    """Preview unsaved template content with brand wrapper."""
    variables = {**sample_variables_for_template(template_key or ""), **(variables or {})}
    brand = get_brand_settings(db)
    if brand.contact_url:
        variables.setdefault("contactUrl", brand.contact_url)
    if brand.terms_url:
        variables.setdefault("termsUrl", brand.terms_url)
    rendered_subject = render_template_string(subject, variables, raw_keys=raw_variable_keys)
    rendered_preheader = render_template_string(preheader or "", variables) if preheader else ""
    body = render_template_string(html_body, variables, raw_keys=raw_variable_keys)
    preheader_html = build_preheader_html(rendered_preheader)
    full_html = wrap_with_brand(preheader_html + body, brand, variables)
    if force_dark:
        full_html = full_html.replace("<head>", f"<head>{DARK_MODE_PREVIEW_STYLE}", 1)
    return {"subject": rendered_subject, "preheader": rendered_preheader, "html": full_html}


def preview_template(
    db: Session,
    *,
    template_key: str,
    variables: Optional[dict[str, Any]] = None,
    subject_override: Optional[str] = None,
    html_body_override: Optional[str] = None,
    preheader_override: Optional[str] = None,
    force_dark: bool = False,
) -> dict[str, str]:
    variables = {**sample_variables_for_template(template_key), **(variables or {})}
    brand = get_brand_settings(db)
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl and not (subject_override and html_body_override):
        raise ValueError("Template not found")
    subject = subject_override or (tpl.subject if tpl else "")
    html_body = html_body_override or (tpl.html_body if tpl else "")
    preheader = preheader_override if preheader_override is not None else (tpl.preheader if tpl else "")
    return preview_draft(
        db,
        template_key=template_key,
        subject=subject,
        html_body=html_body,
        preheader=preheader,
        variables=variables,
        force_dark=force_dark,
    )


def _send_resend(
    *, to: str, subject: str, html_body: str, text_body: str | None = None
) -> tuple[bool, str | None, str | None, str | None, str | None]:
    """Returns ok, technical_error, message_id, error_code, user_message."""
    if not settings.RESEND_API_KEY:
        if settings.DEBUG:
            logger.info("[EMAIL MOCK] to=%s subject=%s from=%s", to, subject, settings.MAIL_FROM)
            return True, None, "mock", None, None
        return False, "RESEND_API_KEY is not configured", None, "mail_not_configured", (
            "メール送信が設定されていません。ショップ管理者へお問い合わせください。"
        )

    from_address = _effective_from_address()
    reply_to = (settings.MAIL_REPLY_TO or MAIL_REPLY_TO_FALLBACK).strip()
    payload: dict = {"from": from_address, "to": [to], "subject": subject, "html": html_body}
    if text_body:
        payload["text"] = text_body
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
            msg_id = None
            try:
                msg_id = response.json().get("id")
            except Exception:
                pass
            return True, None, msg_id, None, None
        user_message, error_code, technical = parse_resend_error(
            response.status_code, response.text
        )
        logger.error(
            "Resend send failed to=%s from=%s status=%s error_code=%s detail=%s",
            to,
            settings.MAIL_FROM,
            response.status_code,
            error_code,
            technical,
        )
        if error_code in {"mail_domain_unverified", "mail_forbidden"} and smtp_configured():
            smtp_ok, smtp_err, smtp_id = _send_smtp(
                to=to, subject=subject, html_body=html_body, text_body=text_body
            )
            if smtp_ok:
                return True, None, smtp_id, None, None
            technical = f"{technical}; SMTP fallback failed: {smtp_err}"
        return False, technical, None, error_code, user_message
    except Exception as exc:
        logger.exception("Resend send failed to=%s from=%s", to, settings.MAIL_FROM)
        return (
            False,
            str(exc),
            None,
            "mail_network_error",
            "メール送信に失敗しました。通信環境を確認して再度お試しください。",
        )


def _send_email(
    *, to: str, subject: str, html_body: str, text_body: str | None = None
) -> tuple[bool, str | None, str | None, str | None, str | None]:
    """Prefer Resend on cloud hosts; SMTP is often blocked (e.g. Railway port 465)."""
    if settings.RESEND_API_KEY:
        ok, err, msg_id, error_code, user_message = _send_resend(
            to=to, subject=subject, html_body=html_body, text_body=text_body
        )
        if ok:
            return ok, err, msg_id, error_code, user_message
        if smtp_configured() and error_code in {"mail_domain_unverified", "mail_forbidden"}:
            smtp_ok, smtp_err, smtp_id = _send_smtp(
                to=to, subject=subject, html_body=html_body, text_body=text_body
            )
            if smtp_ok:
                return True, None, smtp_id, None, None
            err = f"{err}; SMTP fallback failed: {smtp_err}"
        return False, err, msg_id, error_code, user_message

    if smtp_configured():
        smtp_ok, smtp_err, smtp_id = _send_smtp(
            to=to, subject=subject, html_body=html_body, text_body=text_body
        )
        if smtp_ok:
            return True, None, smtp_id, None, None
        return False, smtp_err, None, "mail_send_failed", (
            "メールの送信に失敗しました。Gmail の設定を確認してください。"
        )

    return _send_resend(to=to, subject=subject, html_body=html_body, text_body=text_body)


def _log_send(
    db: Session,
    *,
    template_key: Optional[str],
    campaign_id: Optional[int],
    recipient: str,
    subject: str,
    html_body_snapshot: Optional[str],
    status: str,
    provider_message_id: Optional[str],
    error_message: Optional[str],
    reference_type: Optional[str],
    reference_id: Optional[str],
    is_test: bool,
    sent_by_user_id: Optional[int] = None,
    retry_count: int = 0,
) -> models_email.EmailSendLog:
    log = models_email.EmailSendLog(
        template_key=template_key,
        campaign_id=campaign_id,
        recipient=recipient,
        subject=subject,
        html_body_snapshot=html_body_snapshot,
        status=status,
        provider_message_id=provider_message_id,
        error_message=error_message,
        reference_type=reference_type,
        reference_id=reference_id,
        is_test=is_test,
        sent_by_user_id=sent_by_user_id,
        retry_count=retry_count,
    )
    db.add(log)
    return log


def send_templated_email(
    db: Session,
    *,
    template_key: str,
    to_email: str,
    variables: Optional[dict[str, Any]] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    campaign_id: Optional[int] = None,
    sent_by_user_id: Optional[int] = None,
    force: bool = False,
    is_test: bool = False,
    fallback_subject: Optional[str] = None,
    fallback_html: Optional[str] = None,
    fallback_text: Optional[str] = None,
    raw_variable_keys: Optional[set[str]] = None,
    html_snapshot: bool = False,
) -> SendResult:
    variables = variables or {}
    brand = get_brand_settings(db)
    if brand.contact_url:
        variables.setdefault("contactUrl", brand.contact_url)
    if brand.terms_url:
        variables.setdefault("termsUrl", brand.terms_url)

    used_template = False
    subject = fallback_subject or f"【{settings.SITE_NAME}】お知らせ"
    body_html = fallback_html or "<p>{{content}}</p>"
    text_body = fallback_text
    preheader = ""

    use_db_template = getattr(settings, "EMAIL_TEMPLATES_ENABLED", True)
    if use_db_template and not force:
        tpl = _find_active_template(db, template_key)
        if tpl:
            used_template = True
            subject = render_template_string(tpl.subject, variables, raw_keys=raw_variable_keys)
            body_html = render_template_string(tpl.html_body, variables, raw_keys=raw_variable_keys)
            if tpl.preheader:
                preheader = render_template_string(tpl.preheader, variables, raw_keys=raw_variable_keys)
            if tpl.text_body:
                text_body = render_template_string(tpl.text_body, variables, raw_keys=raw_variable_keys)

    if not used_template and fallback_html is None:
        _log_send(
            db,
            template_key=template_key,
            campaign_id=campaign_id,
            recipient=to_email,
            subject=subject,
            html_body_snapshot=None,
            status="skipped",
            provider_message_id=None,
            error_message="No template and no fallback",
            reference_type=reference_type,
            reference_id=reference_id,
            is_test=is_test,
            sent_by_user_id=sent_by_user_id,
        )
        return SendResult(ok=False, error="No template and no fallback", used_template=False)

    if used_template or fallback_html:
        subject = (
            render_template_string(subject, variables, raw_keys=raw_variable_keys)
            if "{{" in subject
            else subject
        )
        body_html = render_template_string(body_html, variables, raw_keys=raw_variable_keys)

    preheader_html = build_preheader_html(preheader)
    full_html = wrap_with_brand(preheader_html + body_html, brand, variables)
    ok, err, msg_id, error_code, user_message = _send_email(
        to=to_email, subject=subject, html_body=full_html, text_body=text_body
    )
    _log_send(
        db,
        template_key=template_key,
        campaign_id=campaign_id,
        recipient=to_email,
        subject=subject,
        html_body_snapshot=full_html if html_snapshot else body_html,
        status="sent" if ok else "failed",
        provider_message_id=msg_id,
        error_message=err,
        reference_type=reference_type,
        reference_id=reference_id,
        is_test=is_test,
        sent_by_user_id=sent_by_user_id,
    )
    return SendResult(
        ok=ok,
        error=err,
        error_code=error_code,
        user_message=user_message,
        provider_message_id=msg_id,
        used_template=used_template,
    )

