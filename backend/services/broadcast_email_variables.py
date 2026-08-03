"""Build announcement/campaign broadcast email template variables."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Optional

import models
from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_broadcast_info_block,
    build_buttons_block,
    build_contact_block,
    build_image_block,
    build_notes_block,
    build_signature_block,
    build_text_body,
)
from services.broadcast_email_registry import get_broadcast_email_event, normalize_template_key

BROADCAST_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "publishedAt": ("公開日時", "publishedAt"),
    "startAt": ("開始日時", "startAt"),
    "endAt": ("終了日時", "endAt"),
    "eventAt": ("日時", "eventAt"),
}

BROADCAST_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "broadcast_notice_important": ["publishedAt"],
    "broadcast_notice_urgent": ["publishedAt"],
    "broadcast_maintenance_scheduled": ["startAt", "endAt"],
    "broadcast_maintenance_started": ["startAt"],
    "broadcast_maintenance_ended": ["endAt"],
    "broadcast_service_incident": ["eventAt"],
    "broadcast_incident_recovered": ["eventAt"],
    "broadcast_terms_important": ["publishedAt"],
    "broadcast_privacy_important": ["publishedAt"],
    "broadcast_promo_start": ["startAt", "endAt"],
    "broadcast_promo_ending_soon": ["endAt"],
    "broadcast_promo_ended": ["endAt"],
    "broadcast_promo_limited_event": ["startAt", "endAt"],
    "broadcast_promo_limited_sale": ["startAt", "endAt"],
    "broadcast_promo_new_product": ["publishedAt"],
    "broadcast_promo_new_feature": ["publishedAt"],
    "broadcast_system_error": ["eventAt"],
}

RAW_BROADCAST_VARIABLE_KEYS = frozenset({
    "broadcastInfoBlock",
    "imageBlock",
    "noticeContent",
    "content",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
})


def _format_jst(dt: datetime | None = None) -> str:
    value = dt or datetime.utcnow()
    return value.strftime("%Y/%m/%d %H:%M")


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def _collect_image_urls(announcement: models.Announcement | None) -> list[str]:
    if not announcement:
        return []
    urls: list[str] = []
    if announcement.thumbnail:
        urls.append(announcement.thumbnail)
    for img in getattr(announcement, "images", []) or []:
        if img.image_url and img.image_url not in urls:
            urls.append(img.image_url)
    return urls


def _default_buttons(ctx: dict[str, str]) -> list[dict[str, str]]:
    url = ctx.get("url") or ctx.get("URL") or ""
    contact_url = ctx.get("contactUrl") or ""
    if url:
        return [{"text": "（ボタンラベル）", "url": url}]
    if contact_url:
        return [{"text": "（ボタンラベル）", "url": contact_url}]
    return []


def _build_info_block(template_key: str, ctx: dict[str, str]) -> str:
    rows: list[tuple[str, str]] = []
    for fk in BROADCAST_EVENT_VISIBLE_FIELDS.get(template_key, []):
        if fk not in BROADCAST_INFO_FIELD_DEFS:
            continue
        label, var_key = BROADCAST_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if value:
            rows.append((label, html.escape(str(value))))
    return build_broadcast_info_block(rows)


def build_broadcast_email_variables(
    db,
    *,
    template_key: str,
    user: models.User | None = None,
    announcement: models.Announcement | None = None,
    to_email: str | None = None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template_key = normalize_template_key(template_key)
    name = (user.name if user else None) or "お客"
    email = to_email or (user.email if user else "")
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()

    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    ann_title = ""
    ann_content = ""
    if announcement:
        ann_title = announcement.title_ja or announcement.title or ""
        ann_content = announcement.content_ja or announcement.content or ""
        title = body_title or ann_title or p_title
        desc = body_description or p_desc

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    contact_url = brand.contact_url or settings.FRONTEND_URL or ""
    base_url = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""
    detail_url = f"{base_url}/mypage/announcements/{announcement.id}" if announcement and base_url else base_url

    published_at = _format_jst(getattr(announcement, "publish_at", None) or getattr(announcement, "created_at", None))
    start_at = _format_jst(getattr(announcement, "publish_at", None))
    end_at = _format_jst(getattr(announcement, "expire_at", None)) if announcement and announcement.expire_at else ""
    event_at = _format_jst()

    ctx = {
        "publishedAt": published_at,
        "公開日時": published_at,
        "startAt": start_at,
        "開始日時": start_at,
        "endAt": end_at,
        "終了日時": end_at,
        "eventAt": event_at,
        "日時": event_at,
        "date": event_at,
        "url": detail_url,
        "URL": detail_url,
        "contactUrl": contact_url,
        "お問い合わせURL": contact_url,
    }

    image_urls = _collect_image_urls(announcement)
    image_block = build_image_block(image_urls)
    info_block = _build_info_block(template_key, ctx)
    btn_list = buttons if buttons is not None else _default_buttons(ctx)

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": email,
        "noticeTitle": ann_title,
        "お知らせタイトル": ann_title,
        "title": ann_title,
        "noticeContent": ann_content,
        "content": ann_content,
        "bodyTitle": title,
        "bodyDescription": desc,
        "broadcastInfoBlock": info_block,
        "imageBlock": image_block,
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
    if ann_title:
        summary_lines.append(f"お知らせ: {ann_title}")
    for fk in BROADCAST_EVENT_VISIBLE_FIELDS.get(template_key, []):
        if fk in BROADCAST_INFO_FIELD_DEFS:
            label, var_key = BROADCAST_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val:
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


def build_broadcast_sample_variables(template_key: str) -> dict[str, Any]:
    template_key = normalize_template_key(template_key)
    base_url = settings.FRONTEND_URL or "https://example.com"
    sample_ctx = {
        "publishedAt": "2026/08/03 10:00",
        "公開日時": "2026/08/03 10:00",
        "startAt": "2026/08/01 00:00",
        "開始日時": "2026/08/01 00:00",
        "endAt": "2026/08/31 23:59",
        "終了日時": "2026/08/31 23:59",
        "eventAt": "2026/08/03 14:30",
        "日時": "2026/08/03 14:30",
        "url": f"{base_url}/mypage/announcements/1",
        "URL": f"{base_url}/mypage/announcements/1",
        "contactUrl": f"{base_url}/contact",
        "お問い合わせURL": f"{base_url}/contact",
    }
    info_block = _build_info_block(template_key, sample_ctx)
    buttons = _default_buttons(sample_ctx)
    sample_images = [f"{base_url}/placeholder-announcement.jpg"]

    return {
        "name": "山田 太郎",
        "ユーザー名": "山田 太郎",
        "email": "sample@example.com",
        "noticeTitle": "サンプルお知らせタイトル",
        "お知らせタイトル": "サンプルお知らせタイトル",
        "title": "サンプルお知らせタイトル",
        "noticeContent": "<p>（お知らせ本文を入力してください）</p>",
        "content": "<p>（お知らせ本文を入力してください）</p>",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "broadcastInfoBlock": info_block,
        "imageBlock": build_image_block(sample_images),
        "buttonsBlock": build_buttons_block(buttons, brand_color="#ca8a04"),
        "notesBlock": build_notes_block("（注意事項を入力してください）"),
        "contactBlock": build_contact_block("（お問い合わせ案内を入力してください）"),
        "signatureBlock": build_signature_block("（署名）"),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **sample_ctx,
    }


def broadcast_variables_for_template(template_key: str) -> list[str]:
    return [
        "name", "email", "noticeTitle", "noticeContent", "content", "bodyTitle", "bodyDescription",
        "broadcastInfoBlock", "imageBlock", "buttonsBlock", "notesBlock", "contactBlock", "signatureBlock",
        "publishedAt", "startAt", "endAt", "eventAt", "url", "contactUrl",
    ]
