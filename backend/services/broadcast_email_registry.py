"""Announcement / campaign broadcast email event registry — extensible without changing send code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

BroadcastEmailCategory = Literal["notice", "promo", "broadcast"]


@dataclass(frozen=True)
class BroadcastEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    category: BroadcastEmailCategory = "notice"


LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "announcement_broadcast": "broadcast_notice_important",
    "maintenance_notice": "broadcast_maintenance_scheduled",
    "incident_notice": "broadcast_service_incident",
    "incident_resolved": "broadcast_incident_recovered",
}


BROADCAST_EMAIL_EVENTS: dict[str, BroadcastEmailEventDef] = {
    # お知らせ
    "broadcast_notice_important": BroadcastEmailEventDef(
        "broadcast_notice_important", "broadcast_notice_important", "重要なお知らせ", "notice"
    ),
    "broadcast_notice_urgent": BroadcastEmailEventDef(
        "broadcast_notice_urgent", "broadcast_notice_urgent", "緊急のお知らせ", "notice"
    ),
    "broadcast_maintenance_scheduled": BroadcastEmailEventDef(
        "broadcast_maintenance_scheduled", "broadcast_maintenance_scheduled", "メンテナンス予定", "notice"
    ),
    "broadcast_maintenance_started": BroadcastEmailEventDef(
        "broadcast_maintenance_started", "broadcast_maintenance_started", "メンテナンス開始", "notice"
    ),
    "broadcast_maintenance_ended": BroadcastEmailEventDef(
        "broadcast_maintenance_ended", "broadcast_maintenance_ended", "メンテナンス終了", "notice"
    ),
    "broadcast_service_incident": BroadcastEmailEventDef(
        "broadcast_service_incident", "broadcast_service_incident", "サービス障害", "notice"
    ),
    "broadcast_incident_recovered": BroadcastEmailEventDef(
        "broadcast_incident_recovered", "broadcast_incident_recovered", "障害復旧", "notice"
    ),
    "broadcast_terms_important": BroadcastEmailEventDef(
        "broadcast_terms_important", "broadcast_terms_important", "重要な規約変更", "notice"
    ),
    "broadcast_privacy_important": BroadcastEmailEventDef(
        "broadcast_privacy_important", "broadcast_privacy_important", "重要なプライバシーポリシー変更", "notice"
    ),
    # キャンペーン
    "broadcast_promo_start": BroadcastEmailEventDef(
        "broadcast_promo_start", "broadcast_promo_start", "キャンペーン開始", "promo"
    ),
    "broadcast_promo_ending_soon": BroadcastEmailEventDef(
        "broadcast_promo_ending_soon", "broadcast_promo_ending_soon", "キャンペーン終了間近", "promo"
    ),
    "broadcast_promo_ended": BroadcastEmailEventDef(
        "broadcast_promo_ended", "broadcast_promo_ended", "キャンペーン終了", "promo"
    ),
    "broadcast_promo_limited_event": BroadcastEmailEventDef(
        "broadcast_promo_limited_event", "broadcast_promo_limited_event", "期間限定イベント", "promo"
    ),
    "broadcast_promo_limited_sale": BroadcastEmailEventDef(
        "broadcast_promo_limited_sale", "broadcast_promo_limited_sale", "限定販売", "promo"
    ),
    "broadcast_promo_new_product": BroadcastEmailEventDef(
        "broadcast_promo_new_product", "broadcast_promo_new_product", "新商品公開", "promo"
    ),
    "broadcast_promo_new_feature": BroadcastEmailEventDef(
        "broadcast_promo_new_feature", "broadcast_promo_new_feature", "新機能追加", "promo"
    ),
    # その他
    "broadcast_system_error": BroadcastEmailEventDef(
        "broadcast_system_error", "broadcast_system_error", "システムエラー", "broadcast"
    ),
}

DEFAULT_BROADCAST_TEMPLATE_KEY = "broadcast_notice_important"


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def resolve_broadcast_template_key(event_key: str) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = BROADCAST_EMAIL_EVENTS.get(key)
    if event:
        return event.default_template_key
    return key


def get_broadcast_email_event(event_key: str) -> Optional[BroadcastEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return BROADCAST_EMAIL_EVENTS.get(key)


def is_broadcast_template_key(template_key: str) -> bool:
    key = normalize_template_key(template_key)
    if key in BROADCAST_EMAIL_EVENTS:
        return True
    return key.startswith("broadcast_")


def default_template_for_announcement() -> str:
    return DEFAULT_BROADCAST_TEMPLATE_KEY
