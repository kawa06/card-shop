"""Barcode scan tokens for buyback logistics."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models_buyback


def generate_scan_token() -> str:
    return secrets.token_urlsafe(32)


def create_barcode(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    barcode_type: str,
    human_readable: Optional[str] = None,
) -> models_buyback.BuybackBarcode:
    for _ in range(10):
        token = generate_scan_token()
        exists = (
            db.query(models_buyback.BuybackBarcode.id)
            .filter(models_buyback.BuybackBarcode.scan_token == token)
            .first()
        )
        if exists:
            continue
        row = models_buyback.BuybackBarcode(
            scan_token=token,
            barcode_type=barcode_type,
            entity_type=entity_type,
            entity_id=entity_id,
            human_readable=human_readable,
        )
        db.add(row)
        db.flush()
        return row

    raise RuntimeError("Failed to generate unique scan token")


def get_active_barcode_for_entity(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    barcode_type: Optional[str] = None,
) -> models_buyback.BuybackBarcode | None:
    query = db.query(models_buyback.BuybackBarcode).filter(
        models_buyback.BuybackBarcode.entity_type == entity_type,
        models_buyback.BuybackBarcode.entity_id == entity_id,
        models_buyback.BuybackBarcode.is_active.is_(True),
    )
    if barcode_type:
        query = query.filter(models_buyback.BuybackBarcode.barcode_type == barcode_type)
    return query.order_by(models_buyback.BuybackBarcode.created_at.desc()).first()


def lookup_barcode_by_token(
    db: Session, scan_token: str
) -> models_buyback.BuybackBarcode | None:
    token = (scan_token or "").strip()
    if not token:
        return None
    return (
        db.query(models_buyback.BuybackBarcode)
        .filter(
            models_buyback.BuybackBarcode.scan_token == token,
            models_buyback.BuybackBarcode.is_active.is_(True),
        )
        .first()
    )


def revoke_barcode(db: Session, barcode: models_buyback.BuybackBarcode) -> None:
    barcode.is_active = False
    barcode.revoked_at = datetime.utcnow()
    barcode.updated_at = datetime.utcnow()
