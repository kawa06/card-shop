"""Admin buyback management routes (Phase 7)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

import models
import models_buyback
import schemas_buyback
import schemas_email
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.buyback_admin import (
    DOCUMENT_TYPE_LABELS,
    approve_identity,
    build_admin_guardian_detail,
    complete_request_payout,
    get_admin_request,
    get_identity_verification,
    get_request_payout_context,
    identity_approval_blockers,
    identity_stats,
    list_admin_requests,
    list_identity_verifications,
    reject_identity,
    request_resubmit_identity,
    request_stats,
    resolve_payout_transfer_status,
    schedule_request_payout,
    update_identity_admin_memo,
    update_request_items,
    update_request_status,
)
from services.buyback_age import age_profile_for_user, requires_guardian_consent_for_user
from services.buyback_guardian import get_latest_guardian_consent
from services.buyback_identity_compare import build_profile_comparison
from services.buyback_kyc_storage import fetch_kyc_document
from services.user_profile import legal_full_name, legal_name_kana
from services.buyback_serializers import (
    rejection_reason_options,
    rejected_item_handling_label,
    serialize_appraisal_estimate,
    serialize_request_item,
    store_payment_method_label,
)
from services.buyback_method import buyback_method_label, is_store_purchase, normalize_buyback_method
from services.buyback_customer_review import present_assessment_to_customer
from services.buyback_store_workflow import (
    check_in_store_visit,
    complete_store_payment,
    complete_store_transaction,
    send_appraisal_estimate,
    start_store_assessment,
    update_store_visit_at,
)
from services.buyback_compliance import IDENTITY_STATUS_LABELS, PAYOUT_TRANSFER_STATUS_LABELS
from services.buyback_request_status import (
    STATUS_DESCRIPTIONS,
    STATUS_LABELS,
    allowed_next_statuses,
    status_color,
    status_description,
)
from services.buyback_admin_permissions import (
    can_complete_payout,
    can_view_bank_account,
    can_view_kyc,
    can_view_kyc_documents,
    can_view_payout_queue,
    has_any_buyback_perm,
    has_buyback_perm,
)
from services.buyback_firestore_import import import_firestore_buylist_export, validate_import_counts
from services.buyback_logistics_logs import write_buyback_audit
from services import buyback_catalog
from services.buyback_catalog import (
    CatalogConflictError,
    CatalogNotFoundError,
    CatalogPersistenceError,
    CatalogValidationError,
)
from services.db_persist import PersistDep
from sqlalchemy.orm import selectinload

router = APIRouter(
    prefix="/api/admin/buyback",
    tags=["admin-buyback"],
    dependencies=[PersistDep],
)


def _enforce_permission(
    db: Session,
    ctx: AdminContext,
    permission: str,
    *,
    request: Request,
) -> None:
    if has_buyback_perm(ctx, permission):
        return
    try:
        require_permission(ctx, permission)
    except AdminAccessError as exc:
        write_buyback_audit(
            db,
            actor_user_id=ctx.user.id,
            action="permission_denied",
            entity_type="admin_buyback_endpoint",
            entity_id=request.url.path,
            details={
                "required_permission": permission,
                "method": request.method,
                "failure_reason": "insufficient_permission",
            },
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail="権限が不足しています") from exc


def _require_perms(*permissions: str):
    def _dep(
        request: Request,
        db: Session = Depends(get_db),
        ctx: AdminContext = Depends(get_current_admin_context),
    ) -> AdminContext:
        for permission in permissions:
            _enforce_permission(db, ctx, permission, request=request)
        return ctx

    return _dep


def _require_perm(permission: str):
    return _require_perms(permission)


def _audit_access(
    db: Session,
    ctx: AdminContext,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    includes_pii: bool = False,
) -> None:
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"includes_pii": includes_pii},
    )
    db.commit()


def _user_map(db: Session, user_ids: set[int]) -> dict[int, models.User]:
    if not user_ids:
        return {}
    rows = db.query(models.User).filter(models.User.id.in_(user_ids)).all()
    return {row.id: row for row in rows}


def _identity_status_label(row: models_buyback.IdentityVerification) -> str:
    if row.status == models_buyback.IdentityVerificationStatus.pending.value:
        if row.admin_memo and str(row.admin_memo).strip():
            return "審査中"
        return "審査待ち"
    return IDENTITY_STATUS_LABELS.get(row.status, row.status)


def _identity_list_out(
    row,
    user: models.User | None,
    reviewer: models.User | None = None,
) -> schemas_buyback.AdminIdentityListOut:
    doc_type = row.document_type
    return schemas_buyback.AdminIdentityListOut(
        id=row.id,
        user_id=row.user_id,
        public_member_id=user.public_member_id if user else None,
        user_email=user.email if user else "",
        user_name=user.name if user else "",
        status=row.status,
        status_label=_identity_status_label(row),
        document_type=doc_type,
        document_type_label=DOCUMENT_TYPE_LABELS.get(doc_type, doc_type) if doc_type else None,
        has_front=bool(row.storage_key_front),
        has_back=bool(row.storage_key_back),
        submitted_at=row.submitted_at,
        updated_at=row.updated_at,
        reviewer_name=reviewer.name if reviewer else None,
    )


def _identity_detail_out(
    row: models_buyback.IdentityVerification,
    user: models.User | None,
    reviewer: models.User | None = None,
    db: Session | None = None,
) -> schemas_buyback.AdminIdentityDetailOut:
    base = _identity_list_out(row, user, reviewer)
    age, _ = age_profile_for_user(user)
    is_minor = bool(user and requires_guardian_consent_for_user(user))
    comparison = build_profile_comparison(user, row)
    guardian = build_admin_guardian_detail(db, user=user) if db and user else None
    blockers = identity_approval_blockers(db, row=row, user=user) if db else []
    return schemas_buyback.AdminIdentityDetailOut(
        **base.model_dump(),
        rejection_reason=row.rejection_reason,
        admin_memo=row.admin_memo,
        reviewed_at=row.reviewed_at,
        legal_full_name=legal_full_name(user) or None,
        family_name=user.family_name if user else None,
        given_name=user.given_name if user else None,
        family_name_kana=user.family_name_kana if user else None,
        given_name_kana=user.given_name_kana if user else None,
        display_name=user.name if user else None,
        phone_number=user.phone_number if user else None,
        birth_date=user.birth_date.isoformat() if user and user.birth_date else None,
        age=age,
        is_minor=is_minor,
        postal_code=user.postal_code if user else None,
        prefecture=user.region if user else None,
        city=user.city if user else None,
        address_line1=user.address_line1 if user else None,
        address_line2=user.address_line2 if user else None,
        profile_comparison=schemas_buyback.AdminIdentityComparisonOut(**comparison),
        guardian=schemas_buyback.AdminGuardianDetailOut(**guardian) if guardian else None,
        can_approve=not blockers and row.status == models_buyback.IdentityVerificationStatus.pending.value,
        approval_blockers=blockers,
    )


@router.get("/stats", response_model=schemas_buyback.AdminBuybackStatsOut)
def buyback_stats(
    db: Session = Depends(get_db),
    _: AdminContext = Depends(_require_perm("buyback.request.read")),
):
    kyc = identity_stats(db)
    req = request_stats(db)
    mail = req.get("mail") or {}
    store = req.get("store") or {}
    payout = req.get("payout") or {}
    return schemas_buyback.AdminBuybackStatsOut(
        pending_kyc_count=kyc["pending_count"],
        kyc_in_review_count=kyc["in_review_count"],
        kyc_resubmit_count=kyc["resubmit_requested_count"],
        submitted_request_count=req["submitted_count"],
        in_progress_request_count=req["in_progress_count"],
        payout_pending_count=req["payout_pending_count"],
        payout_scheduled_count=payout.get("scheduled_count", 0),
        payout_waiting_count=payout.get("waiting_count", 0),
        payout_needs_review_count=payout.get("needs_review_count", 0),
        payout_failed_count=payout.get("failed_count", 0),
        mail=schemas_buyback.BuybackChannelStatsOut(**mail),
        store=schemas_buyback.BuybackChannelStatsOut(**store),
    )


@router.get("/identity", response_model=list[schemas_buyback.AdminIdentityListOut])
def list_identity(
    status: Optional[str] = Query(None),
    review_queue: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("kyc.view")
    ),
):
    if review_queue and review_queue not in {"waiting", "in_review"}:
        raise HTTPException(status_code=400, detail="review_queue が不正です")
    rows = list_identity_verifications(db, status=status, review_queue=review_queue, q=q)
    users = _user_map(db, {row.user_id for row in rows})
    reviewer_ids = {row.reviewed_by_user_id for row in rows if row.reviewed_by_user_id}
    reviewers = _user_map(db, reviewer_ids)
    result = [
        _identity_list_out(row, users.get(row.user_id), reviewers.get(row.reviewed_by_user_id))
        for row in rows
    ]
    _audit_access(
        db,
        ctx,
        action="pii_identity_list_viewed",
        entity_type="identity_verification_list",
        includes_pii=True,
    )
    return result


@router.get("/identity/{verification_id}", response_model=schemas_buyback.AdminIdentityDetailOut)
def get_identity(
    verification_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("kyc.view")
    ),
):
    row = get_identity_verification(db, verification_id)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    reviewer = None
    if row.reviewed_by_user_id:
        reviewer = (
            db.query(models.User).filter(models.User.id == row.reviewed_by_user_id).first()
        )
    result = schemas_buyback.AdminIdentityDetailOut(
        **_identity_detail_out(row, user, reviewer, db=db).model_dump(),
    )
    _audit_access(
        db,
        ctx,
        action="pii_identity_detail_viewed",
        entity_type="identity_verification",
        entity_id=row.id,
        includes_pii=True,
    )
    return result


@router.get("/identity/{verification_id}/documents/{side}")
def get_identity_document(
    verification_id: int,
    side: str,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perms("kyc.document.view")),
):
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side は front または back を指定してください")

    row = get_identity_verification(db, verification_id)
    if side == "back" and (row.document_type or "").lower() in ("my_number_card", "my_number"):
        raise HTTPException(status_code=404, detail="マイナンバーカードの裏面は保存・表示されません")
    key = row.storage_key_front if side == "front" else row.storage_key_back
    if not key:
        raise HTTPException(status_code=404, detail="書類画像が見つかりません")

    try:
        data, content_type = fetch_kyc_document(key=key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="書類画像が見つかりません") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="書類画像を取得できません") from exc

    _audit_access(
        db,
        ctx,
        action="pii_identity_document_viewed",
        entity_type="identity_verification",
        entity_id=row.id,
        includes_pii=True,
    )
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate, private"}
    return Response(content=data, media_type=content_type, headers=headers)


@router.get("/identity/{verification_id}/guardian/documents/{side}")
def get_guardian_document(
    verification_id: int,
    side: str,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perms("guardian_consent.view", "kyc.document.view")),
):
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side は front または back を指定してください")

    row = get_identity_verification(db, verification_id)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if not user or not requires_guardian_consent_for_user(user):
        raise HTTPException(status_code=404, detail="保護者情報はありません")

    guardian = get_latest_guardian_consent(db, row.user_id)
    if not guardian:
        raise HTTPException(status_code=404, detail="保護者情報が見つかりません")
    if side == "back" and (guardian.document_type or "").lower() in ("my_number_card", "my_number"):
        raise HTTPException(status_code=404, detail="マイナンバーカードの裏面は保存・表示されません")

    key = guardian.storage_key_front if side == "front" else guardian.storage_key_back
    if not key:
        raise HTTPException(status_code=404, detail="保護者書類画像が見つかりません")

    try:
        data, content_type = fetch_kyc_document(key=key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="保護者書類画像が見つかりません") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="保護者書類画像を取得できません") from exc

    _audit_access(
        db,
        ctx,
        action="pii_guardian_document_viewed",
        entity_type="guardian_consent",
        entity_id=guardian.id,
        includes_pii=True,
    )
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate, private"}
    return Response(content=data, media_type=content_type, headers=headers)


@router.post("/identity/{verification_id}/approve", response_model=schemas_buyback.AdminIdentityDetailOut)
def approve_identity_route(
    verification_id: int,
    body: schemas_buyback.AdminIdentityApproveIn | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("kyc.review")
    ),
):
    opts = body or schemas_buyback.AdminIdentityApproveIn()
    row = approve_identity(
        db,
        verification_id=verification_id,
        admin_user=ctx.user,
        send_email=opts.send_email,
        force_email=opts.force_email,
    )
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    return _identity_detail_out(row, user, db=db)


@router.post("/identity/{verification_id}/reject", response_model=schemas_buyback.AdminIdentityDetailOut)
def reject_identity_route(
    verification_id: int,
    body: schemas_buyback.AdminIdentityRejectIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("kyc.review")
    ),
):
    row = reject_identity(
        db,
        verification_id=verification_id,
        admin_user=ctx.user,
        rejection_reason=body.rejection_reason,
        send_email=body.send_email,
        force_email=body.force_email,
    )
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    return _identity_detail_out(row, user, db=db)


@router.post(
    "/identity/{verification_id}/request-resubmit",
    response_model=schemas_buyback.AdminIdentityDetailOut,
)
def request_resubmit_identity_route(
    verification_id: int,
    body: schemas_buyback.AdminIdentityResubmitIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("kyc.review")
    ),
):
    row = request_resubmit_identity(
        db,
        verification_id=verification_id,
        admin_user=ctx.user,
        reason=body.reason,
        admin_memo=body.admin_memo,
        send_email=body.send_email,
        force_email=body.force_email,
        notify_returned=body.notify_returned,
    )
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    return _identity_detail_out(row, user, db=db)


@router.post("/identity/{verification_id}/resend-email")
def resend_identity_email_route(
    verification_id: int,
    body: schemas_email.AdminIdentityResendEmailIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perms("kyc.review")),
):
    from services.kyc_emails import resend_kyc_email

    row = get_identity_verification(db, verification_id)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    ok, err = resend_kyc_email(
        db,
        event_key=body.event_key,
        user=user,
        verification=row,
        reason=row.rejection_reason,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=err or "メール送信に失敗しました")
    return {"message": "メールを再送しました", "event_key": body.event_key}


@router.patch(
    "/identity/{verification_id}/memo",
    response_model=schemas_buyback.AdminIdentityDetailOut,
)
def update_identity_memo_route(
    verification_id: int,
    body: schemas_buyback.AdminIdentityMemoIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("kyc.review")
    ),
):
    row = update_identity_admin_memo(
        db,
        verification_id=verification_id,
        admin_user=ctx.user,
        admin_memo=body.admin_memo,
    )
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    return _identity_detail_out(row, user, db=db)


def _request_list_out(
    request,
    user: models.User | None,
    *,
    include_pii: bool,
    identity_row: models_buyback.IdentityVerification | None = None,
) -> schemas_buyback.AdminBuybackRequestListOut:
    method = normalize_buyback_method(request.buyback_method)
    transfer_status = resolve_payout_transfer_status(request)
    identity_status = identity_row.status if identity_row else None
    return schemas_buyback.AdminBuybackRequestListOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        buyback_method=method,
        buyback_method_label=buyback_method_label(method),
        user_id=request.user_id,
        user_email=user.email if include_pii and user else "",
        user_name=user.name if include_pii and user else "",
        item_count=len(request.items or []),
        estimated_total=request.estimated_total,
        payout_total=request.payout_total,
        identity_status=identity_status,
        identity_status_label=IDENTITY_STATUS_LABELS.get(identity_status, identity_status)
        if identity_status
        else None,
        payout_transfer_status=transfer_status,
        payout_transfer_status_label=PAYOUT_TRANSFER_STATUS_LABELS.get(
            transfer_status, transfer_status
        ),
        payout_scheduled_at=request.payout_scheduled_at,
        paid_at=request.paid_at,
        submitted_at=request.submitted_at,
        created_at=request.created_at,
    )


def _request_detail_out(
    request: models_buyback.BuybackRequest,
    user: models.User | None,
    db: Session,
    *,
    ctx: AdminContext,
) -> schemas_buyback.AdminBuybackRequestDetailOut:
    include_contact = can_view_kyc(ctx) or can_view_payout_queue(ctx)
    include_bank = can_view_bank_account(ctx)
    actor_ids = {
        h.changed_by_user_id for h in (request.status_history or []) if h.changed_by_user_id
    }
    actors = {}
    if actor_ids and include_contact:
        rows = db.query(models.User).filter(models.User.id.in_(actor_ids)).all()
        actors = {row.id: row.name or row.email for row in rows}
    history = [
        schemas_buyback.AdminBuybackStatusHistoryOut(
            id=h.id,
            from_status=h.from_status,
            from_status_label=STATUS_LABELS.get(h.from_status, h.from_status)
            if h.from_status
            else None,
            to_status=h.to_status,
            to_status_label=STATUS_LABELS.get(h.to_status, h.to_status),
            changed_by_name=actors.get(h.changed_by_user_id) if include_contact else None,
            note=h.note if include_contact else None,
            created_at=h.created_at,
        )
        for h in sorted(request.status_history or [], key=lambda x: x.created_at)
    ]
    payout_ctx = get_request_payout_context(db, request)
    payout_account = payout_ctx.get("payout_account") if include_bank else None
    next_statuses = allowed_next_statuses(request, permissions=set(ctx.permissions))
    handling = request.rejected_item_handling
    method = normalize_buyback_method(request.buyback_method)
    estimate_row = (
        db.query(models_buyback.BuybackAppraisalEstimate)
        .filter(models_buyback.BuybackAppraisalEstimate.request_id == request.id)
        .first()
    )
    from datetime import datetime

    store_visit_overdue = False
    if (
        is_store_purchase(method)
        and request.store_visit_at
        and not request.store_checked_in_at
        and request.status == models_buyback.BuybackRequestStatus.awaiting_visit.value
        and datetime.utcnow() > request.store_visit_at
    ):
        store_visit_overdue = True
    return schemas_buyback.AdminBuybackRequestDetailOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        status_description=status_description(request.status),
        status_color=status_color(request.status),
        buyback_method=method,
        user_id=request.user_id,
        user_email=user.email if include_contact and user else "",
        user_name=user.name if include_contact and user else "",
        shipping_method=request.shipping_method,
        tracking_number=request.tracking_number if include_contact else None,
        customer_note=request.customer_note if include_contact else None,
        admin_note=request.admin_note if include_contact else None,
        customer_status_note=request.customer_status_note if include_contact else None,
        estimated_total=request.estimated_total,
        assessed_total=request.assessed_total,
        payout_total=request.payout_total,
        rejected_item_handling=handling,
        rejected_item_handling_label=rejected_item_handling_label(handling),
        agreed_prepaid_shipping=bool(request.agreed_prepaid_shipping),
        agreed_cod_consequence=bool(request.agreed_cod_consequence),
        agreed_condition_rejection=bool(request.agreed_condition_rejection),
        submitted_at=request.submitted_at,
        created_at=request.created_at,
        store_visit_at=request.store_visit_at,
        store_checked_in_at=request.store_checked_in_at,
        assessment_started_at=request.assessment_started_at,
        assessment_presented_at=request.assessment_presented_at,
        assessment_result_version=request.assessment_result_version or 0,
        latest_appraisal_estimate=serialize_appraisal_estimate(estimate_row),
        is_store_purchase=is_store_purchase(method),
        store_visit_overdue=store_visit_overdue,
        items=[serialize_request_item(item, request) for item in (request.items or [])],
        status_history=history,
        allowed_next_statuses=next_statuses,
        allowed_next_status_labels=[
            {"code": code, "label": STATUS_LABELS.get(code, code), "description": STATUS_DESCRIPTIONS.get(code, "")}
            for code in next_statuses
        ],
        payout_account=schemas_buyback.AdminPayoutAccountOut(**payout_account)
        if payout_account
        else None,
        ready_for_payout=bool(payout_ctx.get("ready_for_payout")),
        payout_email_sent=bool(payout_ctx.get("payout_email_sent")),
        paid_at=payout_ctx.get("paid_at"),
        payout_scheduled_at=payout_ctx.get("payout_scheduled_at"),
        payout_transfer_status=payout_ctx.get("payout_transfer_status"),
        payout_transfer_status_label=payout_ctx.get("payout_transfer_status_label"),
        identity_status=payout_ctx.get("identity_status"),
        identity_status_label=payout_ctx.get("identity_status_label"),
        identity_approved_at=payout_ctx.get("identity_approved_at") if include_contact else None,
        assessment_approved_at=payout_ctx.get("assessment_approved_at") if include_contact else None,
        requires_guardian_consent=bool(payout_ctx.get("requires_guardian_consent")),
        guardian_status=payout_ctx.get("guardian_status") if include_contact else None,
        guardian_status_label=payout_ctx.get("guardian_status_label") if include_contact else None,
        guardian_ready=bool(payout_ctx.get("guardian_ready")),
        rejection_reason_options=rejection_reason_options(),
    )


@router.get("/requests", response_model=list[schemas_buyback.AdminBuybackRequestListOut])
def list_requests(
    status: Optional[str] = Query(None),
    buyback_method: Optional[str] = Query(None),
    payout_transfer_status: Optional[str] = Query(None),
    identity_not_approved: bool = Query(False),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.request.read")),
):
    from datetime import datetime

    include_contact = can_view_kyc(ctx) or can_view_payout_queue(ctx)
    parsed_from = None
    parsed_to = None
    if date_from:
        try:
            parsed_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from の形式が不正です")
    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to の形式が不正です")

    rows = list_admin_requests(
        db,
        status=status,
        buyback_method=buyback_method,
        payout_transfer_status=payout_transfer_status,
        identity_not_approved=identity_not_approved,
        date_from=parsed_from,
        date_to=parsed_to,
        q=q,
        allow_pii_search=include_contact,
    )
    users = _user_map(db, {row.user_id for row in rows}) if include_contact else {}
    user_ids = {row.user_id for row in rows}
    identity_map: dict[int, models_buyback.IdentityVerification] = {}
    if user_ids:
        identity_rows = (
            db.query(models_buyback.IdentityVerification)
            .filter(models_buyback.IdentityVerification.user_id.in_(user_ids))
            .order_by(models_buyback.IdentityVerification.id.desc())
            .all()
        )
        for identity_row in identity_rows:
            if identity_row.user_id not in identity_map:
                identity_map[identity_row.user_id] = identity_row
    result = [
        _request_list_out(
            row,
            users.get(row.user_id),
            include_pii=include_contact,
            identity_row=identity_map.get(row.user_id),
        )
        for row in rows
    ]
    _audit_access(
        db,
        ctx,
        action="buyback_request_list_viewed",
        entity_type="buyback_request_list",
        includes_pii=include_contact,
    )
    return result


@router.get("/requests/{request_id}", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.request.read")),
):
    request = get_admin_request(db, request_id)
    include_contact = can_view_kyc(ctx) or can_view_payout_queue(ctx)
    user = (
        db.query(models.User).filter(models.User.id == request.user_id).first()
        if include_contact
        else None
    )
    result = _request_detail_out(request, user, db, ctx=ctx)
    _audit_access(
        db,
        ctx,
        action="buyback_request_detail_viewed",
        entity_type="buyback_request",
        entity_id=request.id,
        includes_pii=include_contact or can_view_bank_account(ctx),
    )
    return result


@router.post("/requests/{request_id}/complete-payout", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def complete_payout_route(
    request_id: int,
    body: schemas_buyback.AdminCompletePayoutIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("payout.complete")),
):
    complete_request_payout(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        payout_total=body.payout_total,
        admin_note=body.admin_note,
        send_email=body.send_email,
        force_email=body.force_email,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post("/requests/{request_id}/schedule-payout", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def schedule_payout_route(
    request_id: int,
    body: schemas_buyback.AdminSchedulePayoutIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("payout.complete")),
):
    schedule_request_payout(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        payout_scheduled_at=body.payout_scheduled_at,
        admin_note=body.admin_note,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


def _serialize_catalog_product(
    product: models_buyback.BuybackProduct,
) -> schemas_buyback.AdminBuybackCatalogProductOut:
    prices = sorted(
        product.prices,
        key=lambda row: (row.condition_code.casefold(), row.id),
    )
    return schemas_buyback.AdminBuybackCatalogProductOut(
        id=product.id,
        name=product.name,
        category=product.category,
        card_number=product.card_number,
        rarity=product.rarity,
        pack_name=product.pack_name,
        image_url=product.image_url,
        notes=product.notes,
        promo_badge_text=product.promo_badge_text,
        promo_badge_bg=product.promo_badge_bg,
        promo_badge_fg=product.promo_badge_fg,
        promo_badge_starts_at=product.promo_badge_starts_at,
        promo_badge_ends_at=product.promo_badge_ends_at,
        is_active=product.is_active,
        sort_order=product.sort_order,
        prices=[
            schemas_buyback.AdminBuybackCatalogPriceOut.model_validate(price)
            for price in prices
        ],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _reload_catalog_product(db: Session, product_id: int) -> models_buyback.BuybackProduct:
    product = (
        db.query(models_buyback.BuybackProduct)
        .options(selectinload(models_buyback.BuybackProduct.prices))
        .filter(models_buyback.BuybackProduct.id == product_id)
        .first()
    )
    if product is None:
        raise CatalogNotFoundError
    return product


def _handle_catalog_errors(exc: Exception) -> None:
    if isinstance(exc, CatalogConflictError):
        raise HTTPException(
            status_code=409,
            detail="同じ条件の買取カードが既に登録されています",
        ) from exc
    if isinstance(exc, CatalogNotFoundError):
        raise HTTPException(status_code=404, detail="買取カードが見つかりません") from exc
    if isinstance(exc, CatalogValidationError):
        raise HTTPException(status_code=400, detail="入力内容が不正です") from exc
    if isinstance(exc, CatalogPersistenceError):
        raise HTTPException(
            status_code=500,
            detail="買取カードの保存に失敗しました",
        ) from exc
    raise exc


@router.get(
    "/catalog/products",
    response_model=list[schemas_buyback.AdminBuybackCatalogProductOut],
)
def list_catalog_products(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.catalog.read")),
):
    del ctx
    products = buyback_catalog.list_products(db, include_inactive=include_inactive)
    return [_serialize_catalog_product(product) for product in products]


@router.post(
    "/catalog/products",
    response_model=schemas_buyback.AdminBuybackCatalogProductOut,
    status_code=201,
)
def create_catalog_product(
    body: schemas_buyback.AdminBuybackCatalogProductIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.catalog.write")),
):
    try:
        product = buyback_catalog.create_product(
            db,
            body=body,
            actor_user_id=ctx.user.id,
        )
        db.commit()
        product = _reload_catalog_product(db, product.id)
    except (
        CatalogConflictError,
        CatalogNotFoundError,
        CatalogValidationError,
        CatalogPersistenceError,
    ) as exc:
        _handle_catalog_errors(exc)
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="buyback_catalog_create",
        entity_type="buyback_catalog",
        entity_id=product.id,
        details={"failure_reason": None},
    )
    db.commit()
    return _serialize_catalog_product(product)


@router.put(
    "/catalog/products/{product_id}",
    response_model=schemas_buyback.AdminBuybackCatalogProductOut,
)
def update_catalog_product(
    product_id: int,
    body: schemas_buyback.AdminBuybackCatalogProductIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.catalog.write")),
):
    try:
        buyback_catalog.update_product(
            db,
            product_id=product_id,
            body=body,
            actor_user_id=ctx.user.id,
        )
        db.commit()
        product = _reload_catalog_product(db, product_id)
    except (
        CatalogConflictError,
        CatalogNotFoundError,
        CatalogValidationError,
        CatalogPersistenceError,
    ) as exc:
        _handle_catalog_errors(exc)
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="buyback_catalog_update",
        entity_type="buyback_catalog",
        entity_id=product.id,
        details={"failure_reason": None},
    )
    db.commit()
    return _serialize_catalog_product(product)


@router.delete("/catalog/products/{product_id}", status_code=204)
def delete_catalog_product(
    product_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.catalog.write")),
):
    try:
        product = buyback_catalog.soft_delete_product(db, product_id=product_id)
        db.commit()
    except (
        CatalogConflictError,
        CatalogNotFoundError,
        CatalogValidationError,
        CatalogPersistenceError,
    ) as exc:
        _handle_catalog_errors(exc)
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="buyback_catalog_soft_delete",
        entity_type="buyback_catalog",
        entity_id=product.id,
        details={"failure_reason": None},
    )
    db.commit()
    return None


@router.post("/import-firestore", response_model=schemas_buyback.AdminFirestoreImportOut)
def import_firestore_route(
    body: schemas_buyback.AdminFirestoreImportIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.catalog.import")),
):
    payload = {"items": body.items, "images": body.images}
    result = import_firestore_buylist_export(db, payload, dry_run=body.dry_run)
    validation = validate_import_counts(db, payload) if not body.dry_run else {}
    response = schemas_buyback.AdminFirestoreImportOut(
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        price_rows_upserted=result.price_rows_upserted,
        image_failures=result.image_failures,
        errors=result.errors,
        dry_run=body.dry_run,
        validation=validation,
    )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="buyback_catalog_import",
        entity_type="buyback_catalog",
        entity_id=None,
        details={
            "dry_run": body.dry_run,
            "created": result.created,
            "updated": result.updated,
            "failure_reason": None,
        },
    )
    db.commit()
    return response


@router.patch("/requests/{request_id}", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def patch_request(
    request: Request,
    request_id: int,
    body: schemas_buyback.AdminBuybackRequestUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    assessment_statuses = {
        models_buyback.BuybackRequestStatus.assessing.value,
        models_buyback.BuybackRequestStatus.assessed.value,
    }
    permission = (
        "buyback.assessment.write"
        if body.status in assessment_statuses
        else "buyback.request.status.write"
    )
    _enforce_permission(db, ctx, permission, request=request)
    update_request_status(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        new_status=body.status,
        admin_note=body.admin_note,
        customer_status_note=body.customer_status_note,
        tracking_number=body.tracking_number,
        assessed_total=body.assessed_total,
        payout_total=body.payout_total,
        send_email=body.send_email,
        force_email=body.force_email,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post("/requests/{request_id}/resend-email")
def resend_request_email(
    request_id: int,
    body: schemas_buyback.AdminBuybackResendEmailIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    _enforce_permission(db, ctx, "buyback.request.status.write")
    from services.buyback_admin import get_admin_request
    from services.buyback_emails import send_buyback_event_email

    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    ok, err = send_buyback_event_email(
        db,
        request,
        user,
        body.event_key,
        force=body.force,
        send_email=True,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=err or "メール送信に失敗しました")
    return {"message": "メールを再送しました", "event_key": body.event_key}


@router.patch(
    "/requests/{request_id}/items",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def patch_request_items(
    request_id: int,
    body: schemas_buyback.AdminBuybackRequestItemsUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.assessment.write")),
):
    update_request_items(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        item_updates=[item.model_dump(exclude_unset=True) for item in body.items],
        recalculate_assessed_total=body.recalculate_assessed_total,
        apply_handling_policy=body.apply_handling_policy,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post(
    "/requests/{request_id}/store/check-in",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def store_check_in(
    request_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.assessment.write")),
):
    check_in_store_visit(db, request_id=request_id, admin_user=ctx.user)
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post(
    "/requests/{request_id}/store/start-assessment",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def store_start_assessment(
    request_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.assessment.write")),
):
    start_store_assessment(db, request_id=request_id, admin_user=ctx.user)
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post(
    "/requests/{request_id}/store/appraisal-estimate",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def store_appraisal_estimate(
    request_id: int,
    body: schemas_buyback.AdminAppraisalEstimateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.assessment.write")),
):
    row = send_appraisal_estimate(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        estimated_minutes=body.estimated_minutes,
        message=body.message,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    out = _request_detail_out(request, user, db, ctx=ctx)
    warning = getattr(row, "_notification_warning", None)
    if warning:
        note = out.customer_status_note or ""
        out.customer_status_note = (note + f"\n[通知警告] {warning}").strip()
    return out


@router.patch(
    "/requests/{request_id}/store/visit-at",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def store_update_visit_at(
    request_id: int,
    body: schemas_buyback.AdminStoreVisitUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.assessment.write")),
):
    update_store_visit_at(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        store_visit_at=body.store_visit_at,
        reason=body.reason,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post(
    "/requests/{request_id}/present-assessment",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def present_assessment(
    request_id: int,
    body: schemas_buyback.AdminPresentAssessmentIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.assessment.write")),
):
    present_assessment_to_customer(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        customer_status_note=body.customer_status_note,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post(
    "/requests/{request_id}/store/complete-payment",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def store_complete_payment(
    request_id: int,
    body: schemas_buyback.AdminStorePaymentIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("payout.complete")),
):
    complete_store_payment(
        db,
        request_id=request_id,
        admin_user=ctx.user,
        payment_method=body.payment_method,
        payment_amount=body.payment_amount,
        payment_note=body.payment_note,
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


@router.post(
    "/requests/{request_id}/store/complete-transaction",
    response_model=schemas_buyback.AdminBuybackRequestDetailOut,
)
def store_complete_transaction(
    request_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.request.status.write")),
):
    complete_store_transaction(db, request_id=request_id, admin_user=ctx.user)
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)
