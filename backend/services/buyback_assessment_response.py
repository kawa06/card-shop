"""Customer per-item acceptance of buyback assessment results."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_emails import notify_buyback_status_changed
from services.buyback_customer_review import sync_item_line_statuses_from_assessment
from services.buyback_item_labels import (
    apply_rejected_item_handling,
    expand_assessment_units,
    is_customer_choosable_item,
    item_accepted_subtotal,
)
from services.buyback_request_status import validate_transition
from services.buyback_requests import get_user_request

logger = logging.getLogger(__name__)

CUSTOMER_DECISION_ACCEPTED = "accepted"
CUSTOMER_DECISION_REJECTED = "rejected"
CUSTOMER_DECISION_PARTIAL = "partial"

CHOOSABLE_LINE_STATUSES = frozenset(
    {
        models_buyback.BuybackItemLineStatus.buyable.value,
        models_buyback.BuybackItemLineStatus.reduced.value,
    }
)

REVIEWABLE_REQUEST_STATUSES = frozenset(
    {
        models_buyback.BuybackRequestStatus.awaiting_customer.value,
        models_buyback.BuybackRequestStatus.assessed.value,
    }
)


def _unit_key(line_index: int, unit_index: int) -> tuple[int, int]:
    return (line_index, unit_index)


def _apply_unit_decisions(
    item: models_buyback.BuybackRequestItem,
    unit_decisions: list[dict[str, object]],
) -> None:
    expected = expand_assessment_units(item)
    if not expected:
        raise HTTPException(
            status_code=400,
            detail=f"「{item.product_name_snapshot}」の査定単価が設定されていません",
        )

    expected_keys = {
        _unit_key(row["line_index"], row["unit_index"]): row["unit_price"]
        for row in expected
    }
    seen: set[tuple[int, int]] = set()
    stored: list[dict[str, object]] = []
    accepted_count = 0
    accepted_subtotal = 0

    for row in unit_decisions:
        try:
            line_index = int(row.get("line_index", 0))
            unit_index = int(row.get("unit_index", 0))
            accepted = bool(row.get("accepted"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="単位ごとの選択形式が不正です") from exc

        key = _unit_key(line_index, unit_index)
        if key in seen:
            raise HTTPException(
                status_code=400,
                detail=f"「{item.product_name_snapshot}」の選択が重複しています",
            )
        if key not in expected_keys:
            raise HTTPException(
                status_code=400,
                detail=f"「{item.product_name_snapshot}」に存在しない単位が指定されています",
            )
        seen.add(key)
        unit_price = expected_keys[key]
        stored.append(
            {
                "line_index": line_index,
                "unit_index": unit_index,
                "unit_price": unit_price,
                "accepted": accepted,
            }
        )
        if accepted:
            accepted_count += 1
            accepted_subtotal += unit_price

    if len(seen) != len(expected_keys):
        raise HTTPException(
            status_code=400,
            detail=f"「{item.product_name_snapshot}」のすべての枚数について選択してください",
        )

    item.customer_decision_lines_json = json.dumps(stored, ensure_ascii=False)
    if accepted_count == len(expected):
        item.customer_decision = CUSTOMER_DECISION_ACCEPTED
    elif accepted_count == 0:
        item.customer_decision = CUSTOMER_DECISION_REJECTED
    else:
        item.customer_decision = CUSTOMER_DECISION_PARTIAL

    if accepted_count > 0:
        item.accepted_unit_price = accepted_subtotal // accepted_count
    else:
        item.accepted_unit_price = 0

    if accepted_count < len(expected):
        item.is_return_target = True
        item.is_disposal_target = False
        if not item.return_status:
            item.return_status = models_buyback.BuybackItemReturnStatus.pending.value
    else:
        item.is_return_target = False
        item.is_disposal_target = False
        item.return_status = models_buyback.BuybackItemReturnStatus.none.value


def _apply_customer_return_flags(request: models_buyback.BuybackRequest) -> None:
    """Ensure customer-declined units keep return flags after handling policy runs."""
    for item in request.items or []:
        if item.customer_decision not in (
            CUSTOMER_DECISION_REJECTED,
            CUSTOMER_DECISION_PARTIAL,
        ):
            continue
        if item.line_status not in CHOOSABLE_LINE_STATUSES:
            continue
        item.is_return_target = True
        item.is_disposal_target = False
        if not item.return_status or item.return_status == models_buyback.BuybackItemReturnStatus.none.value:
            item.return_status = models_buyback.BuybackItemReturnStatus.pending.value


def submit_assessment_response(
    db: Session,
    *,
    user: models.User,
    request_id: int,
    decisions: list[dict[str, object]],
) -> models_buyback.BuybackRequest:
    request = get_user_request(db, user_id=user.id, request_id=request_id)
    if request.customer_confirmed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="すでに査定結果を確定済みです",
        )
    if request.status not in REVIEWABLE_REQUEST_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="査定結果の確定はお客様確認待ちの申込のみ可能です",
        )

    sync_item_line_statuses_from_assessment(request)

    items_by_id = {item.id: item for item in (request.items or [])}
    if not items_by_id:
        raise HTTPException(status_code=400, detail="申込商品がありません")

    choosable_items = [
        item
        for item in (request.items or [])
        if is_customer_choosable_item(item, request)
    ]
    if not choosable_items:
        raise HTTPException(status_code=400, detail="選択可能な商品がありません")

    expected_version = request.assessment_result_version or 0
    seen_items: set[int] = set()
    for row in decisions:
        item_id = row.get("item_id")
        unit_decisions = row.get("unit_decisions")
        if item_id is None or unit_decisions is None:
            raise HTTPException(status_code=400, detail="item_id と unit_decisions が必要です")
        try:
            item_id_int = int(item_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="item_id が不正です") from exc
        if item_id_int in seen_items:
            raise HTTPException(status_code=400, detail="同じ商品が重複しています")
        seen_items.add(item_id_int)

        item = items_by_id.get(item_id_int)
        if not item:
            raise HTTPException(status_code=404, detail=f"商品 ID {item_id_int} が見つかりません")
        if not is_customer_choosable_item(item, request):
            raise HTTPException(
                status_code=400,
                detail=f"「{item.product_name_snapshot}」は選択できない査定区分です",
            )
        if not isinstance(unit_decisions, list):
            raise HTTPException(status_code=400, detail="unit_decisions は配列で指定してください")
        _apply_unit_decisions(item, unit_decisions)

    for item in choosable_items:
        if item.id not in seen_items:
            raise HTTPException(
                status_code=400,
                detail=f"「{item.product_name_snapshot}」の買取可否を選択してください",
            )

    for item in request.items or []:
        if item.line_status == models_buyback.BuybackItemLineStatus.rejected.value:
            if not item.customer_decision:
                item.customer_decision = CUSTOMER_DECISION_REJECTED
                item.accepted_unit_price = 0

    apply_rejected_item_handling(request)
    _apply_customer_return_flags(request)

    payout_total = sum(item_accepted_subtotal(item) for item in (request.items or []))
    request.payout_total = payout_total

    accepted_any = payout_total > 0
    new_status = (
        models_buyback.BuybackRequestStatus.accepted.value
        if accepted_any
        else models_buyback.BuybackRequestStatus.rejected.value
    )
    current = request.status
    if current == models_buyback.BuybackRequestStatus.assessed.value:
        current = models_buyback.BuybackRequestStatus.awaiting_customer.value
        request.status = models_buyback.BuybackRequestStatus.awaiting_customer.value
    if not validate_transition(current, new_status, request.buyback_method):
        raise HTTPException(status_code=400, detail="査定結果の確定に失敗しました")

    now = datetime.utcnow()
    request.status = new_status
    request.customer_confirmed_at = now
    request.customer_confirmed_by_user_id = user.id
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
    try:
        notify_buyback_status_changed(db, request, user, previous_status=current)
        db.commit()
    except Exception:
        logger.warning(
            "Assessment confirmation notification failed",
            extra={"request_id": request.id},
            exc_info=True,
        )
    db.refresh(request)
    return request
