"""Centralized point amount calculations (1 point = 1 yen by default)."""

from __future__ import annotations

from models_points import PointSettings

POINTS_PER_YEN = 1


def points_to_yen(points: int) -> int:
    return int(points) * POINTS_PER_YEN


def yen_to_points(yen: int) -> int:
    return int(yen) // POINTS_PER_YEN


def calculate_earn_points(base_amount_yen: int, rate_percent: int) -> int:
    """Earn base × rate%, floor fractional points."""
    if base_amount_yen <= 0 or rate_percent <= 0:
        return 0
    return (int(base_amount_yen) * int(rate_percent)) // 100


def calculate_earn_base_yen(
    *,
    items_subtotal: int,
    discount_amount: int = 0,
    points_used: int = 0,
) -> int:
    """Earn base = product subtotal − discounts − points used (no shipping/fees)."""
    base = int(items_subtotal) - int(discount_amount) - points_to_yen(int(points_used))
    return max(0, base)


def calculate_usable_base_yen(
    *,
    items_subtotal: int,
    shipping_fee: int = 0,
    packaging_fee: int = 0,
    discount_amount: int = 0,
    settings: PointSettings,
) -> int:
    """Maximum order amount that points may cover."""
    base = int(items_subtotal) - int(discount_amount)
    if settings.points_apply_to_shipping:
        base += int(shipping_fee) + int(packaging_fee)
    return max(0, base)


def calculate_max_usable_points(
    *,
    available_points: int,
    items_subtotal: int,
    shipping_fee: int = 0,
    packaging_fee: int = 0,
    discount_amount: int = 0,
    settings: PointSettings,
) -> int:
    usable_base_yen = calculate_usable_base_yen(
        items_subtotal=items_subtotal,
        shipping_fee=shipping_fee,
        packaging_fee=packaging_fee,
        discount_amount=discount_amount,
        settings=settings,
    )
    cap_by_percent = (usable_base_yen * int(settings.max_usage_percent)) // 100
    cap_by_amount = min(int(settings.max_points_per_order), cap_by_percent, usable_base_yen)
    cap_by_points = yen_to_points(cap_by_amount)
    return max(0, min(int(available_points), cap_by_points))


def calculate_order_total_yen(
    *,
    items_subtotal: int,
    shipping_fee: int = 0,
    packaging_fee: int = 0,
    payment_fee: int = 0,
    discount_amount: int = 0,
    points_used: int = 0,
) -> int:
    gross = (
        int(items_subtotal)
        + int(shipping_fee)
        + int(packaging_fee)
        + int(payment_fee)
        - int(discount_amount)
    )
    return max(0, gross - points_to_yen(int(points_used)))
