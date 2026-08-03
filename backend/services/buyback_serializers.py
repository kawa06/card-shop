"""Shared serializers for buyback API responses."""

from __future__ import annotations

from datetime import timedelta

import models_buyback
import schemas_buyback
from services.buyback_customer_review import can_review_appraisal
from services.buyback_item_labels import (
    CUSTOMER_DECISION_LABELS,
    ITEM_RETURN_STATUS_LABELS,
    LINE_STATUS_LABELS,
    REJECTED_ITEM_HANDLING_LABELS,
    condition_code_label,
    customer_line_status_label,
    effective_line_status,
    format_rejection_reason,
    is_customer_choosable_item,
    item_accepted_subtotal,
    item_assessed_subtotal,
    parse_assessment_lines,
    parse_customer_decision_lines,
)
from services.buyback_method import buyback_method_label, is_store_purchase, normalize_buyback_method

STORE_PAYMENT_LABELS = {
    "cash": "現金",
    "bank_transfer": "銀行振込",
    "other": "その他",
}


def serialize_request_item(
    item: models_buyback.BuybackRequestItem,
    request: models_buyback.BuybackRequest | None = None,
) -> schemas_buyback.BuybackRequestItemOut:
    line_status = item.line_status
    effective = effective_line_status(item, request)
    return_status = item.return_status
    assessment_lines = [
        schemas_buyback.AssessmentLineOut(**row)
        for row in parse_assessment_lines(item)
    ]
    decision_lines = [
        schemas_buyback.CustomerUnitDecisionOut(
            line_index=int(row["line_index"]),
            unit_index=int(row["unit_index"]),
            unit_price=int(row["unit_price"]),
            accepted=bool(row["accepted"]),
        )
        for row in parse_customer_decision_lines(item)
    ]
    return schemas_buyback.BuybackRequestItemOut(
        id=item.id,
        product_id=item.product_id,
        product_name_snapshot=item.product_name_snapshot,
        condition_code=item.condition_code,
        condition_code_label=condition_code_label(item.condition_code),
        quantity=item.quantity,
        listed_unit_price=item.listed_unit_price,
        assessed_unit_price=item.assessed_unit_price,
        accepted_unit_price=item.accepted_unit_price,
        assessment_lines=assessment_lines,
        line_status=line_status,
        line_status_label=customer_line_status_label(item, request),
        effective_line_status=effective,
        is_choosable=is_customer_choosable_item(item, request),
        rejection_reason_code=item.rejection_reason_code,
        rejection_reason_text=item.rejection_reason_text,
        rejection_reason_label=format_rejection_reason(
            item.rejection_reason_code,
            item.rejection_reason_text,
        ),
        assessment_comment=item.assessment_comment,
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
        customer_decision_lines=decision_lines,
        assessed_subtotal=item_assessed_subtotal(item, request),
        accepted_subtotal=item_accepted_subtotal(item) if item.customer_decision else None,
    )


def serialize_appraisal_estimate(
    row: models_buyback.BuybackAppraisalEstimate | None,
) -> schemas_buyback.BuybackAppraisalEstimateOut | None:
    if not row:
        return None
    expected = row.sent_at + timedelta(minutes=int(row.estimated_minutes))
    from datetime import datetime

    now = datetime.utcnow()
    return schemas_buyback.BuybackAppraisalEstimateOut(
        estimated_minutes=row.estimated_minutes,
        message=row.message,
        sent_at=row.sent_at,
        revision_count=row.revision_count or 1,
        expected_completion_at=expected,
        is_overdue=now > expected,
    )


def rejection_reason_options() -> list[dict[str, str]]:
    return [
        {"code": code, "label": label}
        for code, label in models_buyback.REJECTION_REASON_CODES.items()
    ]


def condition_code_options() -> list[dict[str, str]]:
    from services.buyback_item_labels import CONDITION_CODE_LABELS

    return [{"code": code, "label": label} for code, label in CONDITION_CODE_LABELS.items()]


def rejected_item_handling_label(value: str | None) -> str | None:
    if not value:
        return None
    return REJECTED_ITEM_HANDLING_LABELS.get(value, value)


def normalized_buyback_method(value: str | None) -> str:
    return normalize_buyback_method(value)


def store_payment_method_label(value: str | None) -> str | None:
    if not value:
        return None
    return STORE_PAYMENT_LABELS.get(value, value)
