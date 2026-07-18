"""Inquiry business logic."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

import models
from services.inquiry_constants import DEFAULT_AUTO_REPLY_BODY
from services.inquiry_number import assign_inquiry_number
from services.inquiry_template_render import build_template_context, render_template_body
from services.inquiry_upload import read_inquiry_upload, save_inquiry_bytes


def get_inquiry_settings(db: Session) -> models.InquirySettings:
    row = db.query(models.InquirySettings).filter(models.InquirySettings.id == 1).first()
    if not row:
        from services.inquiry_seed import seed_inquiry_data

        seed_inquiry_data(db)
        row = db.query(models.InquirySettings).filter(models.InquirySettings.id == 1).first()
    return row


def _load_order(db: Session, order_id: int | None, user_id: int) -> models.Order | None:
    if not order_id:
        return None
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderItem.card))
        .filter(models.Order.id == order_id, models.Order.user_id == user_id)
        .first()
    )


def _load_product(db: Session, product_id: int | None) -> models.Card | None:
    if not product_id:
        return None
    return db.query(models.Card).filter(models.Card.id == product_id).first()


def _content_hash(user_id: int, subject: str, message: str) -> str:
    raw = f"{user_id}|{subject.strip()}|{message.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _check_rate_limit(db: Session, user_id: int) -> None:
    since = datetime.utcnow() - timedelta(minutes=1)
    count = (
        db.query(models.Inquiry)
        .filter(models.Inquiry.user_id == user_id, models.Inquiry.created_at >= since)
        .count()
    )
    if count >= 3:
        raise ValueError("送信が多すぎます。しばらくしてから再度お試しください")


def _record_status(db: Session, inquiry: models.Inquiry, new_status: str, changed_by: int | None, note: str | None = None) -> None:
    if inquiry.status == new_status:
        return
    db.add(
        models.InquiryStatusHistory(
            inquiry_id=inquiry.id,
            previous_status=inquiry.status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )
    )
    inquiry.status = new_status
    now = datetime.utcnow()
    inquiry.updated_at = now
    if new_status == "resolved":
        inquiry.resolved_at = now
    if new_status == "closed":
        inquiry.closed_at = now


def create_inquiry(
    db: Session,
    *,
    user: models.User,
    category: str,
    subject: str,
    message: str,
    reply_email: str | None = None,
    related_order_id: int | None = None,
    related_product_id: int | None = None,
    template_id: int | None = None,
) -> models.Inquiry:
    settings = get_inquiry_settings(db)
    if not settings.enabled:
        raise ValueError("現在、お問い合わせ機能は停止しています")

    subject = subject.strip()
    message = message.strip()
    if not subject or not message:
        raise ValueError("件名と問い合わせ内容は必須です")

    _check_rate_limit(db, user.id)
    digest = _content_hash(user.id, subject, message)
    recent = (
        db.query(models.Inquiry)
        .filter(
            models.Inquiry.user_id == user.id,
            models.Inquiry.content_hash == digest,
            models.Inquiry.created_at >= datetime.utcnow() - timedelta(minutes=5),
        )
        .first()
    )
    if recent:
        raise ValueError("同じ内容の問い合わせが送信済みです")

    order = _load_order(db, related_order_id, user.id)
    if related_order_id and not order:
        raise ValueError("関連注文が見つかりません")

    product = _load_product(db, related_product_id)
    if related_product_id and not product:
        raise ValueError("関連商品が見つかりません")

    now = datetime.utcnow()
    inquiry = models.Inquiry(
        inquiry_number=assign_inquiry_number(db),
        shop_id=1,
        user_id=user.id,
        reply_email=(reply_email or user.email).strip(),
        category=category,
        subject=subject,
        related_order_id=order.id if order else None,
        related_order_number=order.order_number if order else None,
        related_product_id=product.id if product else None,
        status="waiting_admin",
        last_message_at=now,
        customer_last_read_at=now,
        admin_unread_count=1,
        content_hash=digest,
        created_at=now,
        updated_at=now,
    )
    db.add(inquiry)
    db.flush()

    db.add(
        models.InquiryMessage(
            inquiry_id=inquiry.id,
            shop_id=1,
            sender_type="customer",
            sender_user_id=user.id,
            message=message,
            template_id=template_id,
            created_at=now,
        )
    )

    if settings.auto_reply_enabled:
        auto_body = settings.auto_reply_body or DEFAULT_AUTO_REPLY_BODY
        ctx = build_template_context(inquiry=inquiry, user=user, order=order, product=product)
        rendered, _ = render_template_body(auto_body, ctx)
        db.add(
            models.InquiryMessage(
                inquiry_id=inquiry.id,
                shop_id=1,
                sender_type="system",
                message=rendered,
                created_at=now,
            )
        )

    db.add(
        models.InquiryStatusHistory(
            inquiry_id=inquiry.id,
            previous_status=None,
            new_status="waiting_admin",
            changed_by=user.id,
            note="created",
        )
    )
    db.commit()
    db.refresh(inquiry)
    return inquiry


def add_customer_message(
    db: Session,
    inquiry: models.Inquiry,
    user: models.User,
    message: str,
) -> models.InquiryMessage:
    if inquiry.user_id != user.id:
        raise PermissionError("権限がありません")
    if inquiry.status == "closed":
        settings = get_inquiry_settings(db)
        if not settings.allow_reopen_resolved:
            raise ValueError("この問い合わせは終了しています")
        _record_status(db, inquiry, "waiting_admin", user.id, note="reopened by customer")

    message = message.strip()
    if not message:
        raise ValueError("メッセージを入力してください")

    now = datetime.utcnow()
    msg = models.InquiryMessage(
        inquiry_id=inquiry.id,
        shop_id=1,
        sender_type="customer",
        sender_user_id=user.id,
        message=message,
        created_at=now,
    )
    db.add(msg)
    inquiry.last_message_at = now
    inquiry.updated_at = now
    inquiry.customer_last_read_at = now
    inquiry.admin_unread_count = (inquiry.admin_unread_count or 0) + 1
    _record_status(db, inquiry, "waiting_admin", user.id)
    db.commit()
    db.refresh(msg)
    return msg


def add_admin_reply(
    db: Session,
    inquiry: models.Inquiry,
    admin: models.User,
    message: str,
    *,
    is_internal_note: bool = False,
    template_id: int | None = None,
    new_status: str | None = None,
    assigned_admin_id: int | None = None,
) -> models.InquiryMessage:
    message = message.strip()
    if not message:
        raise ValueError("返信内容を入力してください")

    now = datetime.utcnow()
    msg = models.InquiryMessage(
        inquiry_id=inquiry.id,
        shop_id=1,
        sender_type="admin",
        sender_admin_id=admin.id,
        message=message,
        is_internal_note=is_internal_note,
        template_id=template_id,
        created_at=now,
    )
    db.add(msg)

    if assigned_admin_id is not None:
        inquiry.assigned_admin_id = assigned_admin_id

    if not is_internal_note:
        inquiry.last_message_at = now
        inquiry.admin_last_read_at = now
        inquiry.admin_unread_count = 0
        inquiry.customer_unread_count = (inquiry.customer_unread_count or 0) + 1
        status = new_status or "waiting_customer"
        _record_status(db, inquiry, status, admin.id)
    else:
        inquiry.updated_at = now

    db.commit()
    db.refresh(msg)
    return msg


def mark_customer_read(db: Session, inquiry: models.Inquiry, user: models.User) -> None:
    if inquiry.user_id != user.id:
        raise PermissionError("権限がありません")
    inquiry.customer_last_read_at = datetime.utcnow()
    inquiry.customer_unread_count = 0
    db.commit()


def mark_admin_read(db: Session, inquiry: models.Inquiry) -> None:
    inquiry.admin_last_read_at = datetime.utcnow()
    inquiry.admin_unread_count = 0
    db.commit()


def get_customer_inquiry(db: Session, inquiry_id: int, user_id: int) -> models.Inquiry | None:
    return (
        db.query(models.Inquiry)
        .options(
            joinedload(models.Inquiry.messages),
            joinedload(models.Inquiry.attachments),
            joinedload(models.Inquiry.user),
            joinedload(models.Inquiry.related_order).joinedload(models.Order.items).joinedload(models.OrderItem.card),
            joinedload(models.Inquiry.related_product),
        )
        .filter(models.Inquiry.id == inquiry_id, models.Inquiry.user_id == user_id, models.Inquiry.shop_id == 1)
        .first()
    )


def get_admin_inquiry(db: Session, inquiry_id: int) -> models.Inquiry | None:
    return (
        db.query(models.Inquiry)
        .options(
            joinedload(models.Inquiry.messages),
            joinedload(models.Inquiry.attachments),
            joinedload(models.Inquiry.user),
            joinedload(models.Inquiry.related_order).joinedload(models.Order.items).joinedload(models.OrderItem.card),
            joinedload(models.Inquiry.related_product),
            joinedload(models.Inquiry.assigned_admin),
        )
        .filter(models.Inquiry.id == inquiry_id, models.Inquiry.shop_id == 1)
        .first()
    )


def _first_customer_message_id(inquiry: models.Inquiry) -> int | None:
    for msg in inquiry.messages or []:
        if msg.sender_type == "customer" and not msg.deleted_at:
            return msg.id
    return None


def count_inquiry_attachments(db: Session, inquiry_id: int) -> int:
    return (
        db.query(models.InquiryAttachment)
        .filter(models.InquiryAttachment.inquiry_id == inquiry_id)
        .count()
    )


async def save_inquiry_attachments(
    db: Session,
    inquiry: models.Inquiry,
    files: list,
    *,
    message_id: int | None,
    uploaded_by_type: str,
    uploaded_by_id: int,
) -> list[models.InquiryAttachment]:
    settings_row = get_inquiry_settings(db)
    if not settings_row.attachments_enabled:
        raise ValueError("現在、画像添付は利用できません")

    if not files:
        raise ValueError("ファイルが選択されていません")

    current_count = count_inquiry_attachments(db, inquiry.id)
    if current_count + len(files) > settings_row.max_attachments:
        raise ValueError(f"添付は最大{settings_row.max_attachments}件までです")

    resolved_message_id = message_id
    if resolved_message_id is None:
        resolved_message_id = _first_customer_message_id(inquiry)
    if resolved_message_id is None:
        raise ValueError("添付先のメッセージが見つかりません")

    msg = (
        db.query(models.InquiryMessage)
        .filter(
            models.InquiryMessage.id == resolved_message_id,
            models.InquiryMessage.inquiry_id == inquiry.id,
        )
        .first()
    )
    if not msg:
        raise ValueError("添付先のメッセージが見つかりません")

    saved: list[models.InquiryAttachment] = []
    now = datetime.utcnow()
    for file in files:
        data, content_type, original = await read_inquiry_upload(
            file,
            max_bytes=settings_row.max_attachment_bytes,
        )
        storage_path = save_inquiry_bytes(data, content_type)
        row = models.InquiryAttachment(
            inquiry_id=inquiry.id,
            message_id=resolved_message_id,
            shop_id=1,
            storage_path=storage_path,
            original_filename=original,
            mime_type=content_type,
            file_size=len(data),
            uploaded_by_type=uploaded_by_type,
            uploaded_by_id=uploaded_by_id,
            created_at=now,
        )
        db.add(row)
        saved.append(row)

    inquiry.updated_at = now
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved
