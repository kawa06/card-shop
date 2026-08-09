"""Admin coupons management API."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_coupons
import schemas_coupons
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.coupon_calculator import coupon_card_ids, coupon_category_ids
from services.coupon_ledger import count_redemptions

router = APIRouter(prefix="/api/admin/coupons", tags=["admin-coupons"])


def _handle_admin_error(exc: Exception) -> None:
    if isinstance(exc, AdminAccessError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


def _ids_json(ids: list[int] | None) -> Optional[str]:
    if not ids:
        return None
    return json.dumps([int(x) for x in ids], ensure_ascii=False)


def _to_out(db: Session, coupon: models_coupons.Coupon) -> schemas_coupons.CouponOut:
    return schemas_coupons.CouponOut(
        id=coupon.id,
        code=coupon.code,
        name=coupon.name,
        description=coupon.description,
        coupon_type=coupon.coupon_type,
        audience=coupon.audience,
        amount_yen=coupon.amount_yen,
        percent_off=coupon.percent_off,
        max_discount_yen=coupon.max_discount_yen,
        min_subtotal_yen=int(coupon.min_subtotal_yen or 0),
        max_uses_total=coupon.max_uses_total,
        max_uses_per_user=int(coupon.max_uses_per_user or 1),
        starts_at=coupon.starts_at,
        ends_at=coupon.ends_at,
        card_ids=coupon_card_ids(coupon),
        category_ids=coupon_category_ids(coupon),
        is_active=bool(coupon.is_active),
        created_at=coupon.created_at,
        updated_at=coupon.updated_at,
        redemption_count=count_redemptions(db, coupon_id=coupon.id),
    )


def _validate_type_fields(payload: schemas_coupons.CouponCreateIn | schemas_coupons.CouponUpdateIn, *, coupon_type: str) -> None:
    if coupon_type == "fixed_amount":
        amount = getattr(payload, "amount_yen", None)
        if amount is None or int(amount) <= 0:
            raise HTTPException(status_code=400, detail="固定金額クーポンには amount_yen が必要です")
    elif coupon_type == "percent":
        percent = getattr(payload, "percent_off", None)
        if percent is None or int(percent) <= 0:
            raise HTTPException(status_code=400, detail="割引率クーポンには percent_off が必要です")
    elif coupon_type == "free_shipping":
        return
    else:
        raise HTTPException(status_code=400, detail="不正なクーポン種別です")


def _audit(
    db: Session,
    *,
    ctx: AdminContext,
    action: str,
    coupon_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    reason: Optional[str] = None,
) -> None:
    db.add(
        models_coupons.CouponAuditLog(
            actor_admin_user_id=ctx.user.id,
            action=action,
            coupon_id=coupon_id,
            target_user_id=target_user_id,
            before_json=json.dumps(before, ensure_ascii=False, default=str) if before else None,
            after_json=json.dumps(after, ensure_ascii=False, default=str) if after else None,
            reason=reason,
        )
    )


@router.get("", response_model=schemas_coupons.CouponListOut)
def admin_list_coupons(
    q: Optional[str] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "coupon.read")
    except Exception as exc:
        _handle_admin_error(exc)

    query = db.query(models_coupons.Coupon)
    if active_only:
        query = query.filter(models_coupons.Coupon.is_active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (models_coupons.Coupon.code.ilike(like)) | (models_coupons.Coupon.name.ilike(like))
        )
    total = query.count()
    rows = query.order_by(models_coupons.Coupon.id.desc()).offset(offset).limit(limit).all()
    return schemas_coupons.CouponListOut(items=[_to_out(db, r) for r in rows], total=total)


@router.post("", response_model=schemas_coupons.CouponOut, status_code=201)
def admin_create_coupon(
    payload: schemas_coupons.CouponCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "coupon.write")
    except Exception as exc:
        _handle_admin_error(exc)

    _validate_type_fields(payload, coupon_type=payload.coupon_type)
    exists = (
        db.query(models_coupons.Coupon)
        .filter(func.upper(models_coupons.Coupon.code) == payload.code.upper())
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="同じクーポンコードが既に存在します")

    coupon = models_coupons.Coupon(
        code=payload.code.upper(),
        name=payload.name,
        description=payload.description,
        coupon_type=payload.coupon_type,
        audience=payload.audience,
        amount_yen=payload.amount_yen,
        percent_off=payload.percent_off,
        max_discount_yen=payload.max_discount_yen,
        min_subtotal_yen=payload.min_subtotal_yen,
        max_uses_total=payload.max_uses_total,
        max_uses_per_user=payload.max_uses_per_user,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        card_ids_json=_ids_json(payload.card_ids),
        category_ids_json=_ids_json(payload.category_ids),
        is_active=payload.is_active,
        created_by=ctx.user.id,
    )
    db.add(coupon)
    db.flush()
    _audit(db, ctx=ctx, action="coupon.create", coupon_id=coupon.id, after=_to_out(db, coupon).model_dump())
    db.commit()
    db.refresh(coupon)
    return _to_out(db, coupon)


@router.patch("/{coupon_id}", response_model=schemas_coupons.CouponOut)
def admin_update_coupon(
    coupon_id: int,
    payload: schemas_coupons.CouponUpdateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "coupon.write")
    except Exception as exc:
        _handle_admin_error(exc)

    coupon = db.query(models_coupons.Coupon).filter(models_coupons.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="クーポンが見つかりません")

    before = _to_out(db, coupon).model_dump()
    data = payload.model_dump(exclude_unset=True)
    if "card_ids" in data:
        coupon.card_ids_json = _ids_json(data.pop("card_ids"))
    if "category_ids" in data:
        coupon.category_ids_json = _ids_json(data.pop("category_ids"))
    for key, value in data.items():
        setattr(coupon, key, value)
    coupon.updated_at = datetime.utcnow()
    _audit(db, ctx=ctx, action="coupon.update", coupon_id=coupon.id, before=before, after=_to_out(db, coupon).model_dump())
    db.commit()
    db.refresh(coupon)
    return _to_out(db, coupon)


@router.post("/{coupon_id}/assign", response_model=schemas_coupons.CouponOut)
def admin_assign_coupon(
    coupon_id: int,
    payload: schemas_coupons.CouponAssignIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "coupon.assign")
    except Exception as exc:
        _handle_admin_error(exc)

    coupon = db.query(models_coupons.Coupon).filter(models_coupons.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="クーポンが見つかりません")
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    existing = (
        db.query(models_coupons.CouponAssignment)
        .filter(
            models_coupons.CouponAssignment.coupon_id == coupon_id,
            models_coupons.CouponAssignment.user_id == payload.user_id,
        )
        .first()
    )
    if existing is None:
        db.add(
            models_coupons.CouponAssignment(
                coupon_id=coupon_id,
                user_id=payload.user_id,
                assigned_by=ctx.user.id,
                note=payload.note,
            )
        )
        if coupon.audience != "assigned":
            coupon.audience = "assigned"
        _audit(
            db,
            ctx=ctx,
            action="coupon.assign",
            coupon_id=coupon.id,
            target_user_id=payload.user_id,
            reason=payload.note,
        )
        db.commit()
        db.refresh(coupon)
        try:
            assignment = (
                db.query(models_coupons.CouponAssignment)
                .filter(
                    models_coupons.CouponAssignment.coupon_id == coupon_id,
                    models_coupons.CouponAssignment.user_id == payload.user_id,
                )
                .first()
            )
            if assignment:
                from services.notification_events import notify_coupon_assigned

                notify_coupon_assigned(
                    db,
                    user_id=payload.user_id,
                    coupon=coupon,
                    assignment_id=assignment.id,
                )
                db.commit()
        except Exception:
            pass
        return _to_out(db, coupon)
    db.refresh(coupon)
    return _to_out(db, coupon)


@router.get("/export.csv")
def admin_export_coupons_csv(
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "coupon.export")
    except Exception as exc:
        _handle_admin_error(exc)

    rows = db.query(models_coupons.Coupon).order_by(models_coupons.Coupon.id.asc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "code",
            "name",
            "coupon_type",
            "audience",
            "amount_yen",
            "percent_off",
            "max_discount_yen",
            "min_subtotal_yen",
            "max_uses_total",
            "max_uses_per_user",
            "starts_at",
            "ends_at",
            "is_active",
            "redemption_count",
        ]
    )
    for c in rows:
        writer.writerow(
            [
                c.id,
                c.code,
                c.name,
                c.coupon_type,
                c.audience,
                c.amount_yen,
                c.percent_off,
                c.max_discount_yen,
                c.min_subtotal_yen,
                c.max_uses_total,
                c.max_uses_per_user,
                c.starts_at.isoformat() if c.starts_at else "",
                c.ends_at.isoformat() if c.ends_at else "",
                int(bool(c.is_active)),
                count_redemptions(db, coupon_id=c.id),
            ]
        )
    content = buf.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="coupons.csv"'},
    )


@router.get("/audit", response_model=list[schemas_coupons.CouponAuditLogOut])
def admin_coupon_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "coupon.audit")
    except Exception as exc:
        _handle_admin_error(exc)
    rows = (
        db.query(models_coupons.CouponAuditLog)
        .order_by(models_coupons.CouponAuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows
