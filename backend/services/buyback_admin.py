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
from services.buyback_compliance import PAYOUT_TRANSFER_STATUS_LABELS, get_compliance_status
from services.buyback_age import age_profile_for_user, requires_guardian_consent_for_user
from services.buyback_guardian import (
    get_latest_guardian_consent,
    guardian_documents_complete,
)
from services.buyback_identity_compare import build_profile_comparison
from services.user_profile import legal_full_name, legal_name_kana
from services.buyback_emails import (
    notify_buyback_assessment_ready,
    notify_buyback_decision,
    notify_buyback_payout_completed,
    send_buyback_status_change_email,
    payout_email_already_sent,
)
from services.kyc_emails import (
    notify_identity_approved,
    notify_identity_rejected,
    notify_identity_resubmit_requested,
    notify_identity_returned,
)
from services.buyback_item_labels import (
    apply_rejected_item_handling,
    compute_assessed_total,
    CONDITION_CODE_LABELS,
    format_rejection_reason,
    parse_assessment_lines,
)
from services.buyback_customer_review import sync_item_line_statuses_from_assessment
from services.buyback_payout_accounts import get_default_payout_account, serialize_payout_account_for_admin
from services.buyback_logistics_logs import write_buyback_audit
from services.buyback_pricing import (
    build_uniform_assessment_lines,
    resolve_assessment_unit_price_for_condition_change,
)
from services.buyback_request_status import (
    BARCODE_ONLY_STATUSES,
    DEDICATED_PAYOUT_STATUS,
    STATUS_LABELS,
    validate_transition,
)

logger = logging.getLogger(__name__)

DOCUMENT_TYPE_LABELS = {
    "drivers_license": "運転免許証",
    "my_number_card": "マイナンバーカード",
    "passport": "パスポート",
    "residence_card": "在留カード",
}

VALID_LINE_STATUSES = {
    models_buyback.BuybackItemLineStatus.pending.value,
    models_buyback.BuybackItemLineStatus.buyable.value,
    models_buyback.BuybackItemLineStatus.reduced.value,
    models_buyback.BuybackItemLineStatus.rejected.value,
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
    write_buyback_audit(
        db,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )


def _get_user_identity(db: Session, user_id: int) -> models_buyback.IdentityVerification | None:
    return (
        db.query(models_buyback.IdentityVerification)
        .filter(models_buyback.IdentityVerification.user_id == user_id)
        .order_by(models_buyback.IdentityVerification.id.desc())
        .first()
    )


def resolve_payout_transfer_status(request: models_buyback.BuybackRequest) -> str:
    if request.paid_at or request.payout_transfer_status == models_buyback.PayoutTransferStatus.completed.value:
        return models_buyback.PayoutTransferStatus.completed.value
    if (
        request.payout_scheduled_at
        or request.payout_transfer_status == models_buyback.PayoutTransferStatus.scheduled.value
    ):
        return models_buyback.PayoutTransferStatus.scheduled.value
    return models_buyback.PayoutTransferStatus.unpaid.value


def list_identity_verifications(
    db: Session,
    *,
    status: Optional[str] = None,
    review_queue: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
) -> list[models_buyback.IdentityVerification]:
    query = db.query(models_buyback.IdentityVerification).join(
        models.User, models_buyback.IdentityVerification.user_id == models.User.id
    )
    if status:
        query = query.filter(models_buyback.IdentityVerification.status == status)
    if review_queue == "waiting":
        query = query.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.pending.value,
            or_(
                models_buyback.IdentityVerification.admin_memo.is_(None),
                models_buyback.IdentityVerification.admin_memo == "",
            ),
        )
    elif review_queue == "in_review":
        query = query.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.pending.value,
            models_buyback.IdentityVerification.admin_memo.isnot(None),
            models_buyback.IdentityVerification.admin_memo != "",
        )
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


GUARDIAN_STATUS_LABELS = {
    "pending": "同意待ち",
    "signed": "同意済み",
    "expired": "期限切れ",
    "revoked": "取り消し",
}


