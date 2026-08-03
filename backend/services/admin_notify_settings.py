"""Admin notification settings: auto-send, channel, and recipient preferences."""

from __future__ import annotations

import json
import logging
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from services.email_delivery import get_brand_settings
from services.admin_notify_email_registry import all_auto_send_defaults, all_channel_defaults

logger = logging.getLogger(__name__)

NotifyChannel = Literal["email", "in_app", "both"]
RecipientMode = Literal["all_admins", "by_permission", "assignee_only", "custom_emails"]


class RecipientConfig(TypedDict, total=False):
    mode: RecipientMode
    permission_codes: list[str]
    custom_emails: list[str]


DEFAULT_RECIPIENT: RecipientConfig = {"mode": "all_admins", "permission_codes": [], "custom_emails": []}


def _load_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logger.warning("Invalid admin notify JSON settings")
        return {}


def get_auto_send_settings(db: Session) -> dict[str, bool]:
    defaults = all_auto_send_defaults()
    brand = get_brand_settings(db)
    overrides = _load_json(getattr(brand, "admin_notify_email_auto_send_json", None))
    merged = {**defaults}
    for key, value in overrides.items():
        if key in defaults and isinstance(value, bool):
            merged[key] = value
    return merged


def update_auto_send_settings(db: Session, updates: dict[str, bool]) -> dict[str, bool]:
    current = get_auto_send_settings(db)
    for key, value in updates.items():
        if key in current and isinstance(value, bool):
            current[key] = value
    brand = get_brand_settings(db)
    brand.admin_notify_email_auto_send_json = json.dumps(current, ensure_ascii=False)
    return current


def should_auto_send_email(db: Session, event_key: str, *, explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    return get_auto_send_settings(db).get(event_key, True)


def get_channel_settings(db: Session) -> dict[str, str]:
    defaults = all_channel_defaults()
    brand = get_brand_settings(db)
    overrides = _load_json(getattr(brand, "admin_notify_channel_json", None))
    merged = {**defaults}
    for key, value in overrides.items():
        if key in defaults and value in ("email", "in_app", "both"):
            merged[key] = value
    return merged


def update_channel_settings(db: Session, updates: dict[str, str]) -> dict[str, str]:
    current = get_channel_settings(db)
    for key, value in updates.items():
        if key in current and value in ("email", "in_app", "both"):
            current[key] = value
    brand = get_brand_settings(db)
    brand.admin_notify_channel_json = json.dumps(current, ensure_ascii=False)
    return current


def get_channel_for_event(db: Session, event_key: str) -> NotifyChannel:
    return get_channel_settings(db).get(event_key, "both")  # type: ignore[return-value]


def get_recipient_settings(db: Session) -> dict[str, RecipientConfig]:
    brand = get_brand_settings(db)
    raw = _load_json(getattr(brand, "admin_notify_recipients_json", None))
    defaults = all_auto_send_defaults()
    merged: dict[str, RecipientConfig] = {"_default": dict(DEFAULT_RECIPIENT)}
    for key in defaults:
        merged[key] = dict(DEFAULT_RECIPIENT)
    for key, value in raw.items():
        if isinstance(value, dict):
            merged[key] = {
                "mode": value.get("mode", "all_admins"),
                "permission_codes": value.get("permission_codes") or [],
                "custom_emails": value.get("custom_emails") or [],
            }
    return merged


def update_recipient_settings(db: Session, updates: dict[str, RecipientConfig]) -> dict[str, RecipientConfig]:
    current = get_recipient_settings(db)
    for key, value in updates.items():
        if not isinstance(value, dict):
            continue
        mode = value.get("mode", "all_admins")
        if mode not in ("all_admins", "by_permission", "assignee_only", "custom_emails"):
            continue
        current[key] = {
            "mode": mode,
            "permission_codes": list(value.get("permission_codes") or []),
            "custom_emails": list(value.get("custom_emails") or []),
        }
    brand = get_brand_settings(db)
    brand.admin_notify_recipients_json = json.dumps(current, ensure_ascii=False)
    return current


def get_recipient_config_for_event(db: Session, event_key: str) -> RecipientConfig:
    settings_map = get_recipient_settings(db)
    return settings_map.get(event_key) or settings_map.get("_default") or dict(DEFAULT_RECIPIENT)
