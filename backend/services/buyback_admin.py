"""Admin operations for buyback KYC and requests (Phase 7)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

import models
import models_buyback
from services.buyback_compliance import get_compliance_status
from services.buyback_emails import (
    STATUS_LABELS,
    notify_buyback_assessment_ready,
    notify_buyback_decision,
    notify_buyback_payout_completed,
    payout_email_already_sent,
)
from services.buyback_item_labels import (
    apply_rejected_item_handling,
    compute_assessed_total,
    format_rejection_reason,
)
from services.buyback_payout_accounts import get_default_payout_account, serialize_payout_account_for_admin

logger = logging.getLogger(__name__)

DOCUMENT_TYPE_LABELS = {
    "drivers_license": "運転免許証",
    "my_number_card": "マイナンバーカード",
    "passport": "パスポート",
    "residence_card": "在留カード",
}

REQUEST_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"received", "cancelled"},
    "received": {"assessing", "cancelled"},
    "assessing": {"assessed", "cancelled"},
    "assessed": {"awaiting_customer", "accepted", "rejected", "cancelled"},
    "awaiting_customer": {"accepted", "rejected", "returned", "cancelled"},
    "accepted": {"payout_pending", "cancelled"},
    "payout_pending": {"paid"},
    "rejected": {"returned"},
}

VALID_LINE_STATUSES = {
    models_buyback.BuybackItemLineStatus.pending.value,
    models_buyback.BuybackItemLineStatus.buyable.value,
    models_buyback.BuybackItemLineStatus.reduced.value,
    models_buyback.BuybackItemLineStatus.rejected.value,
}

VALID_RETURN_STATUSES = {
    models_buyback.BuybackItemReturnStatus.none.value,
    models_buyback.BuybackItemReturnStatus.pending.value,
    models_buyback.BuybackItemReturnStatus.shipped.value,
    models_buyback.BuybackItemReturnStatus.completed.value,
}


def _audit(
    db: Session,
    *,
    actor_user_id: int,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict,
) -> None:
    try:
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=json.dumps(details, ensure_ascii=False),
            )
        )
    except Exception as exc:
        logger.warning("Failed to write buyback admin audit log: %s", exc)


def list_identity_verifications(
    db: Session,
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
) -> list[models_buyback.IdentityVerification]:
    query = db.query(models_buyback.IdentityVerification).join(
        models.User, models_buyback.IdentityVerification.user_id == models.User.id
    )
    if status:
        query = query.filter(models_buyback.IdentityVerification.status == status)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.User.email.ilike(term),
                models.User.name.ilike(term),
            )
        )
    return (
        query.order_by(
            models_buyback.IdentityVerification.submitted_at.desc(),
            models_buyback.IdentityVerification.updated_at.desc(),
        )
        .limit(limit)
        .all()
    )


def get_identity_verification(
    db: Session, verification_id: int
) -> models_buyback.IdentityVerification:
    row = (
        db.query(models_buyback.IdentityVerification)
        .filter(models_buyback.IdentityVerification.id == verification_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="本人確認が見つかりません")
    return row


def approve_identity(
    db: Session,
    *,
    verification_id: int,
    admin_user: models.User,
) -> models_buyback.IdentityVerification:
    row = get_identity_verification(db, verification_id)
    if row.status != models_buyback.IdentityVerificationStatus.pending.value:
        raise HTTPException(status_code=400, detail="審査中の本人確認のみ承認できます")

    now = datetime.utcnow()
    row.status = models_buyback.IdentityVerificationStatus.approved.value
    row.reviewed_by_user_id = admin_user.id
    row.reviewed_at = now
    row.rejection_reason = None
    row.updated_at = now
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="identity_approved",
        entity_type="identity_verification",
        entity_id=str(row.id),
        details={"user_id": row.user_id},
    )
    db.commit()
    db.refresh(row)
    return row


def reject_identity(
    db: Session,
    *,
    verification_id: int,
    admin_user: models.User,
    rejection_reason: str,
) -> models_buyback.IdentityVerification:
    reason = (rejection_reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="差戻し理由を入力してください")

    row = get_identity_verification(db, verification_id)
    if row.status != models_buyback.IdentityVerificationStatus.pending.value:
        raise HTTPException(status_code=400, detail="審査中の本人確認のみ差戻しできます")

    now = datetime.utcnow()
    row.status = models_buyback.IdentityVerificationStatus.rejected.value
    row.reviewed_by_user_id = admin_user.id
    row.reviewed_at = now
    row.rejection_reason = reason
    row.updated_at = now
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="identity_rejected",
        entity_type="identity_verification",
        entity_id=str(row.id),
        details={"user_id": row.user_id, "rejection_reason": reason},
    )
    db.commit()
    db.refresh(row)
    return row


def list_admin_requests(
    db: Session,
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
) -> list[models_buyback.BuybackRequest]:
    query = (
        db.query(models_buyback.BuybackRequest)
        .join(models.User, models_buyback.BuybackRequest.user_id == models.User.id)
        .options(joinedload(models_buyback.BuybackRequest.items))
    )
    if status:
        query = query.filter(models_buyback.BuybackRequest.status == status)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.User.email.ilike(term),
                models.User.name.ilike(term),
                models_buyback.BuybackRequest.request_number.ilike(term),
            )
        )
    return (
        query.order_by(
            models_buyback.BuybackRequest.submitted_at.desc(),
            models_buyback.BuybackRequest.created_at.desc(),
        )
        .limit(limit)
        .all()
    )


def get_admin_request(db: Session, request_id: int) -> models_buyback.BuybackRequest:
    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == request_id)
        .options(
            joinedload(models_buyback.BuybackRequest.items),
            joinedload(models_buyback.BuybackRequest.status_history),
        )
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申込が見つかりません")
    return request


def update_request_status(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    new_status: str,
    admin_note: Optional[str] = None,
    tracking_number: Optional[str] = None,
    assessed_total: Optional[int] = None,
    payout_total: Optional[int] = None,
) -> models_buyback.BuybackRequest:
    request = get_admin_request(db, request_id)
    current = request.status
    allowed = REQUEST_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"ステータスを {STATUS_LABELS.get(current, current)} から {STATUS_LABELS.get(new_status, new_status)} に変更できません",
        )

    now = datetime.utcnow()
    request.status = new_status
    if admin_note is not None:
        request.admin_note = admin_note.strip() or None
    if tracking_number is not None:
        request.tracking_number = tracking_number.strip() or None
    if assessed_total is not None:
        request.assessed_total = assessed_total
        request.assessed_at = now
    if payout_total is not None:
        request.payout_total = payout_total
    if new_status == models_buyback.BuybackRequestStatus.paid.value:
        request.paid_at = now
    request.updated_at = now

    db.add(
        models_buyback.BuybackStatusHistory(
            request_id=request.id,
            from_status=current,
            to_status=new_status,
            changed_by_user_id=admin_user.id,
            note=admin_note,
        )
    )
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="request_status_updated",
        entity_type="buyback_request",
        entity_id=str(request.id),
        details={
            "from_status": current,
            "to_status": new_status,
            "request_number": request.request_number,
        },
    )
    db.commit()
    db.refresh(request)

    try:
        user = db.query(models.User).filter(models.User.id == request.user_id).first()
        if user:
            if new_status in {
                models_buyback.BuybackRequestStatus.assessed.value,
                models_buyback.BuybackRequestStatus.awaiting_customer.value,
            }:
                notify_buyback_assessment_ready(db, request, user)
            elif new_status in {
                models_buyback.BuybackRequestStatus.accepted.value,
                models_buyback.BuybackRequestStatus.rejected.value,
            }:
                notify_buyback_decision(db, request, user)
    except Exception as exc:
        logger.warning("Failed status-change notification: %s", exc)

    return get_admin_request(db, request_id)


def update_request_items(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    item_updates: list[dict],
    recalculate_assessed_total: bool = True,
    apply_handling_policy: bool = True,
) -> models_buyback.BuybackRequest:
    request = get_admin_request(db, request_id)
    items_by_id = {item.id: item for item in (request.items or [])}

    for payload in item_updates:
        item_id = payload.get("id")
        item = items_by_id.get(item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"明細 ID {item_id} が見つかりません")

        if "line_status" in payload and payload["line_status"] is not None:
            line_status = payload["line_status"]
            if line_status not in VALID_LINE_STATUSES:
                raise HTTPException(status_code=400, detail=f"無効な査定区分: {line_status}")
            item.line_status = line_status

        if "assessed_unit_price" in payload:
            item.assessed_unit_price = payload["assessed_unit_price"]
        if "accepted_unit_price" in payload:
            item.accepted_unit_price = payload["accepted_unit_price"]
        if "rejection_reason_code" in payload:
            item.rejection_reason_code = payload["rejection_reason_code"] or None
        if "rejection_reason_text" in payload:
            item.rejection_reason_text = (payload["rejection_reason_text"] or "").strip() or None
        if "is_return_target" in payload and payload["is_return_target"] is not None:
            item.is_return_target = bool(payload["is_return_target"])
        if "is_disposal_target" in payload and payload["is_disposal_target"] is not None:
            item.is_disposal_target = bool(payload["is_disposal_target"])
        if "return_status" in payload and payload["return_status"] is not None:
            return_status = payload["return_status"]
            if return_status not in VALID_RETURN_STATUSES:
                raise HTTPException(status_code=400, detail=f"無効な返送状況: {return_status}")
            item.return_status = return_status
        if "return_tracking_number" in payload:
            item.return_tracking_number = (payload["return_tracking_number"] or "").strip() or None
        if "return_shipping_cost" in payload:
            item.return_shipping_cost = payload["return_shipping_cost"]

        if item.line_status == models_buyback.BuybackItemLineStatus.rejected.value:
            reason = format_rejection_reason(item.rejection_reason_code, item.rejection_reason_text)
            if not reason:
                raise HTTPException(
                    status_code=400,
                    detail=f"「{item.product_name_snapshot}」の買取不可理由を入力してください",
                )
        elif item.line_status == models_buyback.BuybackItemLineStatus.reduced.value:
            if item.assessed_unit_price is None or item.assessed_unit_price < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"「{item.product_name_snapshot}」の減額査定単価を入力してください",
                )

    if apply_handling_policy:
        apply_rejected_item_handling(request)

    if recalculate_assessed_total:
        request.assessed_total = compute_assessed_total(list(request.items or []))
        request.assessed_at = datetime.utcnow()

    request.updated_at = datetime.utcnow()
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="request_items_updated",
        entity_type="buyback_request",
        entity_id=str(request.id),
        details={"item_count": len(item_updates), "assessed_total": request.assessed_total},
    )
    db.commit()
    return get_admin_request(db, request_id)


def identity_stats(db: Session) -> dict[str, int]:
    base = db.query(models_buyback.IdentityVerification)
    return {
        "pending_count": base.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.pending.value
        ).count(),
        "approved_count": base.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.approved.value
        ).count(),
        "rejected_count": base.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.rejected.value
        ).count(),
    }


def complete_request_payout(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    payout_total: Optional[int] = None,
    admin_note: Optional[str] = None,
    send_email: bool = True,
    force_email: bool = False,
) -> models_buyback.BuybackRequest:
    request = get_admin_request(db, request_id)
    if request.status != models_buyback.BuybackRequestStatus.payout_pending.value:
        raise HTTPException(
            status_code=400,
            detail="振込準備中の申込のみ振込完了にできます",
        )

    amount = payout_total if payout_total is not None else request.payout_total
    if amount is None or amount <= 0:
        raise HTTPException(status_code=400, detail="振込金額を入力してください")

    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="会員情報が見つかりません")

    default_account = get_default_payout_account(db, request.user_id)
    if not default_account:
        raise HTTPException(status_code=400, detail="振込口座が未登録です。振込前に口座登録を確認してください")

    updated = update_request_status(
        db,
        request_id=request_id,
        admin_user=admin_user,
        new_status=models_buyback.BuybackRequestStatus.paid.value,
        admin_note=admin_note,
        payout_total=amount,
    )

    email_ok = True
    email_err: str | None = None
    if send_email:
        email_ok, email_err = notify_buyback_payout_completed(
            db, updated, user, force=force_email
        )
        if not email_ok and email_err:
            logger.warning(
                "Payout completion email failed for request %s: %s",
                request_id,
                email_err,
            )

    _audit(
        db,
        actor_user_id=admin_user.id,
        action="request_payout_completed",
        entity_type="buyback_request",
        entity_id=str(request_id),
        details={
            "request_number": updated.request_number,
            "payout_total": amount,
            "email_sent": send_email and email_ok,
            "email_error": email_err,
        },
    )
    db.commit()
    return get_admin_request(db, request_id)


def get_request_payout_context(db: Session, request: models_buyback.BuybackRequest) -> dict:
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    default_account = get_default_payout_account(db, request.user_id)
    compliance = get_compliance_status(db, user_id=request.user_id)
    return {
        "payout_account": serialize_payout_account_for_admin(default_account)
        if default_account
        else None,
        "ready_for_payout": compliance.get("ready_for_payout", False),
        "payout_email_sent": payout_email_already_sent(db, request.id),
        "paid_at": request.paid_at,
    }


def request_stats(db: Session) -> dict[str, int]:
    base = db.query(models_buyback.BuybackRequest)
    return {
        "submitted_count": base.filter(
            models_buyback.BuybackRequest.status
            == models_buyback.BuybackRequestStatus.submitted.value
        ).count(),
        "in_progress_count": base.filter(
            models_buyback.BuybackRequest.status.in_(
                [
                    models_buyback.BuybackRequestStatus.received.value,
                    models_buyback.BuybackRequestStatus.assessing.value,
                    models_buyback.BuybackRequestStatus.assessed.value,
                    models_buyback.BuybackRequestStatus.awaiting_customer.value,
                ]
            )
        ).count(),
        "payout_pending_count": base.filter(
            models_buyback.BuybackRequest.status
            == models_buyback.BuybackRequestStatus.payout_pending.value
        ).count(),
    }
