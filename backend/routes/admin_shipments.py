"""Admin APIs for Phase 3-9 outbound shipments (oripa entries)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

import models
import models_oripa
import models_shipment
import schemas_shipment
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.barcode_render import render_code128_svg
from services.oripa_admin import OripaError, raise_http
from services.oripa_constants import format_entry_number
from services.oripa_shipment import (
    create_oripa_shipment,
    ensure_shipment_barcode,
    list_shipment_items,
    shipment_entry_labels,
    update_shipment,
)

router = APIRouter(prefix="/api/admin", tags=["admin-shipments"])


def _handle(exc: Exception) -> None:
    if isinstance(exc, AdminAccessError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


def _serialize_shipment(db: Session, row: models_shipment.Shipment, *, with_admin_content: bool = True) -> schemas_shipment.ShipmentOut:
    items_out: list[schemas_shipment.ShipmentItemOut] = []
    for item in list_shipment_items(db, row.id):
        entry = None
        if item.oripa_entry_id:
            entry = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.id == item.oripa_entry_id).first()
        product_name = None
        linked_id = None
        if with_admin_content and entry and entry.linked_product_id:
            linked_id = entry.linked_product_id
            card = db.query(models.Card).filter(models.Card.id == entry.linked_product_id).first()
            product_name = card.name if card else None
        items_out.append(
            schemas_shipment.ShipmentItemOut(
                id=item.id,
                item_type=item.item_type,
                oripa_entry_id=item.oripa_entry_id,
                entry_label=format_entry_number(entry.entry_number) if entry else None,
                oripa_id=entry.oripa_id if entry else None,
                linked_product_id=linked_id,
                linked_product_name=product_name,
            )
        )
    return schemas_shipment.ShipmentOut(
        id=row.id,
        user_id=row.user_id,
        status=row.status,
        shipping_carrier=row.shipping_carrier,
        tracking_number=row.tracking_number,
        shipping_method=row.shipping_method,
        shipped_at=row.shipped_at,
        recipient_name=row.recipient_name,
        postal_code=row.postal_code,
        region=row.region,
        city=row.city,
        address_line1=row.address_line1,
        address_line2=row.address_line2,
        phone_number=row.phone_number,
        note=row.note,
        entry_labels=shipment_entry_labels(db, row.id),
        items=items_out,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/shipments", response_model=schemas_shipment.ShipmentListOut)
def list_shipments(
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.read")
        query = db.query(models_shipment.Shipment)
        if user_id is not None:
            query = query.filter(models_shipment.Shipment.user_id == user_id)
        if status:
            query = query.filter(models_shipment.Shipment.status == status)
        total = query.count()
        rows = query.order_by(models_shipment.Shipment.id.desc()).offset(offset).limit(limit).all()
        return schemas_shipment.ShipmentListOut(
            total=total,
            items=[_serialize_shipment(db, r) for r in rows],
        )
    except Exception as exc:
        _handle(exc)


@router.post("/shipments", response_model=schemas_shipment.ShipmentOut)
def create_shipment(
    payload: schemas_shipment.ShipmentCreateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.create")
        shipment = create_oripa_shipment(
            db,
            user_id=payload.user_id,
            entry_ids=payload.entry_ids,
            actor_admin_user_id=ctx.user.id,
            note=payload.note,
        )
        db.commit()
        db.refresh(shipment)
        return _serialize_shipment(db, shipment)
    except OripaError as exc:
        db.rollback()
        raise_http(exc)
    except Exception as exc:
        db.rollback()
        _handle(exc)


@router.get("/shipments/{shipment_id}", response_model=schemas_shipment.ShipmentOut)
def get_shipment(
    shipment_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.read")
        row = db.query(models_shipment.Shipment).filter(models_shipment.Shipment.id == shipment_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Shipment が見つかりません")
        return _serialize_shipment(db, row)
    except Exception as exc:
        _handle(exc)


@router.patch("/shipments/{shipment_id}", response_model=schemas_shipment.ShipmentOut)
def patch_shipment(
    shipment_id: int,
    payload: schemas_shipment.ShipmentUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.update")
        data = payload.model_dump(exclude_unset=True)
        row = update_shipment(db, shipment_id, actor_admin_user_id=ctx.user.id, **data)
        db.commit()
        db.refresh(row)
        return _serialize_shipment(db, row)
    except OripaError as exc:
        db.rollback()
        raise_http(exc)
    except Exception as exc:
        db.rollback()
        _handle(exc)


@router.get("/shipments/{shipment_id}/logs", response_model=list[schemas_shipment.ShipmentLogOut])
def shipment_logs(
    shipment_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.read")
        rows = (
            db.query(models_shipment.ShipmentLog)
            .filter(models_shipment.ShipmentLog.shipment_id == shipment_id)
            .order_by(models_shipment.ShipmentLog.id.asc())
            .all()
        )
        return [
            schemas_shipment.ShipmentLogOut(
                id=r.id,
                event_type=r.event_type,
                from_status=r.from_status,
                to_status=r.to_status,
                tracking_number=r.tracking_number,
                shipping_carrier=r.shipping_carrier,
                admin_user_id=r.admin_user_id,
                note=r.note,
                created_at=r.created_at,
            )
            for r in rows
        ]
    except Exception as exc:
        _handle(exc)


@router.get("/shipments/{shipment_id}/barcode", response_model=schemas_shipment.ShipmentBarcodeOut)
def shipment_barcode(
    shipment_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.read")
        shipment = db.query(models_shipment.Shipment).filter(models_shipment.Shipment.id == shipment_id).first()
        if shipment is None:
            raise HTTPException(status_code=404, detail="Shipment が見つかりません")
        row = ensure_shipment_barcode(db, shipment=shipment)
        db.commit()
        return schemas_shipment.ShipmentBarcodeOut(
            id=row.id,
            scan_token=row.scan_token,
            human_readable=row.human_readable,
            shipment_id=row.shipment_id,
            is_active=row.is_active,
        )
    except Exception as exc:
        db.rollback()
        _handle(exc)


@router.get("/shipments/{shipment_id}/barcode.svg")
def shipment_barcode_svg(
    shipment_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "shipment.read")
        shipment = db.query(models_shipment.Shipment).filter(models_shipment.Shipment.id == shipment_id).first()
        if shipment is None:
            raise HTTPException(status_code=404, detail="Shipment が見つかりません")
        row = ensure_shipment_barcode(db, shipment=shipment)
        db.commit()
        svg = render_code128_svg(row.scan_token, aria_label=f"Shipment {shipment_id}")
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as exc:
        db.rollback()
        _handle(exc)
