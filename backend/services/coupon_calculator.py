"""Coupon discount calculations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Sequence

import models_coupons


@dataclass
class CartLine:
    card_id: int
    quantity: int
    unit_price: int
    category_id: Optional[int] = None


def _parse_id_list(raw: Optional[str]) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[int] = []
    for item in data:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def coupon_card_ids(coupon: models_coupons.Coupon) -> list[int]:
    return _parse_id_list(coupon.card_ids_json)


def coupon_category_ids(coupon: models_coupons.Coupon) -> list[int]:
    return _parse_id_list(coupon.category_ids_json)


def eligible_subtotal_yen(coupon: models_coupons.Coupon, lines: Sequence[CartLine]) -> int:
    card_ids = set(coupon_card_ids(coupon))
    category_ids = set(coupon_category_ids(coupon))
    total = 0
    for line in lines:
        qty = max(0, int(line.quantity))
        price = max(0, int(line.unit_price))
        line_total = qty * price
        if not card_ids and not category_ids:
            total += line_total
            continue
        match = False
        if card_ids and int(line.card_id) in card_ids:
            match = True
        if category_ids and line.category_id is not None and int(line.category_id) in category_ids:
            match = True
        if match:
            total += line_total
    return total


def is_within_validity(coupon: models_coupons.Coupon, *, now: Optional[datetime] = None) -> bool:
    now = now or datetime.utcnow()
    if coupon.starts_at and now < coupon.starts_at:
        return False
    if coupon.ends_at and now > coupon.ends_at:
        return False
    return True


@dataclass
class CouponQuote:
    discount_amount: int
    shipping_discount: int
    shipping_fee_after: int
    eligible_subtotal: int


def quote_coupon(
    coupon: models_coupons.Coupon,
    *,
    lines: Sequence[CartLine],
    items_subtotal: int,
    shipping_fee: int,
) -> CouponQuote:
    """Compute discount without validating usage limits / audience."""
    eligible = eligible_subtotal_yen(coupon, lines)
    if not lines:
        eligible = max(0, int(items_subtotal))

    shipping = max(0, int(shipping_fee))
    discount = 0
    shipping_discount = 0

    ctype = (coupon.coupon_type or "").strip()
    if ctype == "fixed_amount":
        discount = min(int(coupon.amount_yen or 0), eligible)
    elif ctype == "percent":
        rate = max(0, min(100, int(coupon.percent_off or 0)))
        discount = (eligible * rate) // 100
        if coupon.max_discount_yen is not None:
            discount = min(discount, int(coupon.max_discount_yen))
        discount = min(discount, eligible)
    elif ctype == "free_shipping":
        shipping_discount = shipping
        shipping = 0
    else:
        discount = 0

    return CouponQuote(
        discount_amount=max(0, int(discount)),
        shipping_discount=max(0, int(shipping_discount)),
        shipping_fee_after=max(0, int(shipping)),
        eligible_subtotal=eligible,
    )


def lines_from_payload(cart_items: Sequence[dict[str, Any]] | None) -> list[CartLine]:
    lines: list[CartLine] = []
    for raw in cart_items or []:
        try:
            card_id = int(raw.get("card_id"))
            quantity = int(raw.get("quantity") or 0)
            unit_price = int(round(float(raw.get("unit_price") or 0)))
        except (TypeError, ValueError, AttributeError):
            continue
        category_id = raw.get("category_id")
        try:
            category_id_int = int(category_id) if category_id is not None else None
        except (TypeError, ValueError):
            category_id_int = None
        if quantity <= 0:
            continue
        lines.append(
            CartLine(
                card_id=card_id,
                quantity=quantity,
                unit_price=unit_price,
                category_id=category_id_int,
            )
        )
    return lines
