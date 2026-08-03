"""Buyback API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from datetime import date
from sqlalchemy.orm import Session, joinedload

from auth import create_access_token, get_current_user
from clerk_auth import clerk_identity_from_token
from database import get_db
from services.buyback_cart import (
    add_cart_item,
    clear_cart,
    remove_cart_item,
    update_cart_item_quantity,
)
from services.buyback_request_status import (
    STATUS_LABELS,
    build_progress_payload,
    status_color,
    status_description,
)
from services.buyback_application_form import BUYBACK_METHOD_LABELS
from services.buyback_serializers import (
    rejected_item_handling_label,
    serialize_request_item,
)
from services.buyback_compliance import (
    GUARDIAN_STATUS_LABELS,
    IDENTITY_STATUS_LABELS,
    get_compliance_status,
)
from services.buyback_assessment_response import submit_assessment_response
from services.buyback_guardian import (
    get_latest_guardian_consent,
    preview_guardian_consent_by_token,
    request_guardian_consent,
    set_guardian_document_type,
    sign_guardian_consent,
    upload_guardian_consent_document,
)
from services.buyback_profile import update_user_birth_date
from services.buyback_identity import (
    get_or_create_identity,
    submit_identity_verification,
    upload_identity_document,
)
from services.buyback_payout_accounts import (
    create_payout_account,
    delete_payout_account,
    list_payout_accounts_masked,
    set_default_payout_account,
)
from services.buyback_application_form import build_application_form
from services.barcode_render import render_code128_svg
from services.buyback_barcodes import get_active_barcode_for_entity
from services.buyback_logistics_logs import write_package_print_log
from services.buyback_requests import get_user_request, list_user_requests, submit_request_from_cart
from services.buyback_channel import (
    get_or_create_channel_settings,
    list_active_banners,
    list_available_slots,
    resolve_allowed_methods,
    resolve_channel_mode,
    resolve_active_product_promo_badge,
    _banner_is_active,
    now_utc_naive,
)
from services.buyback_shop_settings import get_or_create_shop_settings, serialize_shop_settings
from services.user_linking import LinkResult, resolve_clerk_user
import models
import models_buyback
import schemas_buyback

router = APIRouter(prefix="/api/buyback", tags=["buyback"])

INBOUND_STATUS_LABELS = {
    "awaiting_shipment": "発送待ち",
    "customer_shipped": "客から発送済み",
    "arrived": "荷物到着",
    "received": "受付済み",
}


def _load_inbound_for_request(
    db: Session, request_id: int
) -> models_buyback.BuybackInboundShipment | None:
    return (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request_id)
        .first()
    )


def _require_clerk_bearer(request: Request) -> str:
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerkセッショントークンが必要です",
        )
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerkセッショントークンが必要です",
        )
    return token


def _serialize_cart(cart: models_buyback.BuybackCart | None) -> schemas_buyback.BuybackCartOut:
    if not cart or not cart.items:
        return schemas_buyback.BuybackCartOut()

    items_out: list[schemas_buyback.BuybackCartItemOut] = []
    total = 0
    count = 0
    for item in cart.items:
        line_total = item.unit_price_snapshot * item.quantity
        total += line_total
        count += item.quantity
        product = item.product
        items_out.append(
            schemas_buyback.BuybackCartItemOut(
                id=item.id,
                product_id=item.product_id,
                firestore_item_id=product.firestore_item_id if product else None,
                condition_code=item.condition_code,
                quantity=item.quantity,
                unit_price_snapshot=item.unit_price_snapshot,
                product_name=product.name if product else None,
                category=product.category if product else None,
            )
        )

    return schemas_buyback.BuybackCartOut(
        items=items_out,
        item_count=count,
        estimated_total=total,
    )


def _load_user_cart(db: Session, user_id: int) -> models_buyback.BuybackCart | None:
    return (
        db.query(models_buyback.BuybackCart)
        .filter(models_buyback.BuybackCart.user_id == user_id)
        .options(
            joinedload(models_buyback.BuybackCart.items).joinedload(
                models_buyback.BuybackCartItem.product
            )
        )
        .first()
    )


def _serialize_cart_item(item: models_buyback.BuybackCartItem) -> schemas_buyback.BuybackCartItemOut:
    product = item.product
    return schemas_buyback.BuybackCartItemOut(
        id=item.id,
        product_id=item.product_id,
        firestore_item_id=product.firestore_item_id if product else None,
        condition_code=item.condition_code,
        quantity=item.quantity,
        unit_price_snapshot=item.unit_price_snapshot,
        product_name=product.name if product else None,
        category=product.category if product else None,
    )


@router.get("/health", response_model=schemas_buyback.BuybackHealthOut)
def buyback_health(db: Session = Depends(get_db)):
    migrated_count = (
        db.query(models_buyback.BuybackProduct)
        .filter(models_buyback.BuybackProduct.firestore_item_id.isnot(None))
        .count()
    )
    cutover_complete = migrated_count > 0
    products_source = "postgresql" if cutover_complete else "postgresql+firestore_fallback"
    return schemas_buyback.BuybackHealthOut(
        status="ok",
        products_source=products_source,
        cutover_complete=cutover_complete,
    )


def _serialize_public_banner(banner: models_buyback.BuybackPromoBanner) -> schemas_buyback.BuybackPromoBannerOut:
    now = now_utc_naive()
    return schemas_buyback.BuybackPromoBannerOut(
        id=banner.id,
        title=banner.title,
        description=banner.description,
        target_channel=banner.target_channel,
        starts_at=banner.starts_at,
        ends_at=banner.ends_at,
        background_color=banner.background_color,
        text_color=banner.text_color,
        sort_order=banner.sort_order,
        is_visible=banner.is_visible,
        is_active=_banner_is_active(banner, now),
    )


@router.get("/channel/config", response_model=schemas_buyback.BuybackPublicChannelConfigOut)
def get_public_channel_config(
    channel: str | None = Query(None, description="store or mail filter for banners"),
    db: Session = Depends(get_db),
):
    settings = get_or_create_channel_settings(db)
    banners = list_active_banners(db, channel=channel)
    return schemas_buyback.BuybackPublicChannelConfigOut(
        channel_mode=resolve_channel_mode(settings),
        allowed_methods=resolve_allowed_methods(settings),
        store_enabled=settings.store_enabled,
        mail_enabled=settings.mail_enabled,
        slot_interval_minutes=settings.slot_interval_minutes,
        banners=[_serialize_public_banner(b) for b in banners],
    )


@router.get("/channel/slots", response_model=schemas_buyback.BuybackStoreSlotsOut)
def get_store_slots(
    target_date: date = Query(..., alias="date"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slots = list_available_slots(db, target_date=target_date)
    formatted = []
    for slot in slots:
        formatted.append(
            schemas_buyback.BuybackStoreSlotOut(
                visit_at=slot,
                label=slot.strftime("%H:%M"),
            )
        )
    return schemas_buyback.BuybackStoreSlotsOut(date=target_date, slots=formatted)


@router.post("/auth/sync", response_model=schemas_buyback.BuybackSyncResponse)
def buyback_auth_sync(
    request: Request,
    db: Session = Depends(get_db),
):
    """Buylist: Clerk JWT → link user → backend JWT."""
    token = _require_clerk_bearer(request)
    identity = clerk_identity_from_token(token)
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerkセッションが無効です",
        )

    clerk_user_id, email, name = identity
    outcome = resolve_clerk_user(
        db,
        clerk_user_id=clerk_user_id,
        email=email,
        name=name,
    )
    if outcome.result in (LinkResult.email_ambiguous, LinkResult.clerk_id_conflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=outcome.message or "アカウントの紐付けに失敗しました",
        )
    if not outcome.user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="アカウントの紐付けに失敗しました",
        )

    access_token = create_access_token({"sub": str(outcome.user.id)})
    return schemas_buyback.BuybackSyncResponse(
        access_token=access_token,
        user=outcome.user,
        link_result=outcome.result.value,
    )


@router.get("/me", response_model=schemas_buyback.BuybackUserOut)
def buyback_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=schemas_buyback.BuybackUserOut)
def update_buyback_profile(
    payload: schemas_buyback.BuybackProfileUpdateIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = update_user_birth_date(db, user=current_user, birth_date=payload.birth_date)
    return user


@router.post(
    "/requests/{request_id}/assessment-response",
    response_model=schemas_buyback.BuybackRequestDetailOut,
)
def submit_buyback_assessment_response(
    request_id: int,
    payload: schemas_buyback.AssessmentResponseIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = submit_assessment_response(
        db,
        user=current_user,
        request_id=request_id,
        decisions=[row.model_dump() for row in payload.decisions],
    )
    return _serialize_request_detail(db, request, user=current_user)


@router.get("/shop", response_model=schemas_buyback.BuybackShopSettingsOut)
def get_public_shop_settings(db: Session = Depends(get_db)):
    settings = get_or_create_shop_settings(db)
    return schemas_buyback.BuybackShopSettingsOut(**serialize_shop_settings(settings))


@router.get("/products", response_model=list[schemas_buyback.BuybackProductOut])
def list_buyback_products(db: Session = Depends(get_db)):
    products = (
        db.query(models_buyback.BuybackProduct)
        .filter(models_buyback.BuybackProduct.is_active.is_(True))
        .options(joinedload(models_buyback.BuybackProduct.prices))
        .order_by(models_buyback.BuybackProduct.sort_order.asc(), models_buyback.BuybackProduct.id.asc())
        .all()
    )
    result: list[schemas_buyback.BuybackProductOut] = []
    now = now_utc_naive()
    for product in products:
        promo = resolve_active_product_promo_badge(product, now)
        result.append(
            schemas_buyback.BuybackProductOut(
                id=product.id,
                firestore_item_id=product.firestore_item_id,
                name=product.name,
                category=product.category,
                image_url=product.image_url,
                notes=product.notes,
                promo_badge_text=promo["text"] if promo else None,
                promo_badge_bg=promo["background_color"] if promo else None,
                promo_badge_fg=promo["text_color"] if promo else None,
                prices=[
                    schemas_buyback.BuybackProductPriceOut(
                        condition_code=price.condition_code,
                        price_normal=price.price_normal,
                        price_high=price.price_high,
                        purchase_limit=price.purchase_limit,
                    )
                    for price in product.prices
                ],
            )
        )
    return result


@router.get("/cart", response_model=schemas_buyback.BuybackCartOut)
def get_buyback_cart(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = _load_user_cart(db, current_user.id)
    return _serialize_cart(cart)


@router.post("/cart/items", response_model=schemas_buyback.BuybackCartItemOut, status_code=status.HTTP_201_CREATED)
def create_buyback_cart_item(
    payload: schemas_buyback.BuybackCartItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = add_cart_item(
        db,
        user_id=current_user.id,
        firestore_item_id=payload.firestore_item_id,
        product_name=payload.product_name,
        category=payload.category,
        condition_code=payload.condition_code,
        unit_price=payload.unit_price,
        quantity=payload.quantity,
        image_url=payload.image_url,
    )
    db.refresh(item, attribute_names=["product"])
    return _serialize_cart_item(item)


@router.put("/cart/items/{item_id}", response_model=schemas_buyback.BuybackCartItemOut)
def update_buyback_cart_item(
    item_id: int,
    payload: schemas_buyback.BuybackCartItemUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = update_cart_item_quantity(
        db,
        user_id=current_user.id,
        item_id=item_id,
        quantity=payload.quantity,
    )
    db.refresh(item, attribute_names=["product"])
    return _serialize_cart_item(item)


@router.delete("/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_buyback_cart_item(
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    remove_cart_item(db, user_id=current_user.id, item_id=item_id)
    return None


def _buyback_method_label(method: str | None) -> str | None:
    if not method:
        return None
    return BUYBACK_METHOD_LABELS.get(method, method)


def _serialize_request_summary(
    request: models_buyback.BuybackRequest,
) -> schemas_buyback.BuybackRequestSummaryOut:
    item_count = sum(item.quantity for item in request.items)
    return schemas_buyback.BuybackRequestSummaryOut(
        id=request.id,
        request_number=request.request_number,
        public_buyback_code=request.public_buyback_code,
        inbound_mgmt_id=request.inbound_mgmt_id,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        status_color=status_color(request.status),
        buyback_method=request.buyback_method,
        buyback_method_label=_buyback_method_label(request.buyback_method),
        estimated_total=request.estimated_total,
        item_count=item_count,
        submitted_at=request.submitted_at,
        created_at=request.created_at,
    )


def _serialize_request_detail(
    db: Session,
    request: models_buyback.BuybackRequest,
    *,
    user: models.User | None = None,
) -> schemas_buyback.BuybackRequestDetailOut:
    handling = request.rejected_item_handling
    inbound = _load_inbound_for_request(db, request.id)
    inbound_status = inbound.status if inbound else None
    return schemas_buyback.BuybackRequestDetailOut(
        id=request.id,
        request_number=request.request_number,
        public_buyback_code=request.public_buyback_code,
        inbound_mgmt_id=request.inbound_mgmt_id,
        public_member_id=user.public_member_id if user else None,
        inbound_status=inbound_status,
        inbound_status_label=INBOUND_STATUS_LABELS.get(inbound_status, inbound_status)
        if inbound_status
        else None,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        status_description=status_description(request.status),
        status_color=status_color(request.status),
        customer_status_note=request.customer_status_note,
        progress_steps=[
            schemas_buyback.BuybackProgressStepOut(**step)
            for step in build_progress_payload(request.status, request.buyback_method)
        ],
        shipping_method=request.shipping_method,
        tracking_number=request.tracking_number,
        customer_note=request.customer_note,
        customer_planned_ship_date=request.customer_planned_ship_date,
        estimated_total=request.estimated_total,
        assessed_total=request.assessed_total,
        payout_total=request.payout_total,
        rejected_item_handling=handling,
        rejected_item_handling_label=rejected_item_handling_label(handling),
        buyback_method=request.buyback_method,
        buyback_method_label=_buyback_method_label(request.buyback_method),
        store_visit_at=request.store_visit_at,
        submitted_at=request.submitted_at,
        application_form_issued_at=request.application_form_issued_at,
        assessed_at=request.assessed_at,
        created_at=request.created_at,
        items=[serialize_request_item(item) for item in request.items],
    )


@router.post(
    "/requests",
    response_model=schemas_buyback.BuybackRequestDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def create_buyback_request(
    payload: schemas_buyback.BuybackRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = submit_request_from_cart(
        db,
        user=current_user,
        customer_note=payload.customer_note,
        shipping_method=payload.shipping_method,
        customer_planned_ship_date=payload.customer_planned_ship_date,
        rejected_item_handling=payload.rejected_item_handling,
        agreed_prepaid_shipping=payload.agreed_prepaid_shipping,
        agreed_cod_consequence=payload.agreed_cod_consequence,
        agreed_condition_rejection=payload.agreed_condition_rejection,
        buyback_method=payload.buyback_method,
        store_visit_at=payload.store_visit_at,
    )
    return _serialize_request_detail(db, request, user=current_user)


@router.get("/requests", response_model=list[schemas_buyback.BuybackRequestSummaryOut])
def list_buyback_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requests = list_user_requests(db, user_id=current_user.id)
    return [_serialize_request_summary(r) for r in requests]


@router.get("/requests/{request_id}", response_model=schemas_buyback.BuybackRequestDetailOut)
def get_buyback_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = get_user_request(db, user_id=current_user.id, request_id=request_id)
    return _serialize_request_detail(db, request, user=current_user)


@router.get(
    "/requests/{request_id}/application-form",
    response_model=schemas_buyback.BuybackApplicationFormOut,
)
def get_buyback_application_form(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = build_application_form(
        db,
        user=current_user,
        request_id=request_id,
        mark_issued=False,
    )
    return schemas_buyback.BuybackApplicationFormOut(**payload)


@router.get("/requests/{request_id}/application-form/barcode.svg")
def get_buyback_application_barcode_svg(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = get_user_request(db, user_id=current_user.id, request_id=request_id)
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .first()
    )
    if not inbound:
        raise HTTPException(status_code=404, detail="バーコードが見つかりません")
    barcode = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
    )
    if not barcode:
        raise HTTPException(status_code=404, detail="バーコードが見つかりません")
    write_package_print_log(
        db,
        actor_user_id=current_user.id,
        print_type="application_barcode_render",
        entity_type="buyback_request",
        entity_id=request.id,
    )
    db.commit()
    return Response(
        content=render_code128_svg(barcode.scan_token),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store, private"},
    )


@router.post(
    "/requests/{request_id}/application-form/issue",
    response_model=schemas_buyback.BuybackApplicationFormOut,
)
def issue_buyback_application_form(
    request_id: int,
    payload: schemas_buyback.BuybackApplicationFormIssueIn | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    body = payload or schemas_buyback.BuybackApplicationFormIssueIn()
    data = build_application_form(
        db,
        user=current_user,
        request_id=request_id,
        mark_issued=True,
        print_type=body.print_type or "application_a4",
        device_info=body.device_info,
    )
    return schemas_buyback.BuybackApplicationFormOut(**data)


def _serialize_identity(row: models_buyback.IdentityVerification) -> schemas_buyback.IdentityVerificationOut:
    return schemas_buyback.IdentityVerificationOut(
        status=row.status,
        status_label=IDENTITY_STATUS_LABELS.get(row.status, row.status),
        document_type=row.document_type,
        has_front=bool(row.storage_key_front),
        has_back=bool(row.storage_key_back),
        rejection_reason=row.rejection_reason,
        submitted_at=row.submitted_at,
        updated_at=row.updated_at,
    )


def _serialize_guardian(row: models_buyback.GuardianConsent | None) -> schemas_buyback.GuardianConsentOut:
    if not row:
        return schemas_buyback.GuardianConsentOut(
            status="not_requested",
            status_label="未申請",
        )
    return schemas_buyback.GuardianConsentOut(
        status=row.status,
        status_label=GUARDIAN_STATUS_LABELS.get(row.status, row.status),
        guardian_name=row.guardian_name,
        guardian_email=row.guardian_email,
        document_type=row.document_type,
        has_front=bool(row.storage_key_front),
        has_back=bool(row.storage_key_back),
        signed_at=row.signed_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


@router.get("/compliance", response_model=schemas_buyback.ComplianceStatusOut)
def buyback_compliance(
    requires_guardian: bool | None = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_compliance_status(
        db,
        user_id=current_user.id,
        user=current_user,
        requires_guardian=requires_guardian,
    )


@router.get("/identity", response_model=schemas_buyback.IdentityVerificationOut)
def get_buyback_identity(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_identity(get_or_create_identity(db, current_user.id))


@router.post("/identity/documents", response_model=schemas_buyback.IdentityVerificationOut)
async def upload_buyback_identity_document(
    side: str = Query(..., pattern="^(front|back)$"),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()
    row = upload_identity_document(
        db,
        user_id=current_user.id,
        side=side,
        content_type=file.content_type,
        data=data,
    )
    return _serialize_identity(row)


@router.post("/identity/submit", response_model=schemas_buyback.IdentityVerificationOut)
def submit_buyback_identity(
    payload: schemas_buyback.IdentitySubmitIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = submit_identity_verification(
        db,
        user_id=current_user.id,
        document_type=payload.document_type,
    )
    return _serialize_identity(row)


@router.get("/guardian-consent", response_model=schemas_buyback.GuardianConsentOut)
def get_buyback_guardian_consent(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_guardian(get_latest_guardian_consent(db, current_user.id))


@router.post("/guardian-consent/request", response_model=schemas_buyback.GuardianConsentOut)
def create_buyback_guardian_consent_request(
    payload: schemas_buyback.GuardianConsentRequestIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consent, _token = request_guardian_consent(
        db,
        user=current_user,
        guardian_name=payload.guardian_name,
        guardian_email=payload.guardian_email,
    )
    return _serialize_guardian(consent)


@router.post("/guardian-consent/documents", response_model=schemas_buyback.GuardianConsentOut)
async def upload_buyback_guardian_document(
    side: str = Query(..., pattern="^(front|back)$"),
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()
    row = upload_guardian_consent_document(
        db,
        user_id=current_user.id,
        side=side,
        content_type=file.content_type,
        data=data,
    )
    return _serialize_guardian(row)


@router.post("/guardian-consent/document-type", response_model=schemas_buyback.GuardianConsentOut)
def set_buyback_guardian_document_type(
    payload: schemas_buyback.GuardianDocumentTypeIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = set_guardian_document_type(
        db,
        user_id=current_user.id,
        document_type=payload.document_type,
    )
    return _serialize_guardian(row)


@router.get("/guardian-consent/preview", response_model=schemas_buyback.GuardianConsentPreviewOut)
def preview_buyback_guardian_consent(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    consent = preview_guardian_consent_by_token(db, token=token)
    return schemas_buyback.GuardianConsentPreviewOut(
        guardian_name=consent.guardian_name,
        status=consent.status,
        status_label=GUARDIAN_STATUS_LABELS.get(consent.status, consent.status),
        expires_at=consent.expires_at,
    )


@router.post("/guardian-consent/sign", response_model=schemas_buyback.GuardianConsentOut)
def sign_buyback_guardian_consent(
    payload: schemas_buyback.GuardianConsentSignIn,
    db: Session = Depends(get_db),
):
    consent = sign_guardian_consent(db, token=payload.token)
    return _serialize_guardian(consent)


@router.get("/payout-accounts", response_model=list[schemas_buyback.PayoutAccountOut])
def get_buyback_payout_accounts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_payout_accounts_masked(db, current_user.id)


@router.post(
    "/payout-accounts",
    response_model=schemas_buyback.PayoutAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def create_buyback_payout_account(
    payload: schemas_buyback.PayoutAccountCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_payout_account(
        db,
        user_id=current_user.id,
        bank_name=payload.bank_name,
        branch_name=payload.branch_name,
        account_type=payload.account_type,
        account_number=payload.account_number,
        account_holder=payload.account_holder,
        set_default=payload.set_default,
    )


@router.put("/payout-accounts/{account_id}/default", response_model=schemas_buyback.PayoutAccountOut)
def set_buyback_default_payout_account(
    account_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return set_default_payout_account(db, user_id=current_user.id, account_id=account_id)


@router.delete("/payout-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_buyback_payout_account(
    account_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delete_payout_account(db, user_id=current_user.id, account_id=account_id)
    return None


@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
def delete_buyback_cart(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clear_cart(db, user_id=current_user.id)
    return None
