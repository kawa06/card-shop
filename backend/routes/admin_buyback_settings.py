"""Admin buyback channel settings, banners, and store reservations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import models
import models_buyback
import schemas_buyback
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.buyback_channel import (
    _banner_is_active,
    _load_business_hours,
    _load_closed_dates,
    create_banner,
    delete_banner,
    get_banner,
    get_or_create_channel_settings,
    list_all_banners_admin,
    list_reservations_admin,
    load_banner_linked_product_ids,
    now_utc_naive,
    resolve_allowed_methods,
    resolve_channel_mode,
    update_banner,
    update_channel_settings,
)
from services.buyback_shop_settings import (
    get_or_create_shop_settings,
    serialize_shop_settings,
    update_shop_settings,
)
from services.buyback_logistics_logs import write_buyback_audit
from services.db_persist import PersistDep

router = APIRouter(
    prefix="/api/admin/buyback",
    tags=["admin-buyback-settings"],
    dependencies=[PersistDep],
)


def _require_perm(permission: str):
    def _dep(
        request: Request,
        ctx: AdminContext = Depends(get_current_admin_context),
        db: Session = Depends(get_db),
    ) -> AdminContext:
        try:
            require_permission(ctx, permission)
        except AdminAccessError as exc:
            write_buyback_audit(
                db,
                actor_user_id=ctx.user.id,
                action="permission_denied",
                entity_type="admin_buyback_settings",
                entity_id=request.url.path,
                details={
                    "required_permission": permission,
                    "method": request.method,
                },
            )
            db.commit()
            raise HTTPException(status_code=403, detail="権限がありません") from exc
        return ctx

    return _dep


def _serialize_settings(db: Session) -> schemas_buyback.BuybackChannelSettingsOut:
    settings = get_or_create_channel_settings(db)
    return schemas_buyback.BuybackChannelSettingsOut(
        store_enabled=settings.store_enabled,
        mail_enabled=settings.mail_enabled,
        channel_mode=resolve_channel_mode(settings),
        allowed_methods=resolve_allowed_methods(settings),
        slot_interval_minutes=settings.slot_interval_minutes,
        business_hours=_load_business_hours(settings),
        closed_dates=_load_closed_dates(settings),
        updated_at=settings.updated_at,
    )


def _serialize_shop_settings(db: Session) -> schemas_buyback.BuybackShopSettingsOut:
    settings = get_or_create_shop_settings(db)
    return schemas_buyback.BuybackShopSettingsOut(**serialize_shop_settings(settings))


def _require_catalog_perm(permission: str):
    """Catalog editors and settings admins can manage buylist shop settings."""

    def _dep(
        request: Request,
        ctx: AdminContext = Depends(get_current_admin_context),
        db: Session = Depends(get_db),
    ) -> AdminContext:
        try:
            require_permission(ctx, permission)
        except AdminAccessError:
            fallback = "buyback.settings.read" if permission.endswith(".read") else "buyback.settings.write"
            try:
                require_permission(ctx, fallback)
            except AdminAccessError as exc:
                write_buyback_audit(
                    db,
                    actor_user_id=ctx.user.id,
                    action="permission_denied",
                    entity_type="admin_buyback_shop_settings",
                    entity_id=request.url.path,
                    details={
                        "required_permission": permission,
                        "method": request.method,
                    },
                )
                db.commit()
                raise HTTPException(status_code=403, detail="権限がありません") from exc
        return ctx

    return _dep


def _serialize_banner(banner) -> schemas_buyback.BuybackPromoBannerOut:
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
        linked_product_ids=load_banner_linked_product_ids(banner),
        created_at=banner.created_at,
        updated_at=banner.updated_at,
    )


@router.get("/channel/settings", response_model=schemas_buyback.BuybackChannelSettingsOut)
def get_channel_settings(
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.settings.read")),
):
    return _serialize_settings(db)


@router.get("/shop/settings", response_model=schemas_buyback.BuybackShopSettingsOut)
def get_shop_settings_admin(
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_catalog_perm("buyback.catalog.read")),
):
    return _serialize_shop_settings(db)


@router.put("/shop/settings", response_model=schemas_buyback.BuybackShopSettingsOut)
def update_shop_settings_admin(
    payload: schemas_buyback.BuybackShopSettingsUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_catalog_perm("buyback.catalog.write")),
):
    before = _serialize_shop_settings(db)
    settings = update_shop_settings(
        db,
        name=payload.name,
        slug=payload.slug,
        notice_text=payload.notice_text,
        show_notice=payload.show_notice,
    )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="shop_settings_updated",
        entity_type="buyback_shop_settings",
        entity_id="1",
        details={
            "before": before.model_dump(mode="json"),
            "after": _serialize_shop_settings(db).model_dump(mode="json"),
        },
    )
    db.commit()
    db.refresh(settings)
    return _serialize_shop_settings(db)


@router.put("/channel/settings", response_model=schemas_buyback.BuybackChannelSettingsOut)
def update_channel_settings_endpoint(
    payload: schemas_buyback.BuybackChannelSettingsUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.settings.write")),
):
    before = _serialize_settings(db)
    settings = update_channel_settings(
        db,
        store_enabled=payload.store_enabled,
        mail_enabled=payload.mail_enabled,
        slot_interval_minutes=payload.slot_interval_minutes,
        business_hours=payload.business_hours,
        closed_dates=payload.closed_dates,
    )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="channel_settings_updated",
        entity_type="buyback_channel_settings",
        entity_id="1",
        details={
            "before": before.model_dump(mode="json"),
            "after": _serialize_settings(db).model_dump(mode="json"),
        },
    )
    db.commit()
    db.refresh(settings)
    return _serialize_settings(db)


@router.get("/banners", response_model=list[schemas_buyback.BuybackPromoBannerOut])
def list_banners_admin(
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.settings.read")),
):
    return [_serialize_banner(b) for b in list_all_banners_admin(db)]


@router.post(
    "/banners",
    response_model=schemas_buyback.BuybackPromoBannerOut,
    status_code=201,
)
def create_banner_admin(
    payload: schemas_buyback.BuybackPromoBannerCreateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.settings.write")),
):
    banner = create_banner(
        db,
        title=payload.title,
        description=payload.description,
        target_channel=payload.target_channel,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        background_color=payload.background_color,
        text_color=payload.text_color,
        sort_order=payload.sort_order,
        is_visible=payload.is_visible,
        linked_product_ids=payload.linked_product_ids,
    )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="promo_banner_created",
        entity_type="buyback_promo_banner",
        entity_id=str(banner.id),
        details={"title": banner.title, "target_channel": banner.target_channel},
    )
    db.commit()
    db.refresh(banner)
    return _serialize_banner(banner)


@router.put("/banners/{banner_id}", response_model=schemas_buyback.BuybackPromoBannerOut)
def update_banner_admin(
    banner_id: int,
    payload: schemas_buyback.BuybackPromoBannerUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.settings.write")),
):
    banner = get_banner(db, banner_id)
    before = _serialize_banner(banner)
    update_banner(
        db,
        banner,
        **payload.model_dump(exclude_unset=True),
    )
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="promo_banner_updated",
        entity_type="buyback_promo_banner",
        entity_id=str(banner.id),
        details={
            "before": before.model_dump(mode="json"),
            "after": _serialize_banner(banner).model_dump(mode="json"),
        },
    )
    db.commit()
    db.refresh(banner)
    return _serialize_banner(banner)


@router.delete("/banners/{banner_id}", status_code=204)
def delete_banner_admin(
    banner_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.settings.write")),
):
    banner = get_banner(db, banner_id)
    title = banner.title
    delete_banner(db, banner)
    write_buyback_audit(
        db,
        actor_user_id=ctx.user.id,
        action="promo_banner_deleted",
        entity_type="buyback_promo_banner",
        entity_id=str(banner_id),
        details={"title": title},
    )
    db.commit()
    return None


@router.get("/reservations", response_model=list[schemas_buyback.BuybackStoreReservationOut])
def list_store_reservations_admin(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(_require_perm("buyback.reservation.read")),
):
    rows = list_reservations_admin(db, from_date=from_date, to_date=to_date)
    out: list[schemas_buyback.BuybackStoreReservationOut] = []
    for row in rows:
        request = (
            db.query(models_buyback.BuybackRequest)
            .filter(models_buyback.BuybackRequest.id == row.request_id)
            .first()
        )
        user = db.query(models.User).filter(models.User.id == row.user_id).first()
        out.append(
            schemas_buyback.BuybackStoreReservationOut(
                id=row.id,
                request_id=row.request_id,
                user_id=row.user_id,
                visit_at=row.visit_at,
                status=row.status,
                request_number=request.request_number if request else None,
                customer_name=user.name if user else None,
                created_at=row.created_at,
            )
        )
    return out
