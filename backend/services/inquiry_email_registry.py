"""Inquiry / contact email event registry — extensible for future support channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

InquiryEmailCategory = Literal["inquiry", "other"]
SupportChannel = Literal["email", "chat", "ai", "phone", "line", "discord"]


@dataclass(frozen=True)
class InquiryEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    category: InquiryEmailCategory = "inquiry"
    auto_send_default: bool = True
    support_channel: SupportChannel = "email"


LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "inquiry_reply": "inquiry_admin_reply",
}


INQUIRY_EMAIL_EVENTS: dict[str, InquiryEmailEventDef] = {
    "inquiry_received": InquiryEmailEventDef(
        "inquiry_received", "inquiry_received", "お問い合わせ受付完了", "inquiry"
    ),
    "inquiry_admin_reply": InquiryEmailEventDef(
        "inquiry_admin_reply", "inquiry_admin_reply", "管理者から返信", "inquiry"
    ),
    "inquiry_info_request": InquiryEmailEventDef(
        "inquiry_info_request", "inquiry_info_request", "追加情報のお願い", "inquiry"
    ),
    "inquiry_attachment_received": InquiryEmailEventDef(
        "inquiry_attachment_received", "inquiry_attachment_received", "添付ファイル受領", "inquiry"
    ),
    "inquiry_in_progress": InquiryEmailEventDef(
        "inquiry_in_progress", "inquiry_in_progress", "対応中", "inquiry"
    ),
    "inquiry_on_hold": InquiryEmailEventDef(
        "inquiry_on_hold", "inquiry_on_hold", "対応保留", "inquiry"
    ),
    "inquiry_resolved": InquiryEmailEventDef(
        "inquiry_resolved", "inquiry_resolved", "対応完了", "inquiry"
    ),
    "inquiry_closed": InquiryEmailEventDef(
        "inquiry_closed", "inquiry_closed", "お問い合わせ終了", "inquiry"
    ),
    "inquiry_reopened": InquiryEmailEventDef(
        "inquiry_reopened", "inquiry_reopened", "お問い合わせ再開", "inquiry"
    ),
    "inquiry_cancelled": InquiryEmailEventDef(
        "inquiry_cancelled", "inquiry_cancelled", "お問い合わせキャンセル", "inquiry"
    ),
    "inquiry_system_error": InquiryEmailEventDef(
        "inquiry_system_error",
        "inquiry_system_error",
        "システムエラー",
        "other",
        auto_send_default=False,
    ),
}


STATUS_DEFAULT_EVENT: dict[str, str] = {
    "in_progress": "inquiry_in_progress",
    "waiting_customer": "inquiry_info_request",
    "resolved": "inquiry_resolved",
    "closed": "inquiry_closed",
}


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def resolve_inquiry_template_key(event_key: str) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = INQUIRY_EMAIL_EVENTS.get(key)
    if event:
        return event.default_template_key
    return key


def get_inquiry_email_event(event_key: str) -> Optional[InquiryEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return INQUIRY_EMAIL_EVENTS.get(key)


def is_inquiry_template_key(template_key: str) -> bool:
    normalized = normalize_template_key(template_key)
    if normalized in INQUIRY_EMAIL_EVENTS:
        return True
    return normalized.startswith("inquiry_")


def all_auto_send_defaults() -> dict[str, bool]:
    return {ev.event_key: ev.auto_send_default for ev in INQUIRY_EMAIL_EVENTS.values()}


def resolve_event_for_status(new_status: str, *, explicit_template_key: str | None = None) -> str | None:
    if explicit_template_key:
        normalized = normalize_template_key(explicit_template_key)
        if normalized in INQUIRY_EMAIL_EVENTS:
            return normalized
    return STATUS_DEFAULT_EVENT.get(new_status)