def identity_approval_blockers(
    db: Session,
    *,
    row: models_buyback.IdentityVerification,
    user: models.User | None,
) -> list[str]:
    blockers: list[str] = []
    if not row.storage_key_front:
        blockers.append("本人確認書類（表面）")
    doc_type = (row.document_type or "").lower()
    if doc_type != "my_number_card" and not row.storage_key_back:
        blockers.append("本人確認書類（裏面）")

    if user and requires_guardian_consent_for_user(user):
        guardian = get_latest_guardian_consent(db, row.user_id)
        if not guardian or not (guardian.guardian_name or "").strip():
            blockers.append("保護者情報")
        if not guardian or not (guardian.guardian_email or "").strip():
            blockers.append("保護者メールアドレス")
        if not guardian or guardian.status != models_buyback.GuardianConsentStatus.signed.value:
            blockers.append("保護者同意")
        if not guardian or not guardian_documents_complete(guardian):
            blockers.append("保護者本人確認書類")
    return blockers


def build_admin_guardian_detail(
    db: Session,
    *,
    user: models.User | None,
) -> dict | None:
    if not user or not requires_guardian_consent_for_user(user):
        return None
    guardian = get_latest_guardian_consent(db, user.id)
    missing: list[str] = []
    if not guardian:
        return {
            "id": None,
            "status": "not_requested",
            "status_label": "保護者情報未提出",
            "guardian_name": None,
            "guardian_email": None,
            "guardian_relationship": None,
            "guardian_phone": None,
            "document_type": None,
            "document_type_label": None,
            "has_front": False,
            "has_back": False,
            "signed_at": None,
            "missing_items": [
                "保護者情報未提出",
                "保護者本人確認書類未提出",
                "保護者同意待ち",
            ],
        }

    status = guardian.status or "pending"
    status_label = GUARDIAN_STATUS_LABELS.get(status, status)
    if status != models_buyback.GuardianConsentStatus.signed.value:
        missing.append("保護者同意待ち")
    if not (guardian.guardian_name or "").strip():
        missing.append("保護者氏名未入力")
    if not (guardian.guardian_email or "").strip():
        missing.append("保護者メール未入力")
    if not guardian.storage_key_front:
        missing.append("保護者本人確認書類（表面）未提出")
    doc_type = (guardian.document_type or "").lower()
    if doc_type != "my_number_card" and not guardian.storage_key_back:
        missing.append("保護者本人確認書類（裏面）未提出")

    return {
        "id": guardian.id,
        "status": status,
        "status_label": status_label,
        "guardian_name": guardian.guardian_name,
        "guardian_email": guardian.guardian_email,
        "guardian_relationship": guardian.guardian_relationship,
        "guardian_phone": guardian.guardian_phone,
        "document_type": guardian.document_type,
        "document_type_label": DOCUMENT_TYPE_LABELS.get(guardian.document_type, guardian.document_type)
        if guardian.document_type
        else None,
        "has_front": bool(guardian.storage_key_front),
        "has_back": bool(guardian.storage_key_back),
        "signed_at": guardian.signed_at,
        "missing_items": missing,
    }


def approve_identity(
    db: Session,
    *,
    verification_id: int,
    admin_user: models.User,
    send_email: bool | None = None,
    force_email: bool = False,
) -> models_buyback.IdentityVerification:
    row = get_identity_verification(db, verification_id)
    if row.status != models_buyback.IdentityVerificationStatus.pending.value:
        raise HTTPException(status_code=400, detail="審査中の本人確認のみ承認できます")

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    blockers = identity_approval_blockers(db, row=row, user=user)
    if blockers:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "承認できません",
                "missing_items": blockers,
            },
        )

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

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if user:
        email_ok, email_err = notify_identity_approved(
            db, user=user, verification=row, send_email=send_email, force=force_email
        )
        if not email_ok and email_err:
            logger.warning(
                "Identity approved email failed verification_id=%s error=%s",
                row.id,
                email_err,
            )
    return row


