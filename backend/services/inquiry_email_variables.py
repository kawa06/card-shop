"""Build inquiry email template variables — privacy-safe, no attachment URLs."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Optional

import models
from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_attachment_block,
    build_buttons_block,
    build_contact_block,
    build_inquiry_info_block,
    build_notes_block,
    build_signature_block,
    build_text_body,
)
from services.inquiry_constants import INQUIRY_CATEGORY_LABELS
from services.inquiry_email_registry import get_inquiry_email_event, normalize_template_key

INQUIRY_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "inquiryNo": ("お問い合わせ番号", "inquiryNo"),
    "inquiryCategory": ("お問い合わせ種別", "inquiryCategory"),
    "receivedAt": ("受付日時", "receivedAt"),
    "repliedAt": ("返信日時", "repliedAt"),
    "assignedAdmin": ("担当者", "assignedAdmin"),
    "inquirySubject": ("件名", "inquirySubject"),
    "relatedOrderNo": ("関連注文", "relatedOrderNo"),
    "supportChannel": ("サポート", "supportChannel"),
}

INQUIRY_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "inquiry_received": ["inquiryNo", "inquiryCategory", "receivedAt", "inquirySubject"],
    "inquiry_admin_reply": ["inquiryNo", "repliedAt", "assignedAdmin"],
    "inquiry_info_request": ["inquiryNo", "repliedAt", "assignedAdmin"],
    "inquiry_attachment_received": ["inquiryNo", "receivedAt"],
    "inquiry_in_progress": ["inquiryNo", "assignedAdmin"],
    "inquiry_on_hold": ["inquiryNo", "assignedAdmin"],
    "inquiry_resolved": ["inquiryNo", "repliedAt", "assignedAdmin"],
    "inquiry_closed": ["inquiryNo", "repliedAt"],
    "inquiry_reopened": ["inquiryNo", "receivedAt"],
    "inquiry_cancelled": ["inquiryNo", "receivedAt"],
    "inquiry_system_error": ["inquiryNo", "receivedAt"],
}

RAW_INQUIRY_VARIABLE_KEYS = frozenset({
    "inquiryInfoBlock",
    "attachmentBlock",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "replyContent",
    "inquiryContent",
    "content",
})


def _format_jst(dt: datetime | None = None) -> str:
    value = dt or datetime.utcnow()
    return value.strftime("%Y/%m/%d %H:%M")


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _snippet(text: str, limit: int = 200) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def _category_label(category: str | None) -> str:
    if not category:
        return "—"
    return INQUIRY_CATEGORY_LABELS.get(category, category)


def _default_buttons(event_key: str, ctx: dict[str, str]) -> list[dict[str, str]]:
    inquiry_url = ctx.get("inquiryUrl") or ""
    contact_url = ctx.get("contactUrl") or ""
    if inquiry_url:
        return [{"text": "（ボタンラベル）", "url": inquiry_url}]
    if contact_url:
        return [{"text": "（ボタンラベル）", "url": contact_url}]
    return []


def _build_info_block(template_key: str, ctx: dict[str, str]) -> str:
    rows: list[tuple[str, str]] = []
    for fk in INQUIRY_EVENT_VISIBLE_FIELDS.get(template_key, []):
        if fk not in INQUIRY_INFO_FIELD_DEFS:
            continue
        label, var_key = INQUIRY_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if value:
            rows.append((label, html.escape(str(value))))
    return build_inquiry_info_block(rows)


def build_inquiry_email_variables(
    db,
    inquiry: models.Inquiry | None,
    event_key: str,
    *,
    user: models.User | None = None,
    admin: models.User | None = None,
    to_email: str | None = None,
    reply_text: str | None = None,
    include_inquiry_content: bool = False,
    include_reply_content: bool = False,
    attachments: list[dict[str, Any]] | None = None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    support_channel: str = "email",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    name = (user.name if user else None) or "お客"
    email = to_email or (inquiry.reply_email if inquiry else "") or (user.email if user else "")
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db) if db is not None else None
    signature_html = (getattr(brand, "email_signature_html", None) if brand else None) or ""
    contact_url = (brand.contact_url if brand else None) or settings.FRONTEND_URL or ""
    brand_color = (brand.brand_color if brand else None) or "#ca8a04"
    base_url = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""
    inquiry_url = f"{base_url}/mypage/inquiries/{inquiry.id}" if inquiry and base_url else ""

    received_at = _format_jst(inquiry.created_at if inquiry else None)
    replied_at = _format_jst(inquiry.last_message_at if inquiry else None)
    assigned = admin.name if admin else (inquiry.assigned_admin.name if inquiry and inquiry.assigned_admin else "—")

    ctx = {
        "inquiryNo": inquiry.inquiry_number if inquiry else "INQ-SAMPLE-001",
        "inquiryCategory": _category_label(inquiry.category if inquiry else "other"),
        "receivedAt": received_at,
        "repliedAt": replied_at,
        "assignedAdmin": assigned,
        "inquirySubject": inquiry.subject if inquiry else "（件名）",
        "relatedOrderNo": inquiry.related_order_number if inquiry and inquiry.related_order_number else "",
        "supportChannel": support_channel,
        "inquiryUrl": inquiry_url,
        "contactUrl": contact_url,
    }

    inquiry_info = _build_info_block(event_key, ctx)
    attachment_rows = [
        (str(a.get("filename", "")), _format_file_size(int(a.get("size", 0))))
        for a in (attachments or [])
        if a.get("filename")
    ]
    attachment_block = build_attachment_block(attachment_rows)
    btn_list = buttons if buttons is not None else _default_buttons(event_key, ctx)

    inquiry_content = ""
    if include_inquiry_content and inquiry and inquiry.messages:
        first = next((m for m in inquiry.messages if m.sender_type == "customer" and not m.deleted_at), None)
        if first:
            inquiry_content = html.escape(_snippet(first.message))

    reply_content = ""
    if include_reply_content and reply_text:
        reply_content = html.escape(_snippet(reply_text))

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": email,
        "メールアドレス": email,
        "shopName": settings.SITE_NAME or "KRX TCG",
        "inquiryNo": ctx["inquiryNo"],
        "お問い合わせ番号": ctx["inquiryNo"],
        "inquiryCategory": ctx["inquiryCategory"],
        "お問い合わせ種別": ctx["inquiryCategory"],
        "receivedAt": received_at,
        "受付日時": received_at,
        "repliedAt": replied_at,
        "返信日時": replied_at,
        "assignedAdmin": assigned,
        "担当者": assigned,
        "inquiryUrl": inquiry_url,
        "お問い合わせURL": inquiry_url,
        "inquirySubject": ctx["inquirySubject"],
        "relatedOrderNo": ctx["relatedOrderNo"],
        "supportChannel": support_channel,
        "bodyTitle": title,
        "bodyDescription": desc,
        "inquiryInfoBlock": inquiry_info,
        "attachmentBlock": attachment_block,
        "inquiryContent": inquiry_content,
        "お問い合わせ内容": inquiry_content,
        "replyContent": reply_content,
        "返信内容": reply_content,
        "content": reply_content or inquiry_content,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "contactUrl": contact_url,
        "date": replied_at,
        "日時": replied_at,
    }
    if extra:
        variables.update(extra)

    summary_lines: list[str] = []
    for fk in INQUIRY_EVENT_VISIBLE_FIELDS.get(event_key, []):
        if fk in INQUIRY_INFO_FIELD_DEFS:
            label, var_key = INQUIRY_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val and val != "—":
                summary_lines.append(f"{label}: {val}")
    for filename, size in attachment_rows:
        summary_lines.append(f"添付: {filename} ({size})")
    if reply_content:
        summary_lines.append(f"返信: {reply_text[:200] if reply_text else ''}")

    event = get_inquiry_email_event(event_key)
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


def build_inquiry_sample_variables(template_key: str, db=None) -> dict[str, Any]:
    from services.inquiry_email_registry import INQUIRY_EMAIL_EVENTS

    key = normalize_template_key(template_key)
    event = INQUIRY_EMAIL_EVENTS.get(key)
    sample_attachments = [
        {"filename": "sample-image.png", "size": 245760},
        {"filename": "receipt.jpg", "size": 1048576},
    ]
    variables = build_inquiry_email_variables(
        None,
        None,
        key,
        include_inquiry_content=True,
        include_reply_content=key in {"inquiry_admin_reply", "inquiry_info_request"},
        reply_text="サンプル返信内容です。詳細はマイページよりご確認ください。",
        attachments=sample_attachments if key == "inquiry_attachment_received" else None,
        support_channel="email",
    )
    if event:
        variables["bodyTitle"] = f"（{event.description}）"
    return variables


def inquiry_variables_for_template(template_key: str) -> list[str]:
    sample = build_inquiry_sample_variables(template_key)
    return sorted(k for k in sample.keys() if not str(k).startswith("_"))
