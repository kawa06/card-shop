"""Admin points management API."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas_points
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
import models_points
from services.point_ledger import (
    admin_deduct_points,
    admin_grant_points,
    get_account_summary,
    get_expiring_soon_points,
)
from services.point_settings import get_point_settings, update_point_settings

router = APIRouter(prefix="/api/admin/points", tags=["admin-points"])


def _handle_admin_error(exc: Exception) -> None:
    if isinstance(exc, AdminAccessError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


@router.get("/settings", response_model=schemas_points.PointSettingsOut)
def admin_get_settings(
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.settings")
    except Exception as exc:
        _handle_admin_error(exc)
    return get_point_settings(db)


@router.patch("/settings", response_model=schemas_points.PointSettingsOut)
def admin_update_settings(
    payload: schemas_points.PointSettingsUpdateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.settings")
    except Exception as exc:
        _handle_admin_error(exc)

    before = get_point_settings(db)
    before_data = {
        "enabled": before.enabled,
        "earn_rate_percent": before.earn_rate_percent,
        "expiration_days": before.expiration_days,
        "max_points_per_order": before.max_points_per_order,
        "max_usage_percent": before.max_usage_percent,
        "points_apply_to_shipping": before.points_apply_to_shipping,
    }
    data = payload.model_dump(exclude_unset=True)
    updated = update_point_settings(db, **data)
    after_data = {
        "enabled": updated.enabled,
        "earn_rate_percent": updated.earn_rate_percent,
        "expiration_days": updated.expiration_days,
        "max_points_per_order": updated.max_points_per_order,
        "max_usage_percent": updated.max_usage_percent,
        "points_apply_to_shipping": updated.points_apply_to_shipping,
    }
    db.add(
        models_points.PointAuditLog(
            actor_admin_user_id=ctx.user.id,
            action="settings_update",
            target_user_id=ctx.admin_user.id,
            before_json=json.dumps(before_data, ensure_ascii=False),
            after_json=json.dumps(after_data, ensure_ascii=False),
            reason="point settings updated",
        )
    )
    db.commit()
    db.refresh(updated)
    return updated


@router.get("/users/{user_id}", response_model=schemas_points.AdminUserPointsOut)
def admin_get_user_points(
    user_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.read")
    except Exception as exc:
        _handle_admin_error(exc)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    account = get_account_summary(db, user_id)
    return schemas_points.AdminUserPointsOut(
        user_id=user.id,
        email=user.email,
        name=user.name,
        available_points=account.available_points,
        reserved_points=account.reserved_points,
        lifetime_earned=account.lifetime_earned,
        lifetime_used=account.lifetime_used,
    )


@router.get("/users/{user_id}/history", response_model=schemas_points.PointHistoryOut)
def admin_get_user_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.read")
    except Exception as exc:
        _handle_admin_error(exc)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    query = (
        db.query(models_points.PointTransaction)
        .filter(models_points.PointTransaction.user_id == user_id)
        .order_by(models_points.PointTransaction.created_at.desc())
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return schemas_points.PointHistoryOut(items=items, total=total)


@router.post("/grant", response_model=schemas_points.PointTransactionOut)
def admin_grant(
    payload: schemas_points.AdminPointGrantIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.grant")
    except Exception as exc:
        _handle_admin_error(exc)

    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    key = payload.idempotency_key or f"admin_grant:{uuid.uuid4()}"
    tx = admin_grant_points(
        db,
        user_id=payload.user_id,
        amount=payload.amount,
        reason=payload.reason,
        admin_user_id=ctx.user.id,
        expiration_days=payload.expiration_days,
        idempotency_key=key,
    )
    db.commit()
    db.refresh(tx)
    return tx


@router.post("/deduct", response_model=schemas_points.PointTransactionOut)
def admin_deduct(
    payload: schemas_points.AdminPointDeductIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.deduct")
    except Exception as exc:
        _handle_admin_error(exc)

    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    key = payload.idempotency_key or f"admin_deduct:{uuid.uuid4()}"
    tx = admin_deduct_points(
        db,
        user_id=payload.user_id,
        amount=payload.amount,
        reason=payload.reason,
        admin_user_id=ctx.user.id,
        idempotency_key=key,
    )
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/audit", response_model=list[schemas_points.PointAuditLogOut])
def admin_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "point.audit")
    except Exception as exc:
        _handle_admin_error(exc)

    return (
        db.query(models_points.PointAuditLog)
        .order_by(models_points.PointAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