def reject_identity(
    db: Session,
    *,
    verification_id: int,
    admin_user: models.User,
    rejection_reason: str,
    send_email: bool | None = None,
    force_email: bool = False,
) -> models_buyback.IdentityVerification:
    reason = (rejection_reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="否認理由を入力してください")

    row = get_identity_verification(db, verification_id)
    if row.status != models_buyback.IdentityVerificationStatus.pending.value:
        raise HTTPException(status_code=400, detail="審査中の本人確認のみ否認できます")

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

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if user:
        email_ok, email_err = notify_identity_rejected(
            db,
            user=user,
            verification=row,
            reason=reason,
            send_email=send_email,
            force=force_email,
        )
        if not email_ok and email_err:
            logger.warning(
                "Identity rejected email failed verification_id=%s error=%s",
                row.id,
                email_err,
            )
    return row


def request_resubmit_identity(
    db: Session,
    *,
    verification_id: int,
    admin_user: models.User,
    reason: str,
    admin_memo: str | None = None,
    send_email: bool | None = None,
    force_email: bool = False,
    notify_returned: bool = False,
) -> models_buyback.IdentityVerification:
    note = (reason or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="再提出理由を入力してください")

    row = get_identity_verification(db, verification_id)
    if row.status not in {
        models_buyback.IdentityVerificationStatus.pending.value,
        models_buyback.IdentityVerificationStatus.approved.value,
        models_buyback.IdentityVerificationStatus.rejected.value,
    }:
        raise HTTPException(status_code=400, detail="再提出依頼できないステータスです")

    now = datetime.utcnow()
    row.status = models_buyback.IdentityVerificationStatus.resubmit_requested.value
    row.reviewed_by_user_id = admin_user.id
    row.reviewed_at = now
    row.rejection_reason = note
    if admin_memo is not None:
        row.admin_memo = admin_memo.strip() or None
    row.updated_at = now
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="identity_resubmit_requested",
        entity_type="identity_verification",
        entity_id=str(row.id),
        details={"user_id": row.user_id, "reason": note},
    )
    db.commit()
    db.refresh(row)

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if user:
        if notify_returned:
            email_ok, email_err = notify_identity_returned(
                db,
                user=user,
                verification=row,
                reason=note,
                send_email=send_email,
                force=force_email,
            )
        else:
            email_ok, email_err = notify_identity_resubmit_requested(
                db,
                user=user,
                verification=row,
                reason=note,
                send_email=send_email,
                force=force_email,
            )
        if not email_ok and email_err:
            logger.warning(
                "Identity resubmit email failed verification_id=%s error=%s",
                row.id,
                email_err,
            )
    return row


def update_identity_admin_memo(
    db: Session,
    *,
    verification_id: int,
    admin_user: models.User,
    admin_memo: str,
) -> models_buyback.IdentityVerification:
    row = get_identity_verification(db, verification_id)
    row.admin_memo = (admin_memo or "").strip() or None
    row.updated_at = datetime.utcnow()
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="identity_admin_memo_updated",
        entity_type="identity_verification",
        entity_id=str(row.id),
        details={"user_id": row.user_id},
    )
    db.commit()
    db.refresh(row)
    return row


