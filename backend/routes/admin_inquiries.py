"""Admin inquiry management routes."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from auth import get_current_admin
from database import get_db
from services.db_persist import PersistDep, safe_commit
from services.inquiry_service import (
    add_admin_reply,
    get_admin_inquiry,
    get_inquiry_settings,
    mark_admin_read,
)
from services.inquiry_emails import notify_customer_admin_reply, notify_inquiry_status_change
from services.inquiry_template_render import build_template_context, render_template_body
from services.inquiry_seed import seed_inquiry_data
from services.inquiry_service import save_inquiry_attachments
from services.inquiry_upload import build_download_path, create_attachment_download_token

router = APIRouter(
    prefix="/api/admin/inquiries",
    tags=["admin-inquiries"],
    dependencies=[PersistDep],
)


def _admin_list_out(inquiry: models.Inquiry) -> schemas.AdminInquiryListOut:
    user = inquiry.user
    admin = inquiry.assigned_admin
    return schemas.AdminInquiryListOut(
        id=inquiry.id,
        inquiry_number=inquiry.inquiry_number,
        category=inquiry.category,
        subject=inquiry.subject,
        related_order_number=inquiry.related_order_number,
        status=inquiry.status,
        priority=inquiry.priority,
        last_message_at=inquiry.last_message_at,
        customer_unread_count=inquiry.customer_unread_count or 0,
        admin_unread_count=inquiry.admin_unread_count or 0,
        created_at=inquiry.created_at,
        updated_at=inquiry.updated_at,
        buyer_name=user.name if user else None,
        buyer_email=user.email if user else inquiry.guest_email,
        assigned_admin_name=admin.name if admin else None,
    )


def _admin_detail_messages(inquiry: models.Inquiry) -> list[schemas.InquiryMessageOut]:
    out: list[schemas.InquiryMessageOut] = []
    for msg in inquiry.messages:
        if msg.deleted_at:
            continue
        name = None
        if msg.sender_type == "customer" and inquiry.user:
            name = inquiry.user.name
        elif msg.sender_type == "admin":
            name = inquiry.assigned_admin.name if inquiry.assigned_admin else "管理者"
        elif msg.sender_type == "system":
            name = "システム"
        out.append(
            schemas.InquiryMessageOut(
                id=msg.id,
                sender_type=msg.sender_type,
                message=msg.message,
                is_internal_note=msg.is_internal_note,
                template_id=msg.template_id,
                created_at=msg.created_at,
                sender_name=name,
            )
        )
    return out


def _admin_attachment_out(attachment: models.InquiryAttachment) -> schemas.InquiryAttachmentOut:
    token = create_attachment_download_token(attachment.id, is_admin=True)
    return schemas.InquiryAttachmentOut(
        id=attachment.id,
        message_id=attachment.message_id,
        original_filename=attachment.original_filename,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        created_at=attachment.created_at,
        download_url=build_download_path(attachment.id, token),
    )


@router.get("/stats", response_model=schemas.InquiryStatsOut)
def inquiry_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    base = db.query(models.Inquiry).filter(models.Inquiry.shop_id == 1)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return schemas.InquiryStatsOut(
        unreplied_count=base.filter(models.Inquiry.admin_unread_count > 0).count(),
        today_count=base.filter(models.Inquiry.created_at >= today_start).count(),
        in_progress_count=base.filter(models.Inquiry.status == "in_progress").count(),
        waiting_customer_count=base.filter(models.Inquiry.status == "waiting_customer").count(),
        resolved_count=base.filter(models.Inquiry.status == "resolved").count(),
        high_priority_count=base.filter(models.Inquiry.priority == "high").count(),
    )


@router.get("", response_model=list[schemas.AdminInquiryListOut])
def list_inquiries(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_admin_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    query = (
        db.query(models.Inquiry)
        .options(joinedload(models.Inquiry.user), joinedload(models.Inquiry.assigned_admin))
        .filter(models.Inquiry.shop_id == 1)
    )
    if q:
        term = f"%{q.strip()}%"
        query = query.outerjoin(models.User, models.Inquiry.user_id == models.User.id).filter(
            or_(
                models.Inquiry.inquiry_number.ilike(term),
                models.Inquiry.subject.ilike(term),
                models.Inquiry.related_order_number.ilike(term),
                models.User.name.ilike(term),
                models.User.email.ilike(term),
            )
        )
    if status:
        query = query.filter(models.Inquiry.status == status)
    if category:
        query = query.filter(models.Inquiry.category == category)
    if priority:
        query = query.filter(models.Inquiry.priority == priority)
    if assigned_admin_id:
        query = query.filter(models.Inquiry.assigned_admin_id == assigned_admin_id)

    rows = query.order_by(models.Inquiry.admin_unread_count.desc(), models.Inquiry.updated_at.desc()).all()
    return [_admin_list_out(r) for r in rows]


@router.get("/templates", response_model=list[schemas.InquiryTemplateOut])
def list_admin_templates(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    return (
        db.query(models.InquiryTemplate)
        .filter(
            models.InquiryTemplate.shop_id == 1,
            models.InquiryTemplate.template_type == "admin",
            models.InquiryTemplate.is_active.is_(True),
        )
        .order_by(models.InquiryTemplate.sort_order, models.InquiryTemplate.id)
        .all()
    )


@router.post("/templates/{template_id}/preview", response_model=schemas.InquiryTemplatePreview)
def preview_admin_template(
    template_id: int,
    inquiry_id: int = Query(...),
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    tpl = (
        db.query(models.InquiryTemplate)
        .filter(
            models.InquiryTemplate.id == template_id,
            models.InquiryTemplate.shop_id == 1,
            models.InquiryTemplate.template_type == "admin",
        )
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    inquiry = get_admin_inquiry(db, inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")

    ctx = build_template_context(
        inquiry=inquiry,
        user=inquiry.user,
        order=inquiry.related_order,
        product=inquiry.related_product,
        admin=admin,
        reason=reason,
    )
    body, warnings = render_template_body(tpl.body, ctx, warn_missing=True)
    return schemas.InquiryTemplatePreview(body=body, warnings=warnings)


# ── Settings & template CRUD (must be before /{inquiry_id}) ──

@router.get("/manage/templates", response_model=list[schemas.InquiryTemplateOut])
def manage_list_templates(
    template_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    query = db.query(models.InquiryTemplate).filter(models.InquiryTemplate.shop_id == 1)
    if template_type:
        query = query.filter(models.InquiryTemplate.template_type == template_type)
    return query.order_by(models.InquiryTemplate.template_type, models.InquiryTemplate.sort_order).all()


@router.post("/manage/templates", response_model=schemas.InquiryTemplateOut, status_code=201)
def create_template(
    payload: schemas.InquiryTemplateCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    if payload.template_type not in ("customer", "admin"):
        raise HTTPException(status_code=400, detail="template_type は customer または admin")
    row = models.InquiryTemplate(
        shop_id=1,
        template_type=payload.template_type,
        category=payload.category,
        name=payload.name,
        body=payload.body,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        created_by=admin.id,
    )
    db.add(row)
    safe_commit(db, action="テンプレート作成")
    db.refresh(row)
    return row


@router.put("/manage/templates/{template_id}", response_model=schemas.InquiryTemplateOut)
def update_template(
    template_id: int,
    payload: schemas.InquiryTemplateUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    row = (
        db.query(models.InquiryTemplate)
        .filter(models.InquiryTemplate.id == template_id, models.InquiryTemplate.shop_id == 1)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    safe_commit(db, action="テンプレート更新")
    db.refresh(row)
    return row


@router.delete("/manage/templates/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    row = (
        db.query(models.InquiryTemplate)
        .filter(models.InquiryTemplate.id == template_id, models.InquiryTemplate.shop_id == 1)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    db.delete(row)
    safe_commit(db, action="テンプレート削除")
    return {"ok": True}


@router.get("/manage/settings", response_model=schemas.InquirySettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    seed_inquiry_data(db)
    return get_inquiry_settings(db)


@router.put("/manage/settings", response_model=schemas.InquirySettingsOut)
def update_settings(
    payload: schemas.InquirySettingsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    row = get_inquiry_settings(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    safe_commit(db, action="問い合わせ設定更新")
    db.refresh(row)
    return row


@router.get("/{inquiry_id}")
def get_inquiry_detail(
    inquiry_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    inquiry = get_admin_inquiry(db, inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    mark_admin_read(db, inquiry)
    data = _admin_list_out(inquiry)
    return {
        **data.model_dump(),
        "reply_email": inquiry.reply_email,
        "related_order_id": inquiry.related_order_id,
        "related_product_id": inquiry.related_product_id,
        "related_product_name": inquiry.related_product.name if inquiry.related_product else None,
        "messages": _admin_detail_messages(inquiry),
        "attachments": [_admin_attachment_out(a) for a in (inquiry.attachments or [])],
    }


@router.post("/{inquiry_id}/reply", response_model=schemas.InquiryMessageOut)
def reply_inquiry(
    inquiry_id: int,
    payload: schemas.AdminInquiryReply,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    inquiry = get_admin_inquiry(db, inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")

    old_status = inquiry.status
    message = payload.message
    if payload.template_id and not message.strip():
        tpl = db.query(models.InquiryTemplate).filter(models.InquiryTemplate.id == payload.template_id).first()
        if tpl:
            ctx = build_template_context(
                inquiry=inquiry,
                user=inquiry.user,
                order=inquiry.related_order,
                product=inquiry.related_product,
                admin=admin,
                reason=payload.reason,
            )
            message, _ = render_template_body(tpl.body, ctx, warn_missing=True)

    try:
        msg = add_admin_reply(
            db,
            inquiry,
            admin,
            message,
            is_internal_note=payload.is_internal_note,
            template_id=payload.template_id,
            new_status=payload.status,
            assigned_admin_id=payload.assigned_admin_id or admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not payload.is_internal_note:
        db.refresh(inquiry)
        new_status = inquiry.status
        if new_status in ("resolved", "closed") and new_status != old_status:
            notify_inquiry_status_change(
                inquiry,
                old_status=old_status,
                new_status=new_status,
                reply_text=message,
            )
        else:
            notify_customer_admin_reply(inquiry, message)

    return schemas.InquiryMessageOut(
        id=msg.id,
        sender_type=msg.sender_type,
        message=msg.message,
        is_internal_note=msg.is_internal_note,
        template_id=msg.template_id,
        created_at=msg.created_at,
        sender_name=admin.name,
    )


@router.patch("/{inquiry_id}", response_model=schemas.AdminInquiryListOut)
def update_inquiry(
    inquiry_id: int,
    payload: schemas.AdminInquiryUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    inquiry = get_admin_inquiry(db, inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    old_status = inquiry.status
    if payload.status:
        from services.inquiry_service import _record_status

        _record_status(db, inquiry, payload.status, admin.id)
    if payload.priority:
        inquiry.priority = payload.priority
    if payload.assigned_admin_id is not None:
        inquiry.assigned_admin_id = payload.assigned_admin_id
    inquiry.updated_at = datetime.utcnow()
    safe_commit(db, action="問い合わせ更新")
    db.refresh(inquiry)
    if payload.status and payload.status != old_status:
        notify_inquiry_status_change(
            inquiry,
            old_status=old_status,
            new_status=inquiry.status,
        )
    return _admin_list_out(inquiry)


@router.post("/{inquiry_id}/attachments", response_model=list[schemas.InquiryAttachmentOut])
async def upload_admin_attachments(
    inquiry_id: int,
    files: list[UploadFile] = File(...),
    message_id: int | None = Query(None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    inquiry = get_admin_inquiry(db, inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    try:
        saved = await save_inquiry_attachments(
            db,
            inquiry,
            files,
            message_id=message_id,
            uploaded_by_type="admin",
            uploaded_by_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_admin_attachment_out(a) for a in saved]

