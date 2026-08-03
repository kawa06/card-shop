"""Labels and helpers for buyback item assessment."""

from __future__ import annotations

import json

import models_buyback

LINE_STATUS_LABELS: dict[str, str] = {
    "pending": "査定待ち",
    "buyable": "満額買取",
    "reduced": "減額買取",
    "rejected": "買取不可",
}

REJECTED_ITEM_HANDLING_LABELS: dict[str, str] = {
    "return_rejected_only": "買取可能な商品のみ買取し、買取不可の商品は返送する",
    "dispose_rejected": "買取不可の商品は返送せず、KRX TCG側で処分する",
    "return_all_if_any_rejected": "買取不可の商品が1点でもあれば、すべての商品を返送する",
}

ITEM_RETURN_STATUS_LABELS: dict[str, str] = {
    "none": "—",
    "pending": "返送準備中",
    "shipped": "返送済み",
    "completed": "返送完了",
}


def format_rejection_reason(
    code: str | None,
    text: str | None,
) -> str | None:
    custom = (text or "").strip()
    if custom:
        return custom
    if code:
        return models_buyback.REJECTION_REASON_CODES.get(code, code)
    return None


def parse_assessment_lines(item: models_buyback.BuybackRequestItem) -> list[dict[str, int]]:
    raw = getattr(item, "assessment_lines_json", None)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    lines: list[dict[str, int]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        qty = row.get("quantity")
        price = row.get("unit_price")
        if qty is None or price is None:
            continue
        try:
            qty_int = int(qty)
            price_int = int(price)
        except (TypeError, ValueError):
            continue
        if qty_int <= 0 or price_int < 0:
            continue
        lines.append({"quantity": qty_int, "unit_price": price_int})
    return lines


def item_assessed_subtotal(item: models_buyback.BuybackRequestItem) -> int:
    status = item.line_status or models_buyback.BuybackItemLineStatus.pending.value
    if status == models_buyback.BuybackItemLineStatus.rejected.value:
        return 0

    lines = parse_assessment_lines(item)
    if lines:
        return sum(row["quantity"] * row["unit_price"] for row in lines)

    unit = item.assessed_unit_price
    if unit is None:
        if status == models_buyback.BuybackItemLineStatus.buyable.value:
            unit = item.listed_unit_price
        else:
            unit = 0
    return max(int(unit), 0) * item.quantity


def compute_assessed_total(items: list[models_buyback.BuybackRequestItem]) -> int:
    total = 0
    for item in items:
        total += item_assessed_subtotal(item)
    return total


def apply_rejected_item_handling(request: models_buyback.BuybackRequest) -> None:
    """Set return/disposal flags from customer preference and line statuses."""
    handling = request.rejected_item_handling
    if not handling:
        return

    items = request.items or []
    rejected_items = [
        item
        for item in items
        if item.line_status == models_buyback.BuybackItemLineStatus.rejected.value
    ]
    has_rejected = bool(rejected_items)

    for item in items:
        is_rejected = item.line_status == models_buyback.BuybackItemLineStatus.rejected.value
        if handling == models_buyback.RejectedItemHandling.return_rejected_only.value:
            item.is_return_target = is_rejected
            item.is_disposal_target = False
        elif handling == models_buyback.RejectedItemHandling.dispose_rejected.value:
            item.is_return_target = False
            item.is_disposal_target = is_rejected
        elif handling == models_buyback.RejectedItemHandling.return_all_if_any_rejected.value:
            if has_rejected:
                item.is_return_target = True
                item.is_disposal_target = False
            else:
                item.is_return_target = False
                item.is_disposal_target = False

        if item.is_return_target and not item.return_status:
            item.return_status = models_buyback.BuybackItemReturnStatus.pending.value
        if not item.is_return_target and not item.is_disposal_target:
            item.return_status = models_buyback.BuybackItemReturnStatus.none.value