def list_admin_requests(
    db: Session,
    *,
    status: Optional[str] = None,
    buyback_method: Optional[str] = None,
    payout_transfer_status: Optional[str] = None,
    identity_not_approved: bool = False,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    allow_pii_search: bool = False,
    limit: int = 100,
) -> list[models_buyback.BuybackRequest]:
    from services.buyback_method import MAIL_ALIASES, STORE_ALIASES, normalize_buyback_method

    query = (
        db.query(models_buyback.BuybackRequest)
        .join(models.User, models_buyback.BuybackRequest.user_id == models.User.id)
        .options(joinedload(models_buyback.BuybackRequest.items))
    )
    if status:
        query = query.filter(models_buyback.BuybackRequest.status == status)
    if buyback_method:
        want = normalize_buyback_method(buyback_method)
        if want == "store":
            query = query.filter(
                models_buyback.BuybackRequest.buyback_method.in_(list(STORE_ALIASES))
            )
        else:
            query = query.filter(
                or_(
                    models_buyback.BuybackRequest.buyback_method.in_(list(MAIL_ALIASES)),
                    models_buyback.BuybackRequest.buyback_method.is_(None),
                    ~models_buyback.BuybackRequest.buyback_method.in_(list(STORE_ALIASES)),
                )
            )
    if payout_transfer_status:
        if payout_transfer_status == models_buyback.PayoutTransferStatus.completed.value:
            query = query.filter(
                or_(
                    models_buyback.BuybackRequest.payout_transfer_status
                    == models_buyback.PayoutTransferStatus.completed.value,
                    models_buyback.BuybackRequest.paid_at.isnot(None),
                )
            )
        elif payout_transfer_status == models_buyback.PayoutTransferStatus.scheduled.value:
            query = query.filter(
                or_(
                    models_buyback.BuybackRequest.payout_transfer_status
                    == models_buyback.PayoutTransferStatus.scheduled.value,
                    models_buyback.BuybackRequest.payout_scheduled_at.isnot(None),
                ),
                models_buyback.BuybackRequest.paid_at.is_(None),
            )
        elif payout_transfer_status == models_buyback.PayoutTransferStatus.unpaid.value:
            query = query.filter(models_buyback.BuybackRequest.paid_at.is_(None)).filter(
                or_(
                    models_buyback.BuybackRequest.payout_transfer_status.is_(None),
                    models_buyback.BuybackRequest.payout_transfer_status
                    == models_buyback.PayoutTransferStatus.unpaid.value,
                ),
                models_buyback.BuybackRequest.payout_scheduled_at.is_(None),
            )
    if identity_not_approved:
        approved_ids = (
            db.query(models_buyback.IdentityVerification.user_id)
            .filter(
                models_buyback.IdentityVerification.status
                == models_buyback.IdentityVerificationStatus.approved.value
            )
            .subquery()
        )
        query = query.filter(~models_buyback.BuybackRequest.user_id.in_(approved_ids))
    if date_from:
        query = query.filter(models_buyback.BuybackRequest.submitted_at >= date_from)
    if date_to:
        query = query.filter(models_buyback.BuybackRequest.submitted_at <= date_to)
    if q:
        term = f"%{q.strip()}%"
        search_filters = [models_buyback.BuybackRequest.request_number.ilike(term)]
        if allow_pii_search:
            search_filters.extend(
                [
                    models.User.email.ilike(term),
                    models.User.name.ilike(term),
                ]
            )
        query = query.filter(or_(*search_filters))
    rows = (
        query.order_by(
            models_buyback.BuybackRequest.submitted_at.desc(),
            models_buyback.BuybackRequest.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return rows


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
        raise HTTPException(status_code=404, detail="買取申請が見つかりません")
    return request


def update_request_status(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    new_status: str,
    admin_note: Optional[str] = None,
    customer_status_note: Optional[str] = None,
    tracking_number: Optional[str] = None,
    assessed_total: Optional[int] = None,
    payout_total: Optional[int] = None,
    allow_payout_completion: bool = False,
    send_email: bool | None = None,
    force_email: bool = False,
) -> models_buyback.BuybackRequest:
    request = get_admin_request(db, request_id)
    current = request.status
    if new_status in BARCODE_ONLY_STATUSES:
        _audit(
            db,
            actor_user_id=admin_user.id,
            action="protected_status_update_denied",
            entity_type="buyback_request",
            entity_id=str(request.id),
            details={
                "from_status": current,
                "to_status": new_status,
                "failure_reason": "barcode_required",
            },
        )
        db.commit()
        raise HTTPException(status_code=400, detail="無効なバーコードです")
    if (
        new_status == DEDICATED_PAYOUT_STATUS
        and not allow_payout_completion
    ):
        _audit(
            db,
            actor_user_id=admin_user.id,
            action="protected_status_update_denied",
            entity_type="buyback_request",
            entity_id=str(request.id),
            details={
                "from_status": current,
                "to_status": new_status,
                "failure_reason": "dedicated_operation_required",
            },
        )
        db.commit()
        raise HTTPException(status_code=400, detail="専用の振込完了処理を使用してください")

    if not validate_transition(current, new_status, request.buyback_method):
        raise HTTPException(
            status_code=400,
            detail=f"ステータスを {STATUS_LABELS.get(current, current)} から {STATUS_LABELS.get(new_status, new_status)} に変更できません",
        )

    now = datetime.utcnow()
    request.status = new_status
    if admin_note is not None:
        request.admin_note = admin_note.strip() or None
    if customer_status_note is not None:
        request.customer_status_note = customer_status_note.strip() or None
    if tracking_number is not None:
        request.tracking_number = tracking_number.strip() or None
    if assessed_total is not None:
        request.assessed_total = assessed_total
        request.assessed_at = now
    elif new_status in {
        models_buyback.BuybackRequestStatus.assessed.value,
        models_buyback.BuybackRequestStatus.awaiting_customer.value,
    }:
        sync_item_line_statuses_from_assessment(request)
        request.assessed_total = compute_assessed_total(request.items or [], request)
        request.assessed_at = request.assessed_at or now
    if payout_total is not None:
        request.payout_total = payout_total
    if new_status == models_buyback.BuybackRequestStatus.paid.value:
        request.paid_at = now
        request.payout_transfer_status = models_buyback.PayoutTransferStatus.completed.value
    if new_status == models_buyback.BuybackRequestStatus.payout_pending.value:
        if not request.payout_transfer_status:
            request.payout_transfer_status = models_buyback.PayoutTransferStatus.unpaid.value
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
                notify_buyback_assessment_ready(
                    db, request, user, force=force_email, send_email=send_email
                )
            elif new_status in {
                models_buyback.BuybackRequestStatus.accepted.value,
                models_buyback.BuybackRequestStatus.rejected.value,
            }:
                notify_buyback_decision(
                    db, request, user, force=force_email, send_email=send_email
                )
            else:
                send_buyback_status_change_email(
                    db,
                    request,
                    user,
                    to_status=new_status,
                    previous_status=current,
                    send_email=send_email,
                    force=force_email,
                )
    except Exception:
        logger.warning(
            "Status-change notification failed",
            extra={"request_id": request.id},
        )

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
    if any(
        any(
            key in payload
            for key in (
                "return_status",
                "return_tracking_number",
                "return_shipping_cost",
            )
        )
        for payload in item_updates
    ):
        _audit(
            db,
            actor_user_id=admin_user.id,
            action="protected_return_update_denied",
            entity_type="buyback_request",
            entity_id=str(request.id),
            details={"failure_reason": "barcode_required"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="無効なバーコードです")

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

        previous_condition_code = item.condition_code
        condition_changed = False
        if "condition_code" in payload and payload["condition_code"] is not None:
            code = str(payload["condition_code"]).strip()
            if code and code not in CONDITION_CODE_LABELS:
                raise HTTPException(status_code=400, detail=f"無効な状態コード: {code}")
            if code and code != previous_condition_code:
                condition_changed = True
                item.condition_code = code

        has_manual_lines = "assessment_lines" in payload
        has_manual_price = "assessed_unit_price" in payload

        if has_manual_lines:
            lines = payload["assessment_lines"]
            if lines is None:
                item.assessment_lines_json = None
            elif lines == []:
                item.assessment_lines_json = None
            else:
                if not isinstance(lines, list):
                    raise HTTPException(status_code=400, detail="査定内訳の形式が不正です")
                normalized: list[dict[str, int]] = []
                line_total_qty = 0
                for row in lines:
                    if not isinstance(row, dict):
                        raise HTTPException(status_code=400, detail="査定内訳の形式が不正です")
                    qty = row.get("quantity")
                    unit_price = row.get("unit_price")
                    try:
                        qty_int = int(qty)
                        price_int = int(unit_price)
                    except (TypeError, ValueError):
                        raise HTTPException(
                            status_code=400,
                            detail=f"「{item.product_name_snapshot}」の査定内訳（枚数・単価）を確認してください",
                        )
                    if qty_int <= 0 or price_int < 0:
                        raise HTTPException(
                            status_code=400,
                            detail=f"「{item.product_name_snapshot}」の査定内訳（枚数・単価）を確認してください",
                        )
                    normalized.append({"quantity": qty_int, "unit_price": price_int})
                    line_total_qty += qty_int
                if line_total_qty != item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"「{item.product_name_snapshot}」の査定枚数合計（{line_total_qty}枚）が"
                            f"申請枚数（{item.quantity}枚）と一致しません"
                        ),
                    )
                item.assessment_lines_json = json.dumps(normalized, ensure_ascii=False)
                subtotal = sum(row["quantity"] * row["unit_price"] for row in normalized)
                item.assessed_unit_price = subtotal // item.quantity if item.quantity else 0
        elif condition_changed:
            recalculated = resolve_assessment_unit_price_for_condition_change(
                db,
                item,
                previous_condition_code=previous_condition_code,
                new_condition_code=item.condition_code,
            )
            uniform_lines = build_uniform_assessment_lines(
                quantity=item.quantity,
                unit_price=recalculated,
            )
            item.assessed_unit_price = recalculated
            item.assessment_lines_json = (
                json.dumps(uniform_lines, ensure_ascii=False) if uniform_lines else None
            )
        elif has_manual_price:
            item.assessed_unit_price = payload["assessed_unit_price"]
        if "accepted_unit_price" in payload:
            item.accepted_unit_price = payload["accepted_unit_price"]
        if "rejection_reason_code" in payload:
            item.rejection_reason_code = payload["rejection_reason_code"] or None
        if "rejection_reason_text" in payload:
            item.rejection_reason_text = (payload["rejection_reason_text"] or "").strip() or None
        if "assessment_comment" in payload:
            comment = payload["assessment_comment"]
            item.assessment_comment = (comment or "").strip() or None
        if "is_return_target" in payload and payload["is_return_target"] is not None:
            item.is_return_target = bool(payload["is_return_target"])
        if "is_disposal_target" in payload and payload["is_disposal_target"] is not None:
            item.is_disposal_target = bool(payload["is_disposal_target"])
        if item.line_status == models_buyback.BuybackItemLineStatus.rejected.value:
            reason = format_rejection_reason(item.rejection_reason_code, item.rejection_reason_text)
            if not reason:
                raise HTTPException(
                    status_code=400,
                    detail=f"「{item.product_name_snapshot}」の買取不可理由を入力してください",
                )
        elif item.line_status == models_buyback.BuybackItemLineStatus.reduced.value:
            if not parse_assessment_lines(item):
                if item.assessed_unit_price is None or item.assessed_unit_price < 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"「{item.product_name_snapshot}」の減額査定単価を入力してください",
                    )
        elif item.line_status == models_buyback.BuybackItemLineStatus.buyable.value:
            if not parse_assessment_lines(item) and item.assessed_unit_price is None:
                item.assessed_unit_price = item.listed_unit_price

    if apply_handling_policy:
        apply_rejected_item_handling(request)

    if recalculate_assessed_total:
        request.assessed_total = compute_assessed_total(list(request.items or []), request)
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


