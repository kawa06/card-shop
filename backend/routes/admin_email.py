"""Admin email template management APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import models_email
import schemas_email
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.db_persist import PersistDep, safe_commit
from services.email_delivery import get_brand_settings, preview_template, send_templated_email

router = APIRouter(
    prefix="/api/admin/email",
    tags=["admin-email"],
    dependencies=[PersistDep],
)


def _require_perm(permission: str):
    def _dep(ctx: AdminContext = Depends(get_current_admin_context)) -> AdminContext:
        try:
            require_permission(ctx, permission)
        except AdminAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return ctx

    return _dep


@router.get("/brand", response_model=schemas_email.EmailBrandSettingsOut)
def get_brand(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return get_brand_settings(db)


@router.put("/brand", response_model=schemas_email.EmailBrandSettingsOut)
def update_brand(
    payload: schemas_email.EmailBrandSettingsUpdate,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    brand = get_brand_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    safe_commit(db)
    db.refresh(brand)
    return brand


@router.get("/templates", response_model=list[schemas_email.EmailTemplateListItem])
def list_templates(
    category: Optional[str] = Query(None),
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    q = db.query(models_email.EmailTemplate).order_by(
        models_email.EmailTemplate.category,
        models_email.EmailTemplate.template_key,
    )
    if category:
        q = q.filter(models_email.EmailTemplate.category == category)
    return q.all()


@router.get("/templates/{template_key}", response_model=schemas_email.EmailTemplateOut)
def get_template(
    template_key: str,
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    return tpl


@router.put("/templates/{template_key}", response_model=schemas_email.EmailTemplateOut)
def update_template(
    template_key: str,
    payload: schemas_email.EmailTemplateUpdate,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tpl, field, value)
    safe_commit(db)
    db.refresh(tpl)
    return tpl


@router.patch("/templates/{template_key}/active", response_model=schemas_email.EmailTemplateOut)
def toggle_template_active(
    template_key: str,
    is_active: bool = Query(...),
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    tpl.is_active = is_active
    safe_commit(db)
    db.refresh(tpl)
    return tpl


@router.post("/templates/{template_key}/preview", response_model=schemas_email.EmailTemplatePreviewOut)
def preview(
    template_key: str,
    payload: schemas_email.EmailTemplatePreviewIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    try:
        result = preview_template(db, template_key=template_key, variables=payload.variables)
    except ValueError:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    return schemas_email.EmailTemplatePreviewOut(**result)


@router.post("/templates/{template_key}/test-send", status_code=status.HTTP_200_OK)
def test_send(
    template_key: str,
    payload: schemas_email.EmailTestSendIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=payload.to_email,
        variables=payload.variables,
        is_test=True,
        force=True,
        fallback_subject="テスト送信",
        fallback_html="<p>テストメールです。</p>",
    )
    safe_commit(db)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error or "送信に失敗しました")
    return {"message": "テストメールを送信しました"}


@router.get("/send-logs", response_model=list[schemas_email.EmailSendLogOut])
def send_logs(
    status_filter: Optional[str] = Query(None, alias="status"),
    template_key: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    q = db.query(models_email.EmailSendLog).order_by(models_email.EmailSendLog.created_at.desc())
    if status_filter:
        q = q.filter(models_email.EmailSendLog.status == status_filter)
    if template_key:
        q = q.filter(models_email.EmailSendLog.template_key == template_key)
    return q.limit(limit).all()
