"""Admin buyback management routes (Phase 7)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

import models
import models_buyback
import schemas_buyback
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.buyback_admin import (
    DOCUMENT_TYPE_LABELS,
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
    update_request_items,
    update_request_status,
)
from services.buyback_serializers import (
    rejection_reason_options,
    rejected_item_handling_label,
    serialize_request_item,
)
from services.buyback_compliance import IDENTITY_STATUS_LABELS
from services.buyback_emails import STATUS_LABELS
from services.buyback_request_status import (
    STATUS_DESCRIPTIONS,
    allowed_next_statuses,
    status_color,
    status_description,
)
from services.buyback_kyc_storage import fetch_kyc_document
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
    _: AdminContext = Depends(_require_perm("buyback.request.read")),
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
    ctx: AdminContext = Depends(
        _require_perms("buyback.identity.read", "admin.pii.read")
    ),
):
    rows = list_identity_verifications(db, status=status, q=q)
    users = _user_map(db, {row.user_id for row in rows})
    result = [_identity_list_out(row, users.get(row.user_id)) for row in rows]
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
        _require_perms("buyback.identity.read", "admin.pii.read")
    ),
):
    row = get_identity_verification(db, verification_id)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    reviewer = None
    if row.reviewed_by_user_id:
        reviewer = (
            db.query(models.User).filter(models.User.id == row.reviewed_by_user_id).first()
        )
    base = _identity_list_out(row, user)
    result = schemas_buyback.AdminIdentityDetailOut(
        **base.model_dump(),
        rejection_reason=row.rejection_reason,
        reviewed_at=row.reviewed_at,
        reviewer_name=reviewer.name if reviewer else None,
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
    ctx: AdminContext = Depends(
        _require_perms("buyback.identity.read", "admin.pii.read")
    ),
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
        raise HTTPException(status_code=503, detail="書類画像を取得できません") from exc

    _audit_access(
        db,
        ctx,
        action="pii_identity_document_viewed",
        entity_type="identity_verification",
        entity_id=row.id,
        includes_pii=True,
    )
    return Response(content=data, media_type=content_type)


@router.post("/identity/{verification_id}/approve", response_model=schemas_buyback.AdminIdentityDetailOut)
def approve_identity_route(
    verification_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("buyback.identity.write", "admin.pii.read")
    ),
):
    row = approve_identity(db, verification_id=verification_id, admin_user=ctx.user)
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    base = _identity_list_out(row, user)
    return schemas_buyback.AdminIdentityDetailOut(**base.model_dump(), reviewed_at=row.reviewed_at)


@router.post("/identity/{verification_id}/reject", response_model=schemas_buyback.AdminIdentityDetailOut)
def reject_identity_route(
    verification_id: int,
    body: schemas_buyback.AdminIdentityRejectIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(
        _require_perms("buyback.identity.write", "admin.pii.read")
    ),
):
    row = reject_identity(
        db,
        verification_id=verification_id,
        admin_user=ctx.user,
        rejection_reason=body.rejection_reason,
    )
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    base = _identity_list_out(row, user)
    return schemas_buyback.AdminIdentityDetailOut(
        **base.model_dump(),
        rejection_reason=row.rejection_reason,
        reviewed_at=row.reviewed_at,
    )


def _request_list_out(
    request, user: models.User | None, *, include_pii: bool
) -> schemas_buyback.AdminBuybackRequestListOut:
    return schemas_buyback.AdminBuybackRequestListOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        user_id=request.user_id,
        user_email=user.email if include_pii and user else "",
        user_name=user.name if include_pii and user else "",
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
    *,
    ctx: AdminContext,
) -> schemas_buyback.AdminBuybackRequestDetailOut:
    include_pii = "admin.pii.read" in ctx.permissions
    actor_ids = {
        h.changed_by_user_id for h in (request.status_history or []) if h.changed_by_user_id
    }
    actors = {}
    if actor_ids and include_pii:
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
            changed_by_name=actors.get(h.changed_by_user_id) if include_pii else None,
            note=h.note if include_pii else None,
            created_at=h.created_at,
        )
        for h in sorted(request.status_history or [], key=lambda x: x.created_at)
    ]
    payout_ctx = get_request_payout_context(db, request) if include_pii else {}
    payout_account = payout_ctx.get("payout_account")
    next_statuses = allowed_next_statuses(request, permissions=set(ctx.permissions))
    handling = request.rejected_item_handling
    return schemas_buyback.AdminBuybackRequestDetailOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        status_description=status_description(request.status),
        status_color=status_color(request.status),
        buyback_method=request.buyback_method,
        user_id=request.user_id,
        user_email=user.email if include_pii and user else "",
        user_name=user.name if include_pii and user else "",
        shipping_method=request.shipping_method,
        tracking_number=request.tracking_number if include_pii else None,
        customer_note=request.customer_note if include_pii else None,
        admin_note=request.admin_note if include_pii else None,
        customer_status_note=request.customer_status_note if include_pii else None,
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
        items=[serialize_request_item(item) for item in (request.items or [])],
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
        rejection_reason_options=rejection_reason_options(),
    )


@router.get("/requests", response_model=list[schemas_buyback.AdminBuybackRequestListOut])
def list_requests(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.request.read")),
):
    include_pii = "admin.pii.read" in ctx.permissions
    rows = list_admin_requests(
        db,
        status=status,
        q=q,
        allow_pii_search=include_pii,
    )
    users = _user_map(db, {row.user_id for row in rows}) if include_pii else {}
    result = [
        _request_list_out(row, users.get(row.user_id), include_pii=include_pii)
        for row in rows
    ]
    _audit_access(
        db,
        ctx,
        action="buyback_request_list_viewed",
        entity_type="buyback_request_list",
        includes_pii=include_pii,
    )
    return result


@router.get("/requests/{request_id}", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.request.read")),
):
    request = get_admin_request(db, request_id)
    include_pii = "admin.pii.read" in ctx.permissions
    user = (
        db.query(models.User).filter(models.User.id == request.user_id).first()
        if include_pii
        else None
    )
    result = _request_detail_out(request, user, db, ctx=ctx)
    _audit_access(
        db,
        ctx,
        action="buyback_request_detail_viewed",
        entity_type="buyback_request",
        entity_id=request.id,
        includes_pii=include_pii,
    )
    return result


@router.post("/requests/{request_id}/complete-payout", response_model=schemas_buyback.AdminBuybackRequestDetailOut)
def complete_payout_route(
    request_id: int,
    body: schemas_buyback.AdminCompletePayoutIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.payout.complete")),
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
    )
    request = get_admin_request(db, request_id)
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    return _request_detail_out(request, user, db, ctx=ctx)


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
