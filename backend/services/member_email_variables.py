"""Build member / login / security email template variables (no passwords or auth codes)."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Optional

import models
from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_buttons_block,
    build_contact_block,
    build_member_info_block,
    build_notes_block,
    build_signature_block,
    build_text_body,
)
from services.member_email_registry import get_member_email_event, normalize_template_key

MEMBER_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "eventAt": ("日時", "eventAt"),
    "expiresAt": ("有効期限", "expiresAt"),
    "ipAddress": ("IPアドレス", "ipAddress"),
    "deviceName": ("端末", "deviceName"),
    "browser": ("ブラウザ", "browser"),
    "os": ("OS", "os"),
    "region": ("地域", "region"),
}

MEMBER_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "member_register_completed": ["eventAt"],
    "member_email_verify": ["expiresAt"],
    "member_email_verify_completed": ["eventAt"],
    "member_email_change_received": ["expiresAt"],
    "member_email_change_completed": ["eventAt"],
    "member_phone_verify": ["expiresAt"],
    "member_phone_verify_completed": ["eventAt"],
    "member_profile_updated": ["eventAt"],
    "member_withdrawal_received": ["eventAt"],
    "member_withdrawal_completed": ["eventAt"],
    "login_success": ["eventAt", "ipAddress", "deviceName", "browser", "os", "region"],
    "login_new_device": ["eventAt", "ipAddress", "deviceName", "browser", "os", "region"],
    "login_failed": ["eventAt", "ipAddress"],
    "login_failed_repeated": ["eventAt", "ipAddress"],
    "login_account_locked": ["eventAt", "expiresAt"],
    "login_account_unlocked": ["eventAt"],
    "password_reset_received": ["expiresAt"],
    "password_reset_completed": ["eventAt"],
    "password_changed": ["eventAt"],
    "security_important_notice": ["eventAt"],
    "security_suspicious_access": ["eventAt", "ipAddress", "deviceName", "browser", "region"],
    "security_settings_changed": ["eventAt"],
    "security_2fa_enabled": ["eventAt"],
    "security_2fa_disabled": ["eventAt"],
    "security_2fa_otp_sent": ["expiresAt"],
    "security_terms_updated": ["eventAt"],
    "security_privacy_updated": ["eventAt"],
    "security_system_error": ["eventAt"],
}

RAW_MEMBER_VARIABLE_KEYS = frozenset({
    "memberInfoBlock",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "content",
})


def _format_jst(dt: datetime | None = None) -> str:
    value = dt or datetime.utcnow()
    return value.strftime("%Y/%m/%d %H:%M")


def _mask_email(email: str) -> str:
    parts = (email or "").split("@")
    if len(parts) != 2:
        return "****"
    local, domain = parts
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _parse_user_agent(user_agent: str | None) -> tuple[str, str, str]:
    ua = user_agent or ""
    browser = "—"
    os_name = "—"
    device = "—"
    if "iPhone" in ua or "Android" in ua:
        device = "モバイル"
    elif ua:
        device = "PC"
    if "Chrome" in ua:
        browser = "Chrome"
    elif "Firefox" in ua:
        browser = "Firefox"
    elif "Safari" in ua and "Chrome" not in ua:
        browser = "Safari"
    elif "Edg" in ua:
        browser = "Edge"
    if "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "iPhone" in ua:
        os_name = "iOS"
    elif "Android" in ua:
        os_name = "Android"
    elif "Linux" in ua:
        os_name = "Linux"
    return device, browser, os_name


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def _default_member_buttons(event_key: str, ctx: dict[str, str]) -> list[dict[str, str]]:
    verify_url = ctx.get("verifyUrl") or ctx.get("認証URL") or ""
    reset_url = ctx.get("resetUrl") or ""
    account_url = ctx.get("accountUrl") or ""
    contact_url = ctx.get("contactUrl") or ""

    if event_key in {
        "member_email_verify",
        "member_email_change_received",
        "member_phone_verify",
        "security_2fa_otp_sent",
    } and verify_url:
        return [{"text": "（ボタンラベル）", "url": verify_url}]
    if event_key == "password_reset_received" and reset_url:
        return [{"text": "（ボタンラベル）", "url": reset_url}]
    if account_url:
        return [{"text": "（ボタンラベル）", "url": account_url}]
    if contact_url:
        return [{"text": "（ボタンラベル）", "url": contact_url}]
    return []


def _build_member_info_block_for_event(event_key: str, ctx: dict[str, str]) -> str:
    field_keys = MEMBER_EVENT_VISIBLE_FIELDS.get(event_key, [])
    rows: list[tuple[str, str]] = []
    for fk in field_keys:
        if fk not in MEMBER_INFO_FIELD_DEFS:
            continue
        label, var_key = MEMBER_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if value:
            rows.append((label, html.escape(str(value))))
    return build_member_info_block(rows)


def build_member_email_variables(
    db,
    user: models.User | None,
    event_key: str,
    *,
    to_email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    region: str | None = None,
    verify_url: str | None = None,
    reset_url: str | None = None,
    expires_at: datetime | None = None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    name = (user.name if user else None) or "お客"
    email = to_email or (user.email if user else "")
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    contact_url = brand.contact_url or settings.FRONTEND_URL or ""
    account_url = f"{settings.FRONTEND_URL.rstrip('/')}/account" if settings.FRONTEND_URL else ""
    device, browser, os_name = _parse_user_agent(user_agent)
    event_at = _format_jst()
    expires = _format_jst(expires_at) if expires_at else ""

    ctx = {
        "eventAt": event_at,
        "日時": event_at,
        "date": event_at,
        "expiresAt": expires,
        "有効期限": expires,
        "ipAddress": ip_address or "—",
        "IPアドレス": ip_address or "—",
        "ip": ip_address or "—",
        "deviceName": device,
        "端末名": device,
        "browser": browser,
        "ブラウザ": browser,
        "os": os_name,
        "OS": os_name,
        "region": region or "—",
        "地域": region or "—",
        "verifyUrl": verify_url or "",
        "認証URL": verify_url or "",
        "url": verify_url or reset_url or account_url or contact_url,
        "resetUrl": reset_url or "",
        "再設定URL": reset_url or "",
        "accountUrl": account_url,
        "contactUrl": contact_url,
        "お問い合わせURL": contact_url,
    }

    member_info = _build_member_info_block_for_event(event_key, ctx)
    btn_list = buttons if buttons is not None else _default_member_buttons(event_key, {**ctx, "contactUrl": contact_url})

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": _mask_email(email),
        "メールアドレス": _mask_email(email),
        "bodyTitle": title,
        "bodyDescription": desc,
        "memberInfoBlock": member_info,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color or brand.brand_color or "#ca8a04"),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **ctx,
    }
    if extra:
        variables.update(extra)

    summary_lines = []
    for fk in MEMBER_EVENT_VISIBLE_FIELDS.get(event_key, []):
        if fk in MEMBER_INFO_FIELD_DEFS:
            label, var_key = MEMBER_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val and val != "—":
                summary_lines.append(f"{label}: {val}")

    variables["_text_body"] = build_text_body(
        name=name,
        body_title=title,
        body_description=desc,
        order_summary_lines=summary_lines or None,
        notes=notes.replace("<br>", "\n").replace("<br/>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n").replace("<br/>", "\n") if contact else "",
        buttons=btn_list,
    )
    return variables


def build_member_sample_variables(template_key: str) -> dict[str, Any]:
    template_key = normalize_template_key(template_key)
    event = get_member_email_event(template_key)
    event_key = event.event_key if event else template_key

    sample_ctx = {
        "eventAt": "2026/08/03 14:30",
        "日時": "2026/08/03 14:30",
        "date": "2026/08/03 14:30",
        "expiresAt": "2026/08/03 15:30",
        "有効期限": "2026/08/03 15:30",
        "ipAddress": "203.0.113.1",
        "IPアドレス": "203.0.113.1",
        "deviceName": "PC",
        "端末名": "PC",
        "browser": "Chrome",
        "ブラウザ": "Chrome",
        "os": "Windows",
        "OS": "Windows",
        "region": "東京都",
        "地域": "東京都",
        "verifyUrl": f"{settings.FRONTEND_URL or 'https://example.com'}/verify/sample-token",
        "認証URL": f"{settings.FRONTEND_URL or 'https://example.com'}/verify/sample-token",
        "resetUrl": f"{settings.FRONTEND_URL or 'https://example.com'}/reset/sample-token",
        "再設定URL": f"{settings.FRONTEND_URL or 'https://example.com'}/reset/sample-token",
        "accountUrl": f"{settings.FRONTEND_URL or 'https://example.com'}/account",
        "contactUrl": settings.FRONTEND_URL or "https://example.com/contact",
        "お問い合わせURL": settings.FRONTEND_URL or "https://example.com/contact",
    }

    member_info = _build_member_info_block_for_event(event_key, sample_ctx)
    buttons = _default_member_buttons(event_key, sample_ctx)

    variables: dict[str, Any] = {
        "name": "山田 太郎",
        "ユーザー名": "山田 太郎",
        "email": "y***o@example.com",
        "メールアドレス": "y***o@example.com",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "memberInfoBlock": member_info,
        "buttonsBlock": build_buttons_block(buttons, brand_color="#ca8a04"),
        "notesBlock": build_notes_block("（注意事項を入力してください）"),
        "contactBlock": build_contact_block("（お問い合わせ案内を入力してください）"),
        "signatureBlock": build_signature_block("（署名）"),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **sample_ctx,
    }
    return variables


def member_variables_for_template(template_key: str) -> list[str]:
    template_key = normalize_template_key(template_key)
    base = [
        "name", "email", "bodyTitle", "bodyDescription",
        "memberInfoBlock", "buttonsBlock", "notesBlock", "contactBlock", "signatureBlock",
        "eventAt", "expiresAt", "ipAddress", "deviceName", "browser", "os", "region",
        "verifyUrl", "resetUrl", "contactUrl", "accountUrl",
    ]
    if get_member_email_event(template_key):
        return base
    return base
