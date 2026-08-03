"""Customer appraisal review eligibility and admin presentation."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_item_labels import (
    CUSTOMER_REVIEW_REQUEST_STATUSES,
    infer_line_status_from_assessment,
    is_customer_choosable_item,
    item_has_assessment_data,
    parse_assessment_lines,
)
from services.buyback_logistics_logs import write_buyback_audit
from services.buyback_request_status import validate_transition


def can_review_appraisal(
    request: models_buyback.BuybackRequest,
    *,
    user_id: int | None = None,
) -> bool:
    if user_id is not None and request.user_id != user_id:
        return False
    status = request.status or ""
    if status not in CUSTOMER_REVIEW_REQUEST_STATUSES:
        return False
    if status in {
        models_buyback.BuybackRequestStatus.paid.value,
        models_buyback.BuybackRequestStatus.completed.value,
        models_buyback.BuybackRequestStatus.cancelled.value,
    }:
        return False
    if request.customer_confirmed_at is not None:
        return False
    choosable = [
        item
        for item in (request.items or [])
        if is_customer_choosable_item(item, request)
    ]
    return bool(choosable)


def sync_item_line_statuses_from_assessment(
    request: models_buyback.BuybackRequest,
) -> None:
    """Infer buyable/reduced/rejected from assessment data when line_status is still pending."""
    for item in request.items or []:
        inferred = infer_line_status_from_assessment(item)
        if inferred and (item.line_status or "pending") == models_buyback.BuybackItemLineStatus.pending.value:
            item.line_status = inferred


def present_assessment_to_customer(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    customer_status_note: str | None = None,
) -> models_buyback.BuybackRequest:
    from services.buyback_admin import get_admin_request

    request = get_admin_request(db, request_id)
    current = request.status or ""
    allowed_from = {
        models_buyback.BuybackRequestStatus.assessing.value,
        models_buyback.BuybackRequestStatus.assessed.value,
    }
    if current not in allowed_from:
        raise HTTPException(
            status_code=400,
            detail="査定結果の提示は「査定中」または「査定完了」の申込のみ可能です",
        )

    sync_item_line_statuses_from_assessment(request)
    choosable = [
        item for item in (request.items or []) if is_customer_choosable_item(item, request)
    ]
    if not choosable:
        raise HTTPException(
            status_code=400,
            detail="選択可能な査定商品がありません。商品ごとの査定区分と単価を保存してください",
        )

    new_status = models_buyback.BuybackRequestStatus.awaiting_customer.value
    if not validate_transition(current, new_status, request.buyback_method):
        raise HTTPException(status_code=400, detail="査定結果の提示に失敗しました")

    now = datetime.utcnow()
    from services.buyback_item_labels import compute_assessed_total

    request.assessed_total = compute_assessed_total(request.items or [], request)
    request.assessed_at = request.assessed_at or now
    request.assessment_presented_at = now
    request.assessment_presented_by_user_id = admin_user.id
    request.assessment_result_version = (request.assessment_result_version or 0) + 1
    request.status = new_status
    if customer_status_note:
        request.customer_status_note = customer_status_note.strip()
    request.updated_at = now

    db.add(
        models_buyback.BuybackStatusHistory(
            request_id=request.id,
            from_status=current,
            to_status=new_status,
            changed_by_user_id=admin_user.id,
            note="査定結果をお客様へ提示",
        )
    )
    write_buyback_audit(
        db,
        actor_user_id=admin_user.id,
        action="assessment_presented",
        entity_type="buyback_request",
        entity_id=str(request.id),
        details={
            "from_status": current,
            "to_status": new_status,
            "assessment_result_version": request.assessment_result_version,
            "request_number": request.request_number,
        },
    )
    db.commit()
    db.refresh(request)

    try:
        from services.buyback_emails import notify_buyback_assessment_ready

        user = db.query(models.User).filter(models.User.id == request.user_id).first()
        if user:
            notify_buyback_assessment_ready(db, request, user)
            db.commit()
    except Exception:
        pass

    return get_admin_request(db, request_id)
