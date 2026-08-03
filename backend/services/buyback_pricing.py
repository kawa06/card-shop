"""Buyback assessment pricing helpers (catalog lookup + condition discount rules)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models_buyback

CONDITION_ASSESSMENT_RATE_PERCENT: dict[str, int] = {
    "default": 100,
    "A": 100,
    "B": 92,
    "C": 85,
    "D": 75,
    "E": 60,
    "ジャンク": 40,
}


def _normalize_condition_code(code: str | None) -> str:
    return (code or "default").strip().casefold()


def lookup_catalog_price(
    db: Session,
    *,
    product_id: int | None,
    condition_code: str,
) -> int | None:
    if not product_id:
        return None
    rows = (
        db.query(models_buyback.BuybackProductPrice)
        .filter(models_buyback.BuybackProductPrice.product_id == product_id)
        .all()
    )
    normalized = _normalize_condition_code(condition_code)
    for candidate in rows:
        if _normalize_condition_code(candidate.condition_code) == normalized:
            return int(candidate.price_normal)
    return None


def _rate_percent(condition_code: str) -> int:
    code = (condition_code or "default").strip()
    if code in CONDITION_ASSESSMENT_RATE_PERCENT:
        return CONDITION_ASSESSMENT_RATE_PERCENT[code]
    normalized = _normalize_condition_code(code)
    for key, value in CONDITION_ASSESSMENT_RATE_PERCENT.items():
        if _normalize_condition_code(key) == normalized:
            return value
    return 100


def resolve_assessment_unit_price_for_condition_change(
    db: Session,
    item: models_buyback.BuybackRequestItem,
    *,
    previous_condition_code: str,
    new_condition_code: str,
) -> int:
    listed = max(int(item.listed_unit_price or 0), 0)
    if listed <= 0:
        return 0

    previous = (previous_condition_code or item.condition_code or "default").strip()
    target = (new_condition_code or previous).strip()
    if not target or _normalize_condition_code(target) == _normalize_condition_code(previous):
        return listed

    ref_catalog = lookup_catalog_price(
        db,
        product_id=item.product_id,
        condition_code=previous,
    )
    target_catalog = lookup_catalog_price(
        db,
        product_id=item.product_id,
        condition_code=target,
    )

    if target_catalog is not None and ref_catalog is not None and ref_catalog > 0:
        return (listed * target_catalog) // ref_catalog
    if target_catalog is not None:
        return target_catalog

    ref_rate = _rate_percent(previous)
    target_rate = _rate_percent(target)
    if ref_rate <= 0:
        return 0
    return (listed * target_rate) // ref_rate


def build_uniform_assessment_lines(
    *,
    quantity: int,
    unit_price: int,
) -> list[dict[str, int]]:
    qty = max(int(quantity or 0), 0)
    price = max(int(unit_price), 0)
    if qty <= 0:
        return []
    return [{"quantity": qty, "unit_price": price}]