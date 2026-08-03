"""Buyback email auto-send preferences (admin-configurable per event)."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

import models_buyback
from services.buyback_email_registry import all_auto_send_defaults

logger = logging.getLogger(__name__)


def _get_channel_settings(db: Session) -> models_buyback.BuybackChannelSettings:
    row = db.query(models_buyback.BuybackChannelSettings).filter(
        models_buyback.BuybackChannelSettings.id == 1
    ).first()
    if row is None:
        row = models_buyback.BuybackChannelSettings(id=1)
        db.add(row)
        db.flush()
    return row


def get_auto_send_settings(db: Session) -> dict[str, bool]:
    defaults = all_auto_send_defaults()
    row = _get_channel_settings(db)
    raw = getattr(row, "email_auto_send_json", None) or ""
    if not raw:
        return defaults
    try:
        overrides = json.loads(raw)
        if isinstance(overrides, dict):
            merged = {**defaults}
            for key, value in overrides.items():
                if key in defaults and isinstance(value, bool):
                    merged[key] = value
            return merged
    except json.JSONDecodeError:
        logger.warning("Invalid buyback email_auto_send_json")
    return defaults


def update_auto_send_settings(db: Session, updates: dict[str, bool]) -> dict[str, bool]:
    current = get_auto_send_settings(db)
    for key, value in updates.items():
        if key in current and isinstance(value, bool):
            current[key] = value
    row = _get_channel_settings(db)
    row.email_auto_send_json = json.dumps(current, ensure_ascii=False)
    return current


def should_auto_send(db: Session, event_key: str, *, explicit: bool | None = None) -> bool:
    """explicit=True/False overrides admin defaults; None uses stored preference."""
    if explicit is not None:
        return explicit
    settings_map = get_auto_send_settings(db)
    return settings_map.get(event_key, True)
