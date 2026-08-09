"""Phase 3-9 admin Oripa CRUD and entry management API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models_oripa
import schemas_oripa
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.oripa_admin import (
    OripaError,
    bulk_link_products,
    create_oripa,
    delete_oripa,
    entry_to_admin_out,
    generate_entries,
    link_entry_product,
    oripa_to_out,
    raise_http,
    update_oripa,
)

router = APIRouter(prefix="/api/admin", tags=["admin-oripa"])


def _handle(exc: Exception) -> None:
    if isinstance(exc, AdminAccessError):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    raise exc


@router.get("/oripas", response_model=schemas_oripa.OripaListOut)
def list_oripas(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa.read")
        query = db.query(models_oripa.Oripa)
        if status:
            query = query.filter(models_oripa.Oripa.status == status)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(models_oripa.Oripa.title.ilike(like))
        total = query.count()
        rows = query.order_by(models_oripa.Oripa.id.desc()).offset(offset).limit(limit).all()
        return schemas_oripa.OripaListOut(
            total=total,
            items=[schemas_oripa.OripaOut(**oripa_to_out(db, r)) for r in rows],
        )
    except Exception as exc:
        _handle(exc)


@router.post("/oripas", response_model=schemas_oripa.OripaOut)
def create_oripa_api(
    payload: schemas_oripa.OripaCreate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa.create")
        try:
            row = create_oripa(
                db,
                title=payload.title,
                description=payload.description,
                price_per_entry=payload.price_per_entry,
                total_entries=payload.total_entries,
                status=payload.status,
                sale_start_at=payload.sale_start_at,
                sale_end_at=payload.sale_end_at,
                max_entries_per_purchase=payload.max_entries_per_purchase,
                actor_admin_user_id=ctx.user.id,
            )
        except OripaError as exc:
            raise_http(exc)
        db.commit()
        db.refresh(row)
        return schemas_oripa.OripaOut(**oripa_to_out(db, row))
    except Exception as exc:
        _handle(exc)


@router.get("/oripas/{oripa_id}", response_model=schemas_oripa.OripaOut)
def get_oripa_api(
    oripa_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa.read")
        row = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="オリパが見つかりません")
        return schemas_oripa.OripaOut(**oripa_to_out(db, row))
    except Exception as exc:
        _handle(exc)


@router.patch("/oripas/{oripa_id}", response_model=schemas_oripa.OripaOut)
def update_oripa_api(
    oripa_id: int,
    payload: schemas_oripa.OripaUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa.update")
        try:
            row = update_oripa(
                db,
                oripa_id,
                actor_admin_user_id=ctx.user.id,
                **payload.model_dump(exclude_unset=True),
            )
        except OripaError as exc:
            raise_http(exc)
        db.commit()
        db.refresh(row)
        return schemas_oripa.OripaOut(**oripa_to_out(db, row))
    except Exception as exc:
        _handle(exc)


@router.delete("/oripas/{oripa_id}")
def delete_oripa_api(
    oripa_id: int,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa.delete")
        try:
            delete_oripa(db, oripa_id, actor_admin_user_id=ctx.user.id)
        except OripaError as exc:
            raise_http(exc)
        db.commit()
        return {"ok": True}
    except Exception as exc:
        _handle(exc)


@router.post("/oripas/{oripa_id}/generate-entries")
def generate_entries_api(
    oripa_id: int,
    payload: schemas_oripa.OripaGenerateEntriesIn | None = None,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa_entry.manage")
        force = bool(payload.force) if payload else False
        try:
            n = generate_entries(db, oripa_id, actor_admin_user_id=ctx.user.id, force=force)
        except OripaError as exc:
            raise_http(exc)
        db.commit()
        return {"generated": n}
    except Exception as exc:
        _handle(exc)


@router.get("/oripas/{oripa_id}/entries", response_model=schemas_oripa.OripaEntryListOut)
def list_entries_api(
    oripa_id: int,
    assignment_status: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa_entry.read")
        query = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.oripa_id == oripa_id)
        if assignment_status:
            query = query.filter(models_oripa.OripaEntry.assignment_status == assignment_status)
        total = query.count()
        rows = (
            query.order_by(models_oripa.OripaEntry.entry_number.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return schemas_oripa.OripaEntryListOut(
            total=total,
            items=[schemas_oripa.OripaEntryAdminOut(**entry_to_admin_out(db, r)) for r in rows],
        )
    except Exception as exc:
        _handle(exc)


@router.patch("/oripa-entries/{entry_id}", response_model=schemas_oripa.OripaEntryAdminOut)
def link_entry_api(
    entry_id: int,
    payload: schemas_oripa.OripaEntryLinkIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa_entry.manage")
        try:
            row = link_entry_product(
                db,
                entry_id,
                payload.linked_product_id,
                actor_admin_user_id=ctx.user.id,
            )
        except OripaError as exc:
            raise_http(exc)
        db.commit()
        db.refresh(row)
        return schemas_oripa.OripaEntryAdminOut(**entry_to_admin_out(db, row))
    except Exception as exc:
        _handle(exc)


@router.post("/oripas/{oripa_id}/entries/bulk-link")
def bulk_link_api(
    oripa_id: int,
    payload: schemas_oripa.OripaEntryBulkLinkIn,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_current_admin_context),
):
    try:
        require_permission(ctx, "oripa_entry.manage")
        try:
            n = bulk_link_products(
                db,
                oripa_id,
                start_number=payload.start_number,
                product_ids=payload.product_ids,
                actor_admin_user_id=ctx.user.id,
            )
        except OripaError as exc:
            raise_http(exc)
        db.commit()
        return {"linked": n}
    except Exception as exc:
        _handle(exc)
