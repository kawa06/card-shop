"""Buylist shop display settings (notice text, shop name, etc.)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models_buyback

DEFAULT_SHOP_KEY = "main"
DEFAULT_SHOP_NAME = "KRX TCG"
DEFAULT_SHOP_SLUG = "card-vault"
DEFAULT_NOTICE_TEXT = "実際の買取価格は、店舗での査定結果により変動する場合があります。"


def get_or_create_shop_settings(db: Session) -> models_buyback.BuybackShopSettings:
    row = (
        db.query(models_buyback.BuybackShopSettings)
        .filter(models_buyback.BuybackShopSettings.id == 1)
        .first()
    )
    if row:
        return row
    row = models_buyback.BuybackShopSettings(
        id=1,
        shop_key=DEFAULT_SHOP_KEY,
        name=DEFAULT_SHOP_NAME,
        slug=DEFAULT_SHOP_SLUG,
        notice_text=DEFAULT_NOTICE_TEXT,
        show_notice=True,
    )
    db.add(row)
    db.flush()
    return row


def serialize_shop_settings(row: models_buyback.BuybackShopSettings) -> dict:
    return {
        "id": row.shop_key or DEFAULT_SHOP_KEY,
        "name": row.name or DEFAULT_SHOP_NAME,
        "slug": row.slug or DEFAULT_SHOP_SLUG,
        "notice_text": row.notice_text or "",
        "show_notice": bool(row.show_notice),
        "updated_at": row.updated_at,
    }


def update_shop_settings(
    db: Session,
    *,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    notice_text: Optional[str] = None,
    show_notice: Optional[bool] = None,
) -> models_buyback.BuybackShopSettings:
    row = get_or_create_shop_settings(db)
    if name is not None:
        row.name = name.strip() or DEFAULT_SHOP_NAME
    if slug is not None:
        row.slug = slug.strip() or DEFAULT_SHOP_SLUG
    if notice_text is not None:
        row.notice_text = notice_text
    if show_notice is not None:
        row.show_notice = show_notice
    row.updated_at = datetime.utcnow()
    db.flush()
    return row
