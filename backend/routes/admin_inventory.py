"""Phase 3-8 admin inventory alerts and restocks API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import models_inventory
import schemas_inventory
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.inventory_alerts import manually_resolve_alert
from services.inventory_restock import (
    RestockError,
    create_restock,
    raise_http,
    receive_restock,
    update_restock,
)

router = APIRouter(prefix="/api/admin", tags=["admin-inventory"])


def _handle_admin_error(exc: Exception) -> None:
    if isinstance(exc, AdminAccessError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def _product_name(db: Session, product_id: int) -> Optional[str]:
    card = db.query(models.Card).filter(models.Card.id == product_id).first()
    return card.name if card else None


def _alert_out(db: Session, row: models_inventory.InventoryAlert) -> schemas_inventory.InventoryAlertOut:
    return schemas_inventory.InventoryAlertOut(
        id=row.id,
        product_id=row.product_id,
        product_name=_product_name(db, row.product_id),
        alert_type=row.alert_type,
        stock_quantity=int(row.stock_quantity),
        threshold=int(row.threshold),
        status=row.status,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
        created_by=row.created_by,
        resolved_by=row.resolved_by,
    )


def _restock_out(db: Session, row: models_inventory.InventoryRestock) -> schemas_inventory.InventoryRestockOut:
    card = db.query(models.Card).filter(models.Card.id == row.product_id).first()
    return schemas_inventory.InventoryRestockOut(
        id=row.id,
        product_id=row.product_id,
        product_name=card.name if card else None,
        requested_quantity=int(row.requested_quantity),
        received_quantity=row.received_quantity,
        status=row.status,
        note=row.note,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        current_stock=int(card.stock or 0) if card else None,
    )


@router.get("/inventory-alerts", response_model=schemas_inventory.InventoryAlertListOut)
def list_inventory_alerts(
    q: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    min_stock: Optional[int] = Query(None),
    max_stock: Optional[int] = Query(None),
    from_at: Optional[str] = Query(None),
    to_at: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "inventory_alert.read")
        query = db.query(models_inventory.InventoryAlert)
        if alert_type:
            query = query.filter(models_inventory.InventoryAlert.alert_type == alert_type)
        if status:
            query = query.filter(models_inventory.InventoryAlert.status == status)
        if product_id is not None:
            query = query.filter(models_inventory.InventoryAlert.product_id == product_id)
        if min_stock is not None:
            query = query.filter(models_inventory.InventoryAlert.stock_quantity >= min_stock)
        if max_stock is not None:
            query = query.filter(models_inventory.InventoryAlert.stock_quantity <= max_stock)
        start = _parse_dt(from_at)
        end = _parse_dt(to_at)
        if start is not None:
            query = query.filter(models_inventory.InventoryAlert.created_at >= start)
        if end is not None:
            query = query.filter(models_inventory.InventoryAlert.created_at < end)
        if q:
            like = f"%{q.strip()}%"
            card_ids = [
                c.id
                for c in db.query(models.Card.id)
                .filter(or_(models.Card.name.ilike(like), models.Card.name_en.ilike(like)))
                .limit(500)
                .all()
            ]
            if q.strip().isdigit():
                card_ids.append(int(q.strip()))
            query = query.filter(models_inventory.InventoryAlert.product_id.in_(card_ids or [-1]))

        sort_map = {
            "created_at": models_inventory.InventoryAlert.created_at,
            "stock_quantity": models_inventory.InventoryAlert.stock_quantity,
            "threshold": models_inventory.InventoryAlert.threshold,
            "alert_type": models_inventory.InventoryAlert.alert_type,
            "status": models_inventory.InventoryAlert.status,
            "id": models_inventory.InventoryAlert.id,
        }
        sort_col = sort_map.get(sort, models_inventory.InventoryAlert.created_at)
        sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()
        total = query.count()
        rows = query.order_by(sort_expr, models_inventory.InventoryAlert.id.desc()).offset(offset).limit(limit).all()
        return schemas_inventory.InventoryAlertListOut(
            total=total,
            items=[_alert_out(db, r) for r in rows],
        )
    except Exception as exc:
        _handle_admin_error(exc)


@router.post("/inventory-alerts/{alert_id}/resolve", response_model=schemas_inventory.InventoryAlertOut)
def resolve_inventory_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    """Manually resolve an alert.

    Allowed even if stock is still below threshold. A later stock change that
    still meets alert conditions may open a new alert.
    """
    try:
        require_permission(ctx, "inventory_alert.write")
        try:
            alert = manually_resolve_alert(
                db,
                alert_id,
                actor_admin_user_id=ctx.user.id,
                reason="manual_resolve",
            )
        except LookupError:
            raise HTTPException(status_code=404, detail="alert が見つかりません") from None
        db.commit()
        db.refresh(alert)
        return _alert_out(db, alert)
    except Exception as exc:
        _handle_admin_error(exc)


@router.get("/inventory-restocks", response_model=schemas_inventory.InventoryRestockListOut)
def list_inventory_restocks(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "inventory_restock.read")
        query = db.query(models_inventory.InventoryRestock)
        if status:
            query = query.filter(models_inventory.InventoryRestock.status == status)
        if product_id is not None:
            query = query.filter(models_inventory.InventoryRestock.product_id == product_id)
        if q:
            like = f"%{q.strip()}%"
            card_ids = [
                c.id
                for c in db.query(models.Card.id)
                .filter(or_(models.Card.name.ilike(like), models.Card.name_en.ilike(like)))
                .limit(500)
                .all()
            ]
            if q.strip().isdigit():
                card_ids.append(int(q.strip()))
            query = query.filter(models_inventory.InventoryRestock.product_id.in_(card_ids or [-1]))

        sort_map = {
            "created_at": models_inventory.InventoryRestock.created_at,
            "requested_quantity": models_inventory.InventoryRestock.requested_quantity,
            "status": models_inventory.InventoryRestock.status,
            "id": models_inventory.InventoryRestock.id,
        }
        sort_col = sort_map.get(sort, models_inventory.InventoryRestock.created_at)
        sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()
        total = query.count()
        rows = (
            query.order_by(sort_expr, models_inventory.InventoryRestock.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return schemas_inventory.InventoryRestockListOut(
            total=total,
            items=[_restock_out(db, r) for r in rows],
        )
    except Exception as exc:
        _handle_admin_error(exc)


@router.post("/inventory-restocks", response_model=schemas_inventory.InventoryRestockOut)
def create_inventory_restock(
    payload: schemas_inventory.InventoryRestockCreateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "inventory_restock.write")
        try:
            row = create_restock(
                db,
                product_id=payload.product_id,
                requested_quantity=payload.requested_quantity,
                note=payload.note,
                actor_admin_user_id=ctx.user.id,
            )
        except RestockError as exc:
            raise_http(exc)
        db.commit()
        db.refresh(row)
        return _restock_out(db, row)
    except Exception as exc:
        _handle_admin_error(exc)


@router.get("/inventory-restocks/{restock_id}", response_model=schemas_inventory.InventoryRestockOut)
def get_inventory_restock(
    restock_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "inventory_restock.read")
        row = (
            db.query(models_inventory.InventoryRestock)
            .filter(models_inventory.InventoryRestock.id == restock_id)
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="restock が見つかりません")
        return _restock_out(db, row)
    except Exception as exc:
        _handle_admin_error(exc)


@router.patch("/inventory-restocks/{restock_id}", response_model=schemas_inventory.InventoryRestockOut)
def patch_inventory_restock(
    restock_id: int,
    payload: schemas_inventory.InventoryRestockUpdateIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "inventory_restock.write")
        try:
            row = update_restock(
                db,
                restock_id,
                status=payload.status,
                requested_quantity=payload.requested_quantity,
                note=payload.note,
                actor_admin_user_id=ctx.user.id,
            )
        except RestockError as exc:
            raise_http(exc)
        db.commit()
        db.refresh(row)
        return _restock_out(db, row)
    except Exception as exc:
        _handle_admin_error(exc)


@router.post("/inventory-restocks/{restock_id}/receive", response_model=schemas_inventory.InventoryRestockOut)
def receive_inventory_restock(
    restock_id: int,
    payload: schemas_inventory.InventoryRestockReceiveIn | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "inventory_restock.write")
        qty = payload.received_quantity if payload else None
        try:
            row = receive_restock(
                db,
                restock_id,
                received_quantity=qty,
                actor_admin_user_id=ctx.user.id,
            )
        except RestockError as exc:
            raise_http(exc)
        db.commit()
        db.refresh(row)
        return _restock_out(db, row)
    except Exception as exc:
        _handle_admin_error(exc)