ASSESSMENT_AUDIT_ACTIONS = frozenset(
    {
        "request_items_updated",
        "assessment_presented",
        "status_changed",
        "store_check_in",
        "assessment_started",
        "appraisal_estimate_sent",
        "store_payment_completed",
        "transaction_completed",
        "store_visit_rescheduled",
    }
)

ASSESSMENT_ACTION_LABELS: dict[str, str] = {
    "request_items_updated": "商品査定を更新",
    "assessment_presented": "査定結果を提示",
    "status_changed": "ステータス変更",
    "store_check_in": "来店チェックイン",
    "assessment_started": "査定開始",
    "appraisal_estimate_sent": "査定待ち時間を通知",
    "store_payment_completed": "店舗支払い完了",
    "transaction_completed": "店舗取引完了",
    "store_visit_rescheduled": "来店日時変更",
}


def list_request_assessment_logs(
    db: Session,
    *,
    request_id: int,
    limit: int = 50,
) -> list[dict]:
    get_admin_request(db, request_id)
    logs = (
        db.query(models_buyback.BuybackAuditLog)
        .filter(
            models_buyback.BuybackAuditLog.entity_type == "buyback_request",
            models_buyback.BuybackAuditLog.entity_id == str(request_id),
        )
        .order_by(models_buyback.BuybackAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    actor_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    actors: dict[int, models.User] = {}
    if actor_ids:
        for user in db.query(models.User).filter(models.User.id.in_(actor_ids)).all():
            actors[user.id] = user

    rows: list[dict] = []
    for log in logs:
        action = log.action or ""
        if action not in ASSESSMENT_AUDIT_ACTIONS:
            continue
        actor = actors.get(log.actor_user_id) if log.actor_user_id else None
        details = None
        if log.details_json:
            try:
                details = json.loads(log.details_json)
            except json.JSONDecodeError:
                details = {"raw": log.details_json}
        rows.append(
            {
                "id": log.id,
                "action": action,
                "action_label": ASSESSMENT_ACTION_LABELS.get(action, action),
                "actor_name": (actor.name or actor.email) if actor else None,
                "details": details,
                "created_at": log.created_at,
            }
        )
    return rows


def identity_stats(db: Session) -> dict[str, int]:
    base = db.query(models_buyback.IdentityVerification)
    pending_base = base.filter(
        models_buyback.IdentityVerification.status
        == models_buyback.IdentityVerificationStatus.pending.value
    )
    waiting_count = pending_base.filter(
        or_(
            models_buyback.IdentityVerification.admin_memo.is_(None),
            models_buyback.IdentityVerification.admin_memo == "",
        )
    ).count()
    in_review_count = pending_base.filter(
        models_buyback.IdentityVerification.admin_memo.isnot(None),
        models_buyback.IdentityVerification.admin_memo != "",
    ).count()
    return {
        "pending_count": waiting_count,
        "in_review_count": in_review_count,
        "approved_count": base.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.approved.value
        ).count(),
        "rejected_count": base.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.rejected.value
        ).count(),
        "resubmit_requested_count": base.filter(
            models_buyback.IdentityVerification.status
            == models_buyback.IdentityVerificationStatus.resubmit_requested.value
        ).count(),
    }


