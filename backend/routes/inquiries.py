"""Customer inquiry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user
from database import get_db
from services.inquiry_constants import INQUIRY_CATEGORIES, INQUIRY_CATEGORY_LABELS
from services.inquiry_emails import (
    notify_admin_customer_reply,
    notify_admin_new_inquiry,
    notify_customer_admin_reply,
    notify_inquiry_received,
)
from services.inquiry_service import (
    add_customer_message,
    create_inquiry,
    get_customer_inquiry,
    mark_customer_read,
    save_inquiry_attachments,
)
from services.inquiry_template_render import build_template_context, render_template_body
from services.inquiry_upload import (
    build_download_path,
    create_attachment_download_token,
    resolve_storage_path,
    verify_attachment_download_token,
)

router = APIRouter(prefix="/api/inquiries", tags=["inquiries"])


def _attachment_out(
    attachment: models.InquiryAttachment,
    *,
    user_id: int,
) -> schemas.InquiryAttachmentOut:
    token = create_attachment_download_token(attachment.id, user_id=user_id)
    return schemas.InquiryAttachmentOut(
        id=attachment.id,
        message_id=attachment.message_id,
        original_filename=attachment.original_filename,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        created_at=attachment.created_at,
        download_url=build_download_path(attachment.id, token),
    )


def _message_out(msg: models.InquiryMessage, inquiry: models.Inquiry) -> schemas.InquiryMessageOut:
    name = None
    if msg.sender_type == "customer" and inquiry.user:
        name = inquiry.user.name
    elif msg.sender_type == "admin" and msg.sender_admin_id:
        name = "KRX TCG"
    elif msg.sender_type == "system":
        name = "システム"
    return schemas.InquiryMessageOut(
        id=msg.id,
        sender_type=msg.sender_type,
        message=msg.message,
        is_internal_note=msg.is_internal_note,
        template_id=msg.template_id,
        created_at=msg.created_at,
        sender_name=name,
    )


def _detail_out(inquiry: models.Inquiry) -> schemas.InquiryDetailOut:
    visible_messages = [m for m in inquiry.messages if not m.is_internal_note and not m.deleted_at]
    return schemas.InquiryDetailOut(
        id=inquiry.id,
        inquiry_number=inquiry.inquiry_number,
        category=inquiry.category,
        subject=inquiry.subject,
        related_order_number=inquiry.related_order_number,
        status=inquiry.status,
        priority=inquiry.priority,
        last_message_at=inquiry.last_message_at,
        customer_unread_count=inquiry.customer_unread_count or 0,
        created_at=inquiry.created_at,
        updated_at=inquiry.updated_at,
        reply_email=inquiry.reply_email,
        related_order_id=inquiry.related_order_id,
        related_product_id=inquiry.related_product_id,
        related_product_name=inquiry.related_product.name if inquiry.related_product else None,
        messages=[_message_out(m, inquiry) for m in visible_messages],
        attachments=[_attachment_out(a, user_id=inquiry.user_id) for a in (inquiry.attachments or [])],
    )


@router.get("/unread-count")
def unread_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(models.Inquiry)
        .filter(
            models.Inquiry.user_id == current_user.id,
            models.Inquiry.shop_id == 1,
            models.Inquiry.customer_unread_count > 0,
        )
        .count()
    )
    return {"count": count}


@router.get("/templates", response_model=list[schemas.InquiryTemplateOut])
def list_customer_templates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.InquiryTemplate)
        .filter(
            models.InquiryTemplate.shop_id == 1,
            models.InquiryTemplate.template_type == "customer",
            models.InquiryTemplate.is_active.is_(True),
        )
        .order_by(models.InquiryTemplate.sort_order, models.InquiryTemplate.id)
        .all()
    )


@router.post("/templates/{template_id}/preview", response_model=schemas.InquiryTemplatePreview)
def preview_customer_template(
    template_id: int,
    payload: schemas.InquiryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tpl = (
        db.query(models.InquiryTemplate)
        .filter(
            models.InquiryTemplate.id == template_id,
            models.InquiryTemplate.shop_id == 1,
            models.InquiryTemplate.template_type == "customer",
        )
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")

    order = None
    if payload.related_order_id:
        order = (
            db.query(models.Order)
            .filter(models.Order.id == payload.related_order_id, models.Order.user_id == current_user.id)
            .first()
        )
    product = None
    if payload.related_product_id:
        product = db.query(models.Card).filter(models.Card.id == payload.related_product_id).first()

    ctx = build_template_context(user=current_user, order=order, product=product)
    body, warnings = render_template_body(tpl.body, ctx)
    return schemas.InquiryTemplatePreview(body=body, warnings=warnings)


@router.get("/meta/categories")
def inquiry_categories():
    return [{"value": k, "label": INQUIRY_CATEGORY_LABELS[k]} for k in INQUIRY_CATEGORIES]


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    payload = verify_attachment_download_token(token)
    if payload.get("aid") != attachment_id:
        raise HTTPException(status_code=403, detail="ダウンロードリンクが無効です")

    row = (
        db.query(models.InquiryAttachment)
        .filter(models.InquiryAttachment.id == attachment_id, models.InquiryAttachment.shop_id == 1)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="添付ファイルが見つかりません")

    inquiry = db.query(models.Inquiry).filter(models.Inquiry.id == row.inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")

    is_admin = bool(payload.get("adm"))
    user_id = payload.get("uid")
    if is_admin:
        pass
    elif isinstance(user_id, int) and inquiry.user_id == user_id:
        pass
    else:
        raise HTTPException(status_code=403, detail="権限がありません")

    path = resolve_storage_path(row.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")

    return FileResponse(
        path,
        media_type=row.mime_type,
        filename=row.original_filename,
    )


@router.get("", response_model=list[schemas.InquiryListOut])
def list_inquiries(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Inquiry)
        .filter(models.Inquiry.user_id == current_user.id, models.Inquiry.shop_id == 1)
        .order_by(models.Inquiry.updated_at.desc())
        .all()
    )
    return [schemas.InquiryListOut.model_validate(r) for r in rows]


@router.post("", response_model=schemas.InquiryDetailOut, status_code=201)
def post_inquiry(
    payload: schemas.InquiryCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        inquiry = create_inquiry(
            db,
            user=current_user,
            category=payload.category,
            subject=payload.subject,
            message=payload.message,
            reply_email=payload.reply_email,
            related_order_id=payload.related_order_id,
            related_product_id=payload.related_product_id,
            template_id=payload.template_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    full = get_customer_inquiry(db, inquiry.id, current_user.id)
    first_msg = payload.message
    notify_inquiry_received(full, current_user)
    notify_admin_new_inquiry(full, current_user, first_msg)
    return _detail_out(full)


@router.get("/{inquiry_id}", response_model=schemas.InquiryDetailOut)
def get_inquiry(
    inquiry_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inquiry = get_customer_inquiry(db, inquiry_id, current_user.id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    mark_customer_read(db, inquiry, current_user)
    return _detail_out(inquiry)


@router.post("/{inquiry_id}/messages", response_model=schemas.InquiryMessageOut)
def post_message(
    inquiry_id: int,
    payload: schemas.InquiryMessageCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inquiry = get_customer_inquiry(db, inquiry_id, current_user.id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    try:
        msg = add_customer_message(db, inquiry, current_user, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    notify_admin_customer_reply(inquiry, current_user, payload.message)
    return _message_out(msg, inquiry)


@router.post("/{inquiry_id}/attachments", response_model=list[schemas.InquiryAttachmentOut])
async def upload_attachments(
    inquiry_id: int,
    files: list[UploadFile] = File(...),
    message_id: int | None = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inquiry = get_customer_inquiry(db, inquiry_id, current_user.id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    try:
        saved = await save_inquiry_attachments(
            db,
            inquiry,
            files,
            message_id=message_id,
            uploaded_by_type="customer",
            uploaded_by_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_attachment_out(a, user_id=current_user.id) for a in saved]


@router.post("/{inquiry_id}/read")
def post_read(
    inquiry_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inquiry = get_customer_inquiry(db, inquiry_id, current_user.id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="問い合わせが見つかりません")
    mark_customer_read(db, inquiry, current_user)
    return {"ok": True}
