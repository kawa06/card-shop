"""Customer per-item acceptance of buyback assessment results."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_emails import notify_buyback_status_changed
from services.buyback_item_labels import (
    apply_rejected_item_handling,
    parse_assessment_lines,
)
from services.buyback_request_status import validate_transition
from services.buyback_requests import get_user_request

CUSTOMER_DECISION_ACCEPTED = "accepted"
CUSTOMER_DECISION_REJECTED = "rejected"

CHOOSABLE_LINE_STATUSES = frozenset(
    {
        models_buyback.BuybackItemLineStatus.buyable.value,
        models_buyback.BuybackItemLineStatus.reduced.value,
    }
)


def _accepted_unit_price_for_item(item: models_buyback.BuybackRequestItem) -> int:
    lines = parse_assessment_lines(item)
    if lines:
        subtotal = sum(row["quantity"] * row["unit_price"] for row in lines)
        return subtotal // item.quantity if item.quantity else 0
    if item.assessed_unit_price is not None:
        return max(int(item.assessed_unit_price), 0)
    if item.line_status == models_buyback.BuybackItemLineStatus.buyable.value:
        return item.listed_unit_price
    return 0


def _accepted_subtotal(item: models_buyback.BuybackRequestItem) -> int:
    if item.customer_decision != CUSTOMER_DECISION_ACCEPTED:
        return 0
    unit = item.accepted_unit_price
    if unit is None:
        unit = _accepted_unit_price_for_item(item)
    return max(int(unit), 0) * item.quantity


def _apply_customer_rejection_flags(request: models_buyback.BuybackRequest) -> None:
    for item in request.items or []:
        if item.customer_decision != CUSTOMER_DECISION_REJECTED:
            continue
        if item.line_status == models_buyback.BuybackItemLineStatus.rejected.value:
            continue
        item.is_return_target = True
        item.is_disposal_target = False
        if not item.return_status:
            item.return_status = models_buyback.BuybackItemReturnStatus.pending.value
    apply_rejected_item_handling(request)


def submit_assessment_response(
    db: Session,
    *,
    user: models.User,
    request_id: int,
    decisions: list[dict[str, object]],
) -> models_buyback.BuybackRequest:
    request = get_user_request(db, user_id=user.id, request_id=request_id)
    if request.status != models_buyback.BuybackRequestStatus.awaiting_customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="査定結果の承認は承認待ちの申込のみ可能です",
        )

    items_by_id = {item.id: item for item in (request.items or [])}
    if not items_by_id:
        raise HTTPException(status_code=400, detail="申込商品がありません")

    seen: set[int] = set()
    for row in decisions:
        item_id = row.get("item_id")
        accepted = row.get("accepted")
        if item_id is None or accepted is None:
            raise HTTPException(status_code=400, detail="item_id と accepted が必要です")
        try:
            item_id_int = int(item_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="item_id が不正です") from exc
        if item_id_int in seen:
            raise HTTPException(status_code=400, detail="同じ商品が重複しています")
        seen.add(item_id_int)

        item = items_by_id.get(item_id_int)
        if not item:
            raise HTTPException(status_code=404, detail=f"商品 ID {item_id_int} が見つかりません")
        if item.line_status not in CHOOSABLE_LINE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"「{item.product_name_snapshot}」は選択できない査定区分です",
            )

        if bool(accepted):
            item.customer_decision = CUSTOMER_DECISION_ACCEPTED
            item.accepted_unit_price = _accepted_unit_price_for_item(item)
            item.is_return_target = False
            item.is_disposal_target = False
            item.return_status = models_buyback.BuybackItemReturnStatus.none.value
        else:
            item.customer_decision = CUSTOMER_DECISION_REJECTED
            item.accepted_unit_price = 0
            item.is_return_target = True
            item.is_disposal_target = False
            item.return_status = models_buyback.BuybackItemReturnStatus.pending.value

    for item in request.items or []:
        if item.line_status == models_buyback.BuybackItemLineStatus.rejected.value:
            if not item.customer_decision:
                item.customer_decision = CUSTOMER_DECISION_REJECTED
                item.accepted_unit_price = 0
            continue
        if item.line_status in CHOOSABLE_LINE_STATUSES and not item.customer_decision:
            raise HTTPException(
                status_code=400,
                detail=f"「{item.product_name_snapshot}」の買取可否を選択してください",
            )

    _apply_customer_rejection_flags(request)

    payout_total = sum(_accepted_subtotal(item) for item in (request.items or []))
    request.payout_total = payout_total

    accepted_any = payout_total > 0
    new_status = (
        models_buyback.BuybackRequestStatus.accepted.value
        if accepted_any
        else models_buyback.BuybackRequestStatus.rejected.value
    )
    current = request.status
    if not validate_transition(current, new_status, request.buyback_method):
        raise HTTPException(status_code=400, detail="査定結果の確定に失敗しました")

    now = datetime.utcnow()
    request.status = new_status
    request.updated_at = now
    db.add(
        models_buyback.BuybackStatusHistory(
            request_id=request.id,
            from_status=current,
            to_status=new_status,
            changed_by_user_id=user.id,
            note="顧客が査定結果を確定",
        )
    )
    db.commit()
    db.refresh(request)
    notify_buyback_status_changed(db, request, user, previous_status=current)
    db.commit()
    db.refresh(request)
    return request
