"""Shipping/delivery email event registry — extensible without changing send code."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ShippingEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    status_flag: str = ""
    carrier_templates: dict[str, str] = field(default_factory=dict)


# Legacy template keys → new shipping templates (backward compatible)
LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "order_shipped": "shipping_shipped",
    "order_shipping_prep": "shipping_preparing",
    "order_tracking": "shipping_tracking_issued",
    "order_delivered": "shipping_delivered",
}


SHIPPING_EMAIL_EVENTS: dict[str, ShippingEmailEventDef] = {
    "shipping_preparing": ShippingEmailEventDef(
        "shipping_preparing", "shipping_preparing", "発送準備中", "shipping_preparing_ok"
    ),
    "shipping_shipped": ShippingEmailEventDef(
        "shipping_shipped", "shipping_shipped", "発送完了", "shipping_ok"
    ),
    "shipping_handed_to_carrier": ShippingEmailEventDef(
        "shipping_handed_to_carrier", "shipping_handed_to_carrier", "配送会社引渡し完了"
    ),
    "shipping_tracking_issued": ShippingEmailEventDef(
        "shipping_tracking_issued", "shipping_tracking_issued", "追跡番号発行"
    ),
    "shipping_delivered": ShippingEmailEventDef(
        "shipping_delivered", "shipping_delivered", "配達完了", "shipping_delivered_ok"
    ),
    "shipping_delay_notice": ShippingEmailEventDef(
        "shipping_delay_notice", "shipping_delay_notice", "配送遅延のお知らせ"
    ),
    "shipping_address_issue": ShippingEmailEventDef(
        "shipping_address_issue", "shipping_address_issue", "住所不備のお知らせ"
    ),
    "shipping_absence_return": ShippingEmailEventDef(
        "shipping_absence_return", "shipping_absence_return", "長期不在による持ち戻り"
    ),
    "shipping_return_started": ShippingEmailEventDef(
        "shipping_return_started", "shipping_return_started", "返送開始"
    ),
    "shipping_return_completed": ShippingEmailEventDef(
        "shipping_return_completed", "shipping_return_completed", "返送完了"
    ),
}


def resolve_shipping_template_key(
    event_key: str,
    carrier_id: str | None = None,
) -> str:
    if event_key in LEGACY_TEMPLATE_ALIASES:
        event_key = LEGACY_TEMPLATE_ALIASES[event_key]
    event = SHIPPING_EMAIL_EVENTS.get(event_key)
    if not event:
        return event_key
    cid = (carrier_id or "").strip().lower()
    if cid and cid in event.carrier_templates:
        return event.carrier_templates[cid]
    return event.default_template_key


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def get_shipping_email_event(event_key: str) -> Optional[ShippingEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return SHIPPING_EMAIL_EVENTS.get(key)
