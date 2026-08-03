"""Store buyback workflow: check-in, assessment, estimates, payment, completion."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_logistics_logs import write_buyback_audit
from services.buyback_method import is_store_purchase, normalize_buyback_method
from services.buyback_request_status import validate_transition


def _require_store_request(request: models_buyback.BuybackRequest) -> None:
    if not is_store_purchase(request.buyback_method):
        raise HTTPException(status_code=400, detail="店舗買取の申込のみ操作できます")


def _transition(
    db: Session,
    *,
    request: models_buyback.BuybackRequest,
    admin_user: models.User,
    new_status: str,
    note: str,
    audit_action: str,
    extra_details: dict | None = None,
) -> None:
    current = request.status or ""
    if not validate_transition(current, new_status, request.buyback_method):
        raise HTTPException(status_code=400, detail=f"ステータスを「{new_status}」に変更できません")
    now = datetime.utcnow()
    request.status = new_status
    request.updated_at = now
    db.add(
        models_buyback.BuybackStatusHistory(
            request_id=request.id,
            from_status=current,
            to_status=new_status,
            changed_by_user_id=admin_user.id,
            note=note,
        )
    )
    details = {
        "from_status": current,
        "to_status": new_status,
        "request_number": request.request_number,
    }
    if extra_details:
        details.update(extra_details)
    write_buyback_audit(
        db,
        actor_user_id=admin_user.id,
        action=audit_action,
        entity_type="buyback_request",
        entity_id=str(request.id),
        details=details,
    )


def check_in_store_visit(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
) -> models_buyback.BuybackRequest:
    from services.buyback_admin import get_admin_request

    request = get_admin_request(db, request_id)
    _require_store_request(request)
    current = request.status or ""
    if current not in {
        models_buyback.BuybackRequestStatus.awaiting_visit.value,
        models_buyback.BuybackRequestStatus.submitted.value,
    }:
        raise HTTPException(status_code=400, detail="来店受付は来店待ちの申込のみ可能です")

    new_status = models_buyback.BuybackRequestStatus.store_visited.value
    now = datetime.utcnow()
    request.store_checked_in_at = now
    request.store_checked_in_by_user_id = admin_user.id
    _transition(
        db,
        request=request,
        admin_user=admin_user,
        new_status=new_status,
        note="来店受付",
        audit_action="store_check_in",
    )
    db.commit()
    db.refresh(request)
    return get_admin_request(db, request_id)


def start_store_assessment(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
) -> models_buyback.BuybackRequest:
    from services.buyback_admin import get_admin_request

    request = get_admin_request(db, request_id)
    _require_store_request(request)
    current = request.status or ""
    if current != models_buyback.BuybackRequestStatus.store_visited.value:
        raise HTTPException(status_code=400, detail="査定開始は来店済みの申込のみ可能です")

    new_status = models_buyback.BuybackRequestStatus.assessing.value
    now = datetime.utcnow()
    request.assessment_started_at = now
    request.assessment_started_by_user_id = admin_user.id
    _transition(
        db,
        request=request,
        admin_user=admin_user,
        new_status=new_status,
        note="査定開始",
        audit_action="assessment_started",
    )
    db.commit()
    db.refresh(request)
    return get_admin_request(db, request_id)


def send_appraisal_estimate(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    estimated_minutes: int,
    message: str | None = None,
) -> models_buyback.BuybackAppraisalEstimate:
    from services.buyback_admin import get_admin_request

    if estimated_minutes < 1 or estimated_minutes > 999:
        raise HTTPException(status_code=400, detail="目安時間は1〜999分で指定してください")

    request = get_admin_request(db, request_id)
    _require_store_request(request)
    if request.status != models_buyback.BuybackRequestStatus.assessing.value:
        raise HTTPException(status_code=400, detail="査定中の申込のみ目安時間を送信できます")

    now = datetime.utcnow()
    row = (
        db.query(models_buyback.BuybackAppraisalEstimate)
        .filter(models_buyback.BuybackAppraisalEstimate.request_id == request_id)
        .first()
    )
    if row:
        row.estimated_minutes = estimated_minutes
        row.message = (message or "").strip() or None
        row.sent_at = now
        row.sent_by_user_id = admin_user.id
        row.revision_count = (row.revision_count or 0) + 1
        row.updated_at = now
    else:
        row = models_buyback.BuybackAppraisalEstimate(
            request_id=request_id,
            estimated_minutes=estimated_minutes,
            message=(message or "").strip() or None,
            sent_at=now,
            sent_by_user_id=admin_user.id,
            revision_count=1,
        )
        db.add(row)

    write_buyback_audit(
        db,
        actor_user_id=admin_user.id,
        action="appraisal_estimate_sent",
        entity_type="buyback_request",
        entity_id=str(request_id),
        details={
            "estimated_minutes": estimated_minutes,
            "revision_count": row.revision_count,
            "request_number": request.request_number,
        },
    )

    notification_warning: str | None = None
    try:
        from services.buyback_emails import notify_store_appraisal_estimate

        notify_store_appraisal_estimate(db, request, estimated_minutes, message)
    except Exception as exc:
        notification_warning = str(exc)[:200]

    db.commit()
    db.refresh(row)

    if notification_warning:
        row._notification_warning = notification_warning  # type: ignore[attr-defined]
    return row


def update_store_visit_at(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    store_visit_at: datetime,
    reason: str,
) -> models_buyback.BuybackRequest:
    from services.buyback_admin import get_admin_request

    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="変更理由を入力してください")

    request = get_admin_request(db, request_id)
    _require_store_request(request)
    previous = request.store_visit_at
    request.store_visit_at = store_visit_at
    request.updated_at = datetime.utcnow()
    write_buyback_audit(
        db,
        actor_user_id=admin_user.id,
        action="store_visit_rescheduled",
        entity_type="buyback_request",
        entity_id=str(request_id),
        details={
            "previous_store_visit_at": previous.isoformat() if previous else None,
            "new_store_visit_at": store_visit_at.isoformat(),
            "reason": reason,
            "request_number": request.request_number,
        },
    )
    db.commit()
    db.refresh(request)
    return get_admin_request(db, request_id)


def complete_store_payment(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    payment_method: str,
    payment_amount: int | None = None,
    payment_note: str | None = None,
) -> models_buyback.BuybackRequest:
    from services.buyback_admin import get_admin_request

    request = get_admin_request(db, request_id)
    _require_store_request(request)
    if request.status != models_buyback.BuybackRequestStatus.accepted.value:
        raise HTTPException(status_code=400, detail="承認済みの申込のみ支払い処理できます")

    method = (payment_method or "").strip().lower()
    allowed = {"cash", "bank_transfer", "other"}
    if method not in allowed:
        raise HTTPException(status_code=400, detail="支払方法が不正です")

    note = (payment_note or "").strip()
    if method == "other" and not note:
        raise HTTPException(status_code=400, detail="その他の支払方法では備考が必須です")

    amount = payment_amount if payment_amount is not None else (request.payout_total or 0)
    if amount < 0:
        raise HTTPException(status_code=400, detail="支払金額が不正です")

    now = datetime.utcnow()
    request.store_payment_method = method
    request.store_payment_amount = amount
    request.store_payment_note = note or None
    request.paid_at = now
    new_status = models_buyback.BuybackRequestStatus.paid.value
    _transition(
        db,
        request=request,
        admin_user=admin_user,
        new_status=new_status,
        note=f"店舗支払完了（{method}）",
        audit_action="store_payment_completed",
        extra_details={"payment_method": method, "payment_amount": amount},
    )
    db.commit()
    db.refresh(request)
    return get_admin_request(db, request_id)


def complete_store_transaction(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
) -> models_buyback.BuybackRequest:
    from services.buyback_admin import get_admin_request

    request = get_admin_request(db, request_id)
    _require_store_request(request)
    if request.status != models_buyback.BuybackRequestStatus.paid.value:
        raise HTTPException(status_code=400, detail="支払完了の申込のみ取引完了できます")

    now = datetime.utcnow()
    request.transaction_completed_at = now
    request.transaction_completed_by_user_id = admin_user.id
    new_status = models_buyback.BuybackRequestStatus.completed.value
    _transition(
        db,
        request=request,
        admin_user=admin_user,
        new_status=new_status,
        note="取引完了",
        audit_action="transaction_completed",
    )
    db.commit()
    db.refresh(request)
    return get_admin_request(db, request_id)


def normalize_request_buyback_method(db: Session, request: models_buyback.BuybackRequest) -> None:
    """Persist normalized buyback_method when legacy aliases are stored."""
    normalized = normalize_buyback_method(request.buyback_method)
    if request.buyback_method != normalized:
        request.buyback_method = normalized