def schedule_request_payout(
    db: Session,
    *,
    request_id: int,
    admin_user: models.User,
    payout_scheduled_at: datetime,
    admin_note: str | None = None,
) -> models_buyback.BuybackRequest:
    request = get_admin_request(db, request_id)
    if request.status not in {
        models_buyback.BuybackRequestStatus.payout_pending.value,
        models_buyback.BuybackRequestStatus.accepted.value,
    }:
        raise HTTPException(status_code=400, detail="振込予定日を設定できるステータスではありません")
    if request.paid_at:
        raise HTTPException(status_code=400, detail="振込済みの申込です")

    request.payout_scheduled_at = payout_scheduled_at
    request.payout_transfer_status = models_buyback.PayoutTransferStatus.scheduled.value
    if admin_note is not None:
        request.admin_note = admin_note.strip() or None
    request.updated_at = datetime.utcnow()
    _audit(
        db,
        actor_user_id=admin_user.id,
        action="request_payout_scheduled",
        entity_type="buyback_request",
        entity_id=str(request_id),
        details={
            "payout_scheduled_at": payout_scheduled_at.isoformat(),
            "payout_total": request.payout_total,
        },
    )
    db.commit()
    return get_admin_request(db, request_id)


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
        allow_payout_completion=True,
    )
    updated.payout_transfer_status = models_buyback.PayoutTransferStatus.completed.value

    email_ok = True
    email_err: str | None = None
    if send_email:
        email_ok, email_err = notify_buyback_payout_completed(
            db, updated, user, force=force_email
        )
        if not email_ok and email_err:
            logger.warning(
                "Payout completion email failed",
                extra={"request_id": request_id},
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
            "email_failed": bool(email_err),
        },
    )
    db.commit()
    return get_admin_request(db, request_id)


