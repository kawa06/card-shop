"""Buyback API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
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
from services.buyback_emails import STATUS_LABELS
from services.buyback_compliance import (
    GUARDIAN_STATUS_LABELS,
    IDENTITY_STATUS_LABELS,
    get_compliance_status,
)
from services.buyback_guardian import (
    get_latest_guardian_consent,
    preview_guardian_consent_by_token,
    request_guardian_consent,
    sign_guardian_consent,
)
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
from services.buyback_requests import get_user_request, list_user_requests, submit_request_from_cart
from services.user_linking import LinkResult, resolve_clerk_user
import models
import models_buyback
import schemas_buyback

router = APIRouter(prefix="/api/buyback", tags=["buyback"])


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
    products_source = "postgresql" if migrated_count else "postgresql+firestore_fallback"
    return schemas_buyback.BuybackHealthOut(status="ok", products_source=products_source)


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
    for product in products:
        result.append(
            schemas_buyback.BuybackProductOut(
                id=product.id,
                firestore_item_id=product.firestore_item_id,
                name=product.name,
                category=product.category,
                image_url=product.image_url,
                notes=product.notes,
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


def _serialize_request_summary(
    request: models_buyback.BuybackRequest,
) -> schemas_buyback.BuybackRequestSummaryOut:
    item_count = sum(item.quantity for item in request.items)
    return schemas_buyback.BuybackRequestSummaryOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        estimated_total=request.estimated_total,
        item_count=item_count,
        submitted_at=request.submitted_at,
        created_at=request.created_at,
    )


def _serialize_request_detail(
    request: models_buyback.BuybackRequest,
) -> schemas_buyback.BuybackRequestDetailOut:
    return schemas_buyback.BuybackRequestDetailOut(
        id=request.id,
        request_number=request.request_number,
        status=request.status,
        status_label=STATUS_LABELS.get(request.status, request.status),
        shipping_method=request.shipping_method,
        tracking_number=request.tracking_number,
        customer_note=request.customer_note,
        estimated_total=request.estimated_total,
        assessed_total=request.assessed_total,
        payout_total=request.payout_total,
        submitted_at=request.submitted_at,
        created_at=request.created_at,
        items=[
            schemas_buyback.BuybackRequestItemOut.model_validate(item)
            for item in request.items
        ],
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
    )
    return _serialize_request_detail(request)


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
    return _serialize_request_detail(request)


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
        signed_at=row.signed_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


@router.get("/compliance", response_model=schemas_buyback.ComplianceStatusOut)
def buyback_compliance(
    requires_guardian: bool = Query(False),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_compliance_status(
        db, user_id=current_user.id, requires_guardian=requires_guardian
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
