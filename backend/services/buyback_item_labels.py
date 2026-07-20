"""Labels and helpers for buyback item assessment."""

from __future__ import annotations

import models_buyback

LINE_STATUS_LABELS: dict[str, str] = {
    "pending": "査定待ち",
    "buyable": "買取可能",
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


def compute_assessed_total(items: list[models_buyback.BuybackRequestItem]) -> int:
    total = 0
    for item in items:
        status = item.line_status or models_buyback.BuybackItemLineStatus.pending.value
        if status == models_buyback.BuybackItemLineStatus.rejected.value:
            continue
        unit = item.assessed_unit_price
        if unit is None:
            if status == models_buyback.BuybackItemLineStatus.buyable.value:
                unit = item.listed_unit_price
            else:
                unit = 0
        total += max(int(unit), 0) * item.quantity
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