def get_request_payout_context(db: Session, request: models_buyback.BuybackRequest) -> dict:
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    default_account = get_default_payout_account(db, request.user_id)
    compliance = get_compliance_status(db, user_id=request.user_id, user=user)
    identity = _get_user_identity(db, request.user_id)
    identity_approved_at = None
    if identity and identity.status == models_buyback.IdentityVerificationStatus.approved.value:
        identity_approved_at = identity.reviewed_at
    transfer_status = resolve_payout_transfer_status(request)
    return {
        "payout_account": serialize_payout_account_for_admin(default_account)
        if default_account
        else None,
        "ready_for_payout": compliance.get("ready_for_payout", False),
        "payout_email_sent": payout_email_already_sent(db, request.id),
        "paid_at": request.paid_at,
        "payout_scheduled_at": request.payout_scheduled_at,
        "payout_transfer_status": transfer_status,
        "payout_transfer_status_label": PAYOUT_TRANSFER_STATUS_LABELS.get(
            transfer_status, transfer_status
        ),
        "identity_status": compliance.get("identity_status"),
        "identity_status_label": compliance.get("identity_status_label"),
        "identity_approved_at": identity_approved_at,
        "assessment_approved_at": request.customer_confirmed_at or request.assessed_at,
        "requires_guardian_consent": compliance.get("requires_guardian_consent", False),
        "guardian_status": compliance.get("guardian_status"),
        "guardian_status_label": compliance.get("guardian_status_label"),
        "guardian_ready": compliance.get("guardian_ready", True),
    }


