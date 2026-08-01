#!/usr/bin/env python3
"""Seed buyback channel settings and starter promo banners (idempotent)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from database import SessionLocal
from services.buyback_channel import (
    create_banner,
    get_or_create_channel_settings,
    list_all_banners_admin,
    update_channel_settings,
)


def main() -> None:
    db = SessionLocal()
    try:
        settings = update_channel_settings(
            db,
            store_enabled=True,
            mail_enabled=True,
            slot_interval_minutes=30,
            business_hours={
                "mon": {"open": "10:00", "close": "19:00", "closed": False},
                "tue": {"open": "10:00", "close": "19:00", "closed": False},
                "wed": {"open": "10:00", "close": "19:00", "closed": False},
                "thu": {"open": "10:00", "close": "19:00", "closed": False},
                "fri": {"open": "10:00", "close": "19:00", "closed": False},
                "sat": {"open": "10:00", "close": "19:00", "closed": False},
                "sun": {"open": "10:00", "close": "19:00", "closed": True},
            },
            closed_dates=[],
        )
        print(
            f"channel_settings: mode store={settings.store_enabled} mail={settings.mail_enabled} interval={settings.slot_interval_minutes}m"
        )

        existing = list_all_banners_admin(db)
        if existing:
            print(f"banners: skipped ({len(existing)} already exist)")
        else:
            now = datetime.utcnow()
            samples = [
                {
                    "title": "店舗買取限定価格",
                    "description": "買取価格10%UP",
                    "target_channel": "store",
                    "starts_at": now,
                    "ends_at": now + timedelta(days=14),
                    "background_color": "#1a1a2e",
                    "text_color": "#ffffff",
                    "sort_order": 1,
                },
                {
                    "title": "郵送買取限定価格",
                    "description": "人気カード買取強化中",
                    "target_channel": "mail",
                    "starts_at": now,
                    "ends_at": now + timedelta(days=10),
                    "background_color": "#0f3460",
                    "text_color": "#ffffff",
                    "sort_order": 2,
                },
            ]
            for sample in samples:
                banner = create_banner(db, is_visible=True, **sample)
                print(f"banner_created: id={banner.id} title={banner.title!r}")
        db.commit()
        print("seed_ok")
    except Exception as exc:
        db.rollback()
        print(f"seed_failed: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
