"""Tax breakdown from tax-included (税込) amounts."""

from __future__ import annotations

from dataclasses import dataclass

import schemas


@dataclass
class TaxSlice:
    rate_percent: int
    amount_inclusive: int


def tax_from_inclusive(amount_inclusive: int, rate_percent: int) -> tuple[int, int]:
    """Return (consumption_tax, amount_excluding_tax) from tax-included amount."""
    amount = max(0, int(round(amount_inclusive)))
    tax = int(round(amount * rate_percent / (100 + rate_percent)))
    return tax, amount - tax


def build_tax_breakdown_rows(slices: list[TaxSlice]) -> list[schemas.TaxBreakdownRowOut]:
    grouped: dict[int, int] = {}
    for s in slices:
        if s.amount_inclusive <= 0:
            continue
        grouped[s.rate_percent] = grouped.get(s.rate_percent, 0) + s.amount_inclusive

    rows: list[schemas.TaxBreakdownRowOut] = []
    for rate in sorted(grouped.keys(), reverse=True):
        inclusive = grouped[rate]
        tax, _ex = tax_from_inclusive(inclusive, rate)
        rows.append(
            schemas.TaxBreakdownRowOut(
                rate_percent=rate,
                amount_inclusive=inclusive,
                consumption_tax=tax,
            )
        )
    return rows


def order_tax_slices(
    *,
    items_subtotal: int,
    shipping_fee: int,
    packaging_fee: int,
    payment_fee: int,
    discount_amount: int,
    default_tax_rate: int,
) -> list[TaxSlice]:
    """Build tax slices for an order (all at default rate for now)."""
    rate = default_tax_rate
    slices: list[TaxSlice] = []
    for amount in (items_subtotal, shipping_fee, packaging_fee, payment_fee):
        if amount > 0:
            slices.append(TaxSlice(rate_percent=rate, amount_inclusive=amount))
    if discount_amount > 0:
        slices.append(TaxSlice(rate_percent=rate, amount_inclusive=-discount_amount))
    return slices
