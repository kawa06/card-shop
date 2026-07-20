"""Import buylist products from Firestore JSON export into PostgreSQL (Phase 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

import models_buyback


@dataclass
class FirestoreImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    price_rows_upserted: int = 0
    image_failures: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_price(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        price = int(value)
    except (TypeError, ValueError):
        return None
    if price < 0:
        return None
    return price


def _visible_conditions(item: dict) -> list[dict]:
    rows: list[dict] = []
    for cond in item.get("conditionPrices") or []:
        if cond.get("isVisible") is False:
            continue
        code = (cond.get("conditionCode") or cond.get("conditionName") or "").strip()
        if not code:
            continue
        price = _parse_price(cond.get("price"))
        if price is None:
            continue
        rows.append(
            {
                "condition_code": code,
                "price_normal": price,
                "purchase_limit": _parse_price(cond.get("purchaseLimit")),
            }
        )

    if rows:
        return rows

    legacy_price = _parse_price(item.get("price"))
    if legacy_price is not None:
        return [{"condition_code": "default", "price_normal": legacy_price, "purchase_limit": None}]
    return []


def _resolve_image(item: dict, images: dict[str, str]) -> Optional[str]:
    item_id = item.get("id")
    if item_id is not None:
        mapped = images.get(str(item_id))
        if mapped:
            return mapped
    for key in ("image", "imageUrl"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def import_firestore_buylist_export(
    db: Session,
    payload: dict,
    *,
    dry_run: bool = False,
) -> FirestoreImportResult:
    """
    Import products from export JSON.

    Expected shape::
        {
          "items": [ ... buylist/main items ... ],
          "images": { "123": "data:image/jpeg;base64,..." }
        }
    """
    result = FirestoreImportResult()
    items = payload.get("items") or []
    images = payload.get("images") or {}

    if not isinstance(items, list):
        result.errors.append("items must be a list")
        return result

    for raw in items:
        if not isinstance(raw, dict):
            result.skipped += 1
            continue

        item_id = raw.get("id")
        if item_id is None:
            result.errors.append("item missing id")
            result.skipped += 1
            continue

        firestore_id = str(item_id)
        name = (raw.get("name") or firestore_id).strip()
        category = (raw.get("category") or "raw").strip()
        is_active = raw.get("isPublished", True) is not False
        sort_order = int(raw.get("sortOrder") or raw.get("id") or 0)
        notes = (raw.get("note") or raw.get("notes") or "").strip() or None

        image_url = _resolve_image(raw, images)
        if raw.get("hasImage") and not image_url:
            result.image_failures.append(f"{firestore_id}: hasImage=true but no image data")

        product = (
            db.query(models_buyback.BuybackProduct)
            .filter(models_buyback.BuybackProduct.firestore_item_id == firestore_id)
            .first()
        )
        is_new = product is None
        if is_new:
            product = models_buyback.BuybackProduct(firestore_item_id=firestore_id)
            db.add(product)

        product.name = name
        product.category = category
        product.is_active = is_active
        product.sort_order = sort_order
        product.notes = notes
        product.updated_at = datetime.utcnow()
        if image_url:
            product.image_url = image_url
        elif is_new:
            product.image_url = None

        db.flush()

        conditions = _visible_conditions(raw)
        if not conditions:
            result.skipped += 1
            result.errors.append(f"{firestore_id}: no importable prices")
            continue

        for cond in conditions:
            price_row = (
                db.query(models_buyback.BuybackProductPrice)
                .filter(
                    models_buyback.BuybackProductPrice.product_id == product.id,
                    models_buyback.BuybackProductPrice.condition_code == cond["condition_code"],
                )
                .first()
            )
            if price_row is None:
                price_row = models_buyback.BuybackProductPrice(
                    product_id=product.id,
                    condition_code=cond["condition_code"],
                )
                db.add(price_row)
            price_row.price_normal = cond["price_normal"]
            price_row.purchase_limit = cond["purchase_limit"]
            result.price_rows_upserted += 1

        if is_new:
            result.created += 1
        else:
            result.updated += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return result


def validate_import_counts(db: Session, payload: dict) -> dict[str, int]:
    """Compare export item count with active DB rows keyed by firestore_item_id."""
    items = payload.get("items") or []
    export_ids = {str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id") is not None}
    db_rows = (
        db.query(models_buyback.BuybackProduct)
        .filter(models_buyback.BuybackProduct.firestore_item_id.isnot(None))
        .all()
    )
    db_ids = {row.firestore_item_id for row in db_rows if row.firestore_item_id}
    return {
        "export_count": len(export_ids),
        "db_count": len(db_ids),
        "missing_in_db": len(export_ids - db_ids),
        "extra_in_db": len(db_ids - export_ids),
    }
