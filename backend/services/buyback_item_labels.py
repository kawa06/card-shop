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


CUSTOMER_DECISION_LABELS: dict[str, str] = {
    "accepted": "買取する",
    "rejected": "買取をやめる",
    "partial": "一部買取",
}

CONDITION_CODE_LABELS: dict[str, str] = {
    "default": "標準",
    "A": "極美品",
    "B": "美品",
    "C": "軽い傷あり",
    "D": "傷あり",
    "E": "大きな傷あり",
    "ジャンク": "ジャンク",
}


CUSTOMER_LINE_STATUS_LABELS: dict[str, str] = {
    **LINE_STATUS_LABELS,
    "customer_review": "査定済み・選択してください",
}

CUSTOMER_REVIEW_REQUEST_STATUSES = frozenset(
    {
        "assessed",
        "awaiting_customer",
    }
)

CHOOSABLE_LINE_STATUSES = frozenset(
    {
        models_buyback.BuybackItemLineStatus.buyable.value,
        models_buyback.BuybackItemLineStatus.reduced.value,
    }
)


def item_has_assessment_data(item: models_buyback.BuybackRequestItem) -> bool:
    if parse_assessment_lines(item):
        return True
    if item.assessed_unit_price is not None:
        return True
    status = item.line_status or models_buyback.BuybackItemLineStatus.pending.value
    return status in CHOOSABLE_LINE_STATUSES


def infer_line_status_from_assessment(
    item: models_buyback.BuybackRequestItem,
) -> str | None:
    status = item.line_status or models_buyback.BuybackItemLineStatus.pending.value
    if status != models_buyback.BuybackItemLineStatus.pending.value:
        return None
    if item.rejection_reason_code or (item.rejection_reason_text or "").strip():
        return models_buyback.BuybackItemLineStatus.rejected.value
    lines = parse_assessment_lines(item)
    if lines:
        avg = sum(row["quantity"] * row["unit_price"] for row in lines) // max(item.quantity, 1)
        if avg <= 0:
            return models_buyback.BuybackItemLineStatus.rejected.value
        if avg < item.listed_unit_price:
            return models_buyback.BuybackItemLineStatus.reduced.value
        return models_buyback.BuybackItemLineStatus.buyable.value
    if item.assessed_unit_price is not None:
        price = int(item.assessed_unit_price)
        if price <= 0:
            return models_buyback.BuybackItemLineStatus.rejected.value
        if price < item.listed_unit_price:
            return models_buyback.BuybackItemLineStatus.reduced.value
        return models_buyback.BuybackItemLineStatus.buyable.value
    return None


def effective_line_status(
    item: models_buyback.BuybackRequestItem,
    request: models_buyback.BuybackRequest | None = None,
) -> str:
    status = item.line_status or models_buyback.BuybackItemLineStatus.pending.value
    if status != models_buyback.BuybackItemLineStatus.pending.value:
        return status
    inferred = infer_line_status_from_assessment(item)
    if inferred:
        return inferred
    req_status = request.status if request else None
    if req_status in CUSTOMER_REVIEW_REQUEST_STATUSES and item_has_assessment_data(item):
        return "customer_review"
    return status


def is_customer_choosable_item(
    item: models_buyback.BuybackRequestItem,
    request: models_buyback.BuybackRequest | None = None,
) -> bool:
    effective = effective_line_status(item, request)
    return effective in CHOOSABLE_LINE_STATUSES


def customer_line_status_label(
    item: models_buyback.BuybackRequestItem,
    request: models_buyback.BuybackRequest | None = None,
) -> str | None:
    effective = effective_line_status(item, request)
    return CUSTOMER_LINE_STATUS_LABELS.get(effective, LINE_STATUS_LABELS.get(effective, effective))


def condition_code_label(code: str | None) -> str | None:
    if not code:
        return None
    return CONDITION_CODE_LABELS.get(code, code)


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


def expand_assessment_units(item: models_buyback.BuybackRequestItem) -> list[dict[str, int]]:
    """Expand item assessment into per-unit rows for customer selection."""
    lines = parse_assessment_lines(item)
    units: list[dict[str, int]] = []
    if lines:
        for line_index, line in enumerate(lines):
            for unit_index in range(line["quantity"]):
                units.append(
                    {
                        "line_index": line_index,
                        "unit_index": unit_index,
                        "unit_price": line["unit_price"],
                    }
                )
        return units

    qty = max(int(item.quantity or 0), 0)
    if qty <= 0:
        return []
    unit_price = item.assessed_unit_price
    if unit_price is None:
        if item.line_status == models_buyback.BuybackItemLineStatus.buyable.value:
            unit_price = item.listed_unit_price
        else:
            unit_price = 0
    unit_price = max(int(unit_price), 0)
    for unit_index in range(qty):
        units.append(
            {
                "line_index": 0,
                "unit_index": unit_index,
                "unit_price": unit_price,
            }
        )
    return units


def parse_customer_decision_lines(item: models_buyback.BuybackRequestItem) -> list[dict[str, object]]:
    raw = getattr(item, "customer_decision_lines_json", None)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    rows: list[dict[str, object]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        try:
            rows.append(
                {
                    "line_index": int(row.get("line_index", 0)),
                    "unit_index": int(row.get("unit_index", 0)),
                    "unit_price": int(row.get("unit_price", 0)),
                    "accepted": bool(row.get("accepted")),
                }
            )
        except (TypeError, ValueError):
            continue
    return rows


def item_accepted_subtotal(item: models_buyback.BuybackRequestItem) -> int:
    decision_lines = parse_customer_decision_lines(item)
    if decision_lines:
        return sum(
            int(row["unit_price"])
            for row in decision_lines
            if row.get("accepted")
        )
    if item.customer_decision != "accepted":
        return 0
    unit = item.accepted_unit_price
    if unit is None:
        lines = parse_assessment_lines(item)
        if lines:
            return sum(row["quantity"] * row["unit_price"] for row in lines)
        if item.assessed_unit_price is not None:
            return max(int(item.assessed_unit_price), 0) * item.quantity
        return 0
    return max(int(unit), 0) * item.quantity


def item_assessed_subtotal(
    item: models_buyback.BuybackRequestItem,
    request: models_buyback.BuybackRequest | None = None,
) -> int:
    lines = parse_assessment_lines(item)
    if lines:
        return sum(row["quantity"] * row["unit_price"] for row in lines)

    status = effective_line_status(item, request)
    if status == models_buyback.BuybackItemLineStatus.rejected.value:
        return 0

    unit = item.assessed_unit_price
    if unit is None:
        if status in CHOOSABLE_LINE_STATUSES:
            unit = item.listed_unit_price
        else:
            unit = 0
    return max(int(unit), 0) * item.quantity


def compute_assessed_total(
    items: list[models_buyback.BuybackRequestItem],
    request: models_buyback.BuybackRequest | None = None,
) -> int:
    total = 0
    for item in items:
        total += item_assessed_subtotal(item, request)
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
