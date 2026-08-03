"""Shared serializers for buyback API responses."""

from __future__ import annotations

import models_buyback
import schemas_buyback
from services.buyback_item_labels import (
    CUSTOMER_DECISION_LABELS,
    ITEM_RETURN_STATUS_LABELS,
    LINE_STATUS_LABELS,
    REJECTED_ITEM_HANDLING_LABELS,
    format_rejection_reason,
    parse_assessment_lines,
)


def serialize_request_item(item: models_buyback.BuybackRequestItem) -> schemas_buyback.BuybackRequestItemOut:
    line_status = item.line_status
    return_status = item.return_status
    assessment_lines = [
        schemas_buyback.AssessmentLineOut(**row)
        for row in parse_assessment_lines(item)
    ]
    return schemas_buyback.BuybackRequestItemOut(
        id=item.id,
        product_id=item.product_id,
        product_name_snapshot=item.product_name_snapshot,
        condition_code=item.condition_code,
        quantity=item.quantity,
        listed_unit_price=item.listed_unit_price,
        assessed_unit_price=item.assessed_unit_price,
        accepted_unit_price=item.accepted_unit_price,
        assessment_lines=assessment_lines,
        line_status=line_status,
        line_status_label=LINE_STATUS_LABELS.get(line_status, line_status) if line_status else None,
        rejection_reason_code=item.rejection_reason_code,
        rejection_reason_text=item.rejection_reason_text,
        rejection_reason_label=format_rejection_reason(
            item.rejection_reason_code,
            item.rejection_reason_text,
        ),
        is_return_target=bool(item.is_return_target),
        is_disposal_target=bool(item.is_disposal_target),
        return_status=return_status,
        return_status_label=ITEM_RETURN_STATUS_LABELS.get(return_status, return_status)
        if return_status
        else None,
        return_tracking_number=item.return_tracking_number,
        return_shipping_cost=item.return_shipping_cost,
        customer_decision=item.customer_decision,
        customer_decision_label=CUSTOMER_DECISION_LABELS.get(
            item.customer_decision, item.customer_decision
        )
        if item.customer_decision
        else None,
    )


def rejection_reason_options() -> list[dict[str, str]]:
    return [
        {"code": code, "label": label}
        for code, label in models_buyback.REJECTION_REASON_CODES.items()
    ]


def rejected_item_handling_label(value: str | None) -> str | None:
    if not value:
        return None
    return REJECTED_ITEM_HANDLING_LABELS.get(value, value)