def _count_channel_requests(
    db: Session,
    *,
    method: str,
    exclude_statuses: frozenset[str] | None = None,
) -> dict[str, int]:
    from services.buyback_method import normalize_buyback_method

    exclude = exclude_statuses or frozenset({"draft", "completed", "cancelled"})
    rows = db.query(
        models_buyback.BuybackRequest.status,
        models_buyback.BuybackRequest.buyback_method,
    ).all()

    stats = {
        "total_count": 0,
        "assessing_count": 0,
        "awaiting_customer_count": 0,
        "awaiting_arrival_count": 0,
        "awaiting_visit_count": 0,
    }
    for status, buyback_method in rows:
        if normalize_buyback_method(buyback_method) != method:
            continue
        if status in exclude:
            continue
        stats["total_count"] += 1
        if status == models_buyback.BuybackRequestStatus.assessing.value:
            stats["assessing_count"] += 1
        elif status == models_buyback.BuybackRequestStatus.awaiting_customer.value:
            stats["awaiting_customer_count"] += 1
        elif method == "mail" and status in {
            models_buyback.BuybackRequestStatus.awaiting_shipment.value,
            models_buyback.BuybackRequestStatus.shipped.value,
        }:
            stats["awaiting_arrival_count"] += 1
        elif method == "store" and status in {
            models_buyback.BuybackRequestStatus.awaiting_visit.value,
            models_buyback.BuybackRequestStatus.submitted.value,
        }:
            stats["awaiting_visit_count"] += 1
    return stats


def _payout_queue_stats(db: Session) -> dict[str, int]:
    from sqlalchemy import or_

    base = db.query(models_buyback.BuybackRequest).filter(
        models_buyback.BuybackRequest.status
        == models_buyback.BuybackRequestStatus.payout_pending.value
    )
    scheduled_count = base.filter(
        models_buyback.BuybackRequest.payout_transfer_status
        == models_buyback.PayoutTransferStatus.scheduled.value
    ).count()
    waiting_count = base.filter(
        or_(
            models_buyback.BuybackRequest.payout_transfer_status.is_(None),
            models_buyback.BuybackRequest.payout_transfer_status
            == models_buyback.PayoutTransferStatus.unpaid.value,
        )
    ).count()
    approved_identity = models_buyback.IdentityVerificationStatus.approved.value
    needs_review_count = (
        db.query(models_buyback.BuybackRequest)
        .outerjoin(
            models_buyback.IdentityVerification,
            models_buyback.IdentityVerification.user_id == models_buyback.BuybackRequest.user_id,
        )
        .filter(
            models_buyback.BuybackRequest.status
            == models_buyback.BuybackRequestStatus.payout_pending.value,
            or_(
                models_buyback.IdentityVerification.id.is_(None),
                models_buyback.IdentityVerification.status != approved_identity,
            ),
        )
        .count()
    )
    return {
        "scheduled_count": scheduled_count,
        "waiting_count": waiting_count,
        "needs_review_count": needs_review_count,
        "failed_count": 0,
    }


def request_stats(db: Session) -> dict[str, object]:
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
                    models_buyback.BuybackRequestStatus.awaiting_visit.value,
                    models_buyback.BuybackRequestStatus.store_visited.value,
                ]
            )
        ).count(),
        "payout_pending_count": base.filter(
            models_buyback.BuybackRequest.status
            == models_buyback.BuybackRequestStatus.payout_pending.value
        ).count(),
        "payout": _payout_queue_stats(db),
        "mail": _count_channel_requests(db, method="mail"),
        "store": _count_channel_requests(db, method="store"),
    }
