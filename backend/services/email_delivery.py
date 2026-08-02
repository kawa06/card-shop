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
from services.verification import email_configured

logger = logging.getLogger(__name__)

VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}")

MAIL_REPLY_TO_FALLBACK = "oripakawa@gmail.com"


@dataclass
class SendResult:
    ok: bool
    error: Optional[str] = None
    provider_message_id: Optional[str] = None
    used_template: bool = False


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
        key = match.group(1)
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


def wrap_with_brand(body_html: str, brand: models_email.EmailBrandSettings, variables: dict[str, Any]) -> str:
    logo = brand.logo_url or variables.get("logoUrl", "")
    footer = brand.footer_text or f"© {settings.SITE_NAME or 'KRX TCG'}"
    terms = brand.terms_url or variables.get("termsUrl", "")
    contact = brand.contact_url or variables.get("contactUrl", "")
    logo_html = (
        f'<img src="{html.escape(logo)}" alt="logo" style="max-height:48px;margin-bottom:16px;">'
        if logo
        else f"<h2 style=\"color:#111;\">{html.escape(settings.SITE_NAME or 'KRX TCG')}</h2>"
    )
    links = []
    if terms:
        links.append(f'<a href="{html.escape(terms)}">利用規約</a>')
    if contact:
        links.append(f'<a href="{html.escape(contact)}">お問い合わせ</a>')
    if brand.privacy_url:
        links.append(f'<a href="{html.escape(brand.privacy_url)}">プライバシー</a>')
    try:
        sns = json.loads(brand.sns_links_json or "[]")
    except json.JSONDecodeError:
        sns = []
    for link in sns:
        if isinstance(link, dict) and link.get("url"):
            links.append(
                f'<a href="{html.escape(str(link["url"]))}">{html.escape(str(link.get("label", link["url"])))}</a>'
            )
    links_html = " | ".join(links)
    return (
        '<div style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">'
        f"{logo_html}"
        f"{body_html}"
        f'<hr style="border:0;border-top:1px solid #ddd;margin:24px 0;">'
        f'<p style="font-size:12px;color:#666;">{html.escape(footer)}</p>'
        f'<p style="font-size:12px;">{links_html}</p>'
        "</div>"
    )


def _send_resend(*, to: str, subject: str, html_body: str) -> tuple[bool, str | None, str | None]:
    if not email_configured():
        if settings.DEBUG:
            logger.info("[EMAIL MOCK] to=%s subject=%s", to, subject)
            return True, None, "mock"
        return False, "RESEND_API_KEY is not configured", None

    from_address = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    reply_to = (settings.MAIL_REPLY_TO or MAIL_REPLY_TO_FALLBACK).strip()
    payload: dict = {"from": from_address, "to": [to], "subject": subject, "html": html_body}
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
            return True, None, msg_id
        return False, f"Resend error ({response.status_code}): {response.text}", None
    except Exception as exc:
        logger.exception("Resend send failed")
        return False, str(exc), None


def _log_send(
    db: Session,
    *,
    template_key: Optional[str],
    recipient: str,
    subject: str,
    status: str,
    provider_message_id: Optional[str],
    error_message: Optional[str],
    reference_type: Optional[str],
    reference_id: Optional[str],
    is_test: bool,
) -> None:
    db.add(
        models_email.EmailSendLog(
            template_key=template_key,
            recipient=recipient,
            subject=subject,
            status=status,
            provider_message_id=provider_message_id,
            error_message=error_message,
            reference_type=reference_type,
            reference_id=reference_id,
            is_test=is_test,
        )
    )


def send_templated_email(
    db: Session,
    *,
    template_key: str,
    to_email: str,
    variables: Optional[dict[str, Any]] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    force: bool = False,
    is_test: bool = False,
    fallback_subject: Optional[str] = None,
    fallback_html: Optional[str] = None,
    raw_variable_keys: Optional[set[str]] = None,
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

    use_db_template = getattr(settings, "EMAIL_TEMPLATES_ENABLED", True)
    if use_db_template and not force:
        tpl = (
            db.query(models_email.EmailTemplate)
            .filter(
                models_email.EmailTemplate.template_key == template_key,
                models_email.EmailTemplate.is_active.is_(True),
            )
            .first()
        )
        if tpl:
            used_template = True
            subject = render_template_string(tpl.subject, variables, raw_keys=raw_variable_keys)
            body_html = render_template_string(tpl.html_body, variables, raw_keys=raw_variable_keys)

    if not used_template and fallback_html is None:
        _log_send(
            db,
            template_key=template_key,
            recipient=to_email,
            subject=subject,
            status="skipped",
            provider_message_id=None,
            error_message="No template and no fallback",
            reference_type=reference_type,
            reference_id=reference_id,
            is_test=is_test,
        )
        return SendResult(ok=False, error="No template and no fallback", used_template=False)

    if used_template or fallback_html:
        subject = (
            render_template_string(subject, variables, raw_keys=raw_variable_keys)
            if "{{" in subject
            else subject
        )
        body_html = render_template_string(body_html, variables, raw_keys=raw_variable_keys)

    full_html = wrap_with_brand(body_html, brand, variables)
    ok, err, msg_id = _send_resend(to=to_email, subject=subject, html_body=full_html)
    _log_send(
        db,
        template_key=template_key,
        recipient=to_email,
        subject=subject,
        status="sent" if ok else "failed",
        provider_message_id=msg_id,
        error_message=err,
        reference_type=reference_type,
        reference_id=reference_id,
        is_test=is_test,
    )
    return SendResult(ok=ok, error=err, provider_message_id=msg_id, used_template=used_template)


def preview_template(
    db: Session,
    *,
    template_key: str,
    variables: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    variables = variables or {}
    brand = get_brand_settings(db)
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise ValueError("Template not found")
    subject = render_template_string(tpl.subject, variables)
    html_body = wrap_with_brand(render_template_string(tpl.html_body, variables), brand, variables)
    return {"subject": subject, "html": html_body}
