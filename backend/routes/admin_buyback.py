"""Admin buyback management routes (Phase 7)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

import models
import schemas_buyback
from auth import get_current_admin
from database import get_db
from services.buyback_admin import (
    DOCUMENT_TYPE_LABELS,
    REQUEST_TRANSITIONS,
    approve_identity,
    complete_request_payout,
    get_admin_request,
    get_identity_verification,
    get_request_payout_context,
    identity_stats,
    list_admin_requests,
    list_identity_verifications,
    reject_identity,
    request_stats,
    update_request_status,
)
from services.buyback_compliance import IDENTITY_STATUS_LABELS
from services.buyback_emails import STATUS_LABELS
from services.buyback_kyc_storage import fetch_kyc_document
from services.db_persist import PersistDep

router = APIRouter(
    prefix="/api/admin/buyback",
    tags=["admin-buyback"],
    dependencies=[PersistDep],
)


def _user_map(db: Session, user_ids: set[int]) -> dict[int, models.User]:
    if not user_ids:
        return {}
    rows = db.query(models.User).filter(models.User.id.in_(user_ids)).all()
    return {row.id: row for row in rows}


def _identity_list_out(row, user: models.User | None) -> schemas_buyback.AdminIdentityListOut:
    doc_type = row.document_type
    return schemas_buyback.AdminIdentityListOut(
        id=row.id,
        user_id=row.user_id,
        user_email=user.email if user else "",
        user_name=user.name if user else "",
        status=row.status,
        status_label=IDENTITY_STATUS_LABELS.get(row.status, row.status),
        document_type=doc_type,
        document_type_label=DOCUMENT_TYPE_LABELS.get(doc_type, doc_type) if doc_type else None,
        has_front=bool(row.storage_key_front),
        has_back=bool(row.storage_key_back),
        submitted_at=row.submitted_at,
        updated_at=row.updated_at,
    )


@router.get("/stats", response_model=schemas_buyback.AdminBuybackStatsOut)
def buyback_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    kyc = identity_stats(db)
    req = request_stats(db)
    return schemas_buyback.AdminBuybackStatsOut(
        pending_kyc_count=kyc["pending_count"],
        submitted_request_count=req["submitted_count"],
        in_progress_request_count=req["in_progress_count"],
        payout_pending_count=req["payout_pending_count"],
    )


@router.get("/identity", response_model=list[schemas_buyback.AdminIdentityListOut])
def list_identity(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    rows = list_identity_verifications(db, status=status, q=q)
    users = _user_map(db, {row.user_id for row in rows})
    return [_identity_list_out(row, users.get(row.user_id)) for row in rows]


@router.get("/identity/{verification_id}", response_model=schemas_buyback.AdminIdentityDetailOut)
def get_identity(
    verification_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    row = get_identity_verification(db, verification_id)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    reviewer = None
    if row.reviewed_by_user_id:
        reviewer = (
            db.query(models.User).filter(models.User.id == row.reviewed_by_user_id).first()
        )
    base = _identity_list_out(row, user)
    return schemas_buyback.AdminIdentityDetailOut(
        **base.model_dump(),
        rejection_reason=row.rejection_reason,
        reviewed_at=row.reviewed_at,
        reviewer_name=reviewer.name if reviewer else None,
    )


@router.get("/identity/{verification_id}/documents/{side}")
def get_identity_document(
    verification_id: int,
    side: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side は front または back を指定してください")

    row = get_identity_verification(db, verification_id)
    key = row.storage_key_front if side == "front" else row.storage_key_back
    if not key:
        raise HTTPException(status_code=404, detail="書類画像が見つかりません")

    try:
        data, content_type = fetch_kyc_document(key=key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="書類画像が見つかりません") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(content=data, media_type=content_type)


@router.post("/identity/{verification_id}/approve", response_model=schemas_buyback.AdminIdentityDetailOut)
def approve_identity_route(
    verification_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    row = approve_identity(db, verification_id=verification_id, admin_user=admin)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    base = _identity_list_out(row, user)
    return schemas_buyback.AdminIdentityDetailOut(**base.model_dump(), reviewed_at=row.reviewed_at)


@router.post("/identity/{verification_id}/reject", response_model=schemas_buyback.AdminIdentityDetailOut)
def reject_identity_route(
    verification_id: int,
    body: schemas_buyback.AdminIdentityRejectIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    row = reject_identity(
        db,
        verification_id=verification_id,
        admin_user=admin,
        rejection_reason=body.rejection_reason,
    )
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    base = _identity_list_out(row, user)
    return schemas_buyback.AdminIdentityDetailOut(
        **base.model_dump(),
        rejection_reason=row.rejection_reason,
        reviewed_at=row.reviewed_at,
    )


def _request_list_out(request, user: models.User | None) -> schemas_buyback.AdminBuybackRequestListOut:
    return schemas_buyback.AdminBuybackRequestListOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        user_id=request.user_id,
        user_email=user.email if user else "",
        user_name=user.name if user else "",
        item_count=len(request.items or []),
        estimated_total=request.estimated_total,
        payout_total=request.payout_total,
        submitted_at=request.submitted_at,
        created_at=request.created_at,
    )


def _request_detail_out(
    request: models_buyback.BuybackRequest,
    user: models.User | None,
    db: Session,
) -> schemas_buyback.AdminBuybackRequestDetailOut:
    history = [
        schemas_buyback.AdminBuybackStatusHistoryOut(
            id=h.id,
            from_status=h.from_status,
            from_status_label=STATUS_LABELS.get(h.from_status, h.from_status)
            if h.from_status
            else None,
            to_status=h.to_status,
            to_status_label=STATUS_LABELS.get(h.to_status, h.to_status),
            note=h.note,
            created_at=h.created_at,
        )
        for h in sorted(request.status_history or [], key=lambda x: x.created_at)
    ]
    payout_ctx = get_request_payout_context(db, request)
    payout_account = payout_ctx["payout_account"]
    return schemas_buyback.AdminBuybackRequestDetailOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        user_id=request.user_id,
        user_email=user.email if user else "",
        user_name=user.name if user else "",
        shipping_method=request.shipping_method,
        tracking_number=request.tracking_number,
        customer_note=request.customer_note,
        admin_note=request.admin_note,
        estimated_total=request.estimated_total,
        assessed_total=request.assessed_total,
        payout_total=request.payout_total,
        submitted_at=request.submitted_at,
        created_at=request.created_at,
        items=[
            schemas_buyback.BuybackRequestItemOut.model_validate(item)
            for item in (request.items or [])
        ],
        status_history=history,
        allowed_next_statuses=sorted(REQUEST_TRANSITIONS.get(request.status, set())),
        payout_account=schemas_buyback.AdminPayoutAccountOut(**payout_account)
        if payout_account
        else None,
        ready_for_payout=payout_ctx["ready_for_payout"],
        payout_email_sent=payout_ctx["payout_email_sent"],
        paid_at=payout_ctx["paid_at"],
    )


@router.get("/requests", response_model=list[schemas_buyback.AdminBuybackRequestListOut])
def list_requests(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    rows = list_admin_requests(db, status=status, q=q)
    users = _user_map(db, {row.user_id for row in rows})
    return [_request_list_out(row, users.get(row.user_id)) for row in rows]


@router.get("/requests/{request_id}", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db)


@router.post("/requests/{request_id}/complete-payout", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def complete_payout_route(
    request_id: int,
    body: schemas_buyback.AdminCompletePayoutIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    complete_request_payout(
        db,
        request_id=request_id,
        admin_user=admin,
        payout_total=body.payout_total,
        admin_note=body.admin_note,
        send_email=body.send_email,
        force_email=body.force_email,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db)


@router.patch("/requests/{request_id}", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def patch_request(
    request_id: int,
    body: schemas_buyback.AdminBuybackRequestUpdateIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    update_request_status(
        db,
        request_id=request_id,
        admin_user=admin,
        new_status=body.status,
        admin_note=body.admin_note,
        tracking_number=body.tracking_number,
        assessed_total=body.assessed_total,
        payout_total=body.payout_total,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db)
