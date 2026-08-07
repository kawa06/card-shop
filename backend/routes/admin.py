import math
import csv
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from database import get_db
from auth import get_current_admin
import models
import schemas
import schemas_email
from routes.cards import _apply_card_search
from services.db_persist import PersistDep, safe_commit
from services.image_upload import save_uploaded_image
from services.shipping_rates import refresh_all_rates
from services.order_checkout import cancel_unpaid_order, extend_payment_deadline, fulfill_order_inventory
from services.order_emails import send_purchase_confirmation_email, send_shipping_completion_email
from services.invoice_config import get_invoice_config, update_invoice_settings
from services.barcode_render import (
    ensure_order_barcode,
    get_admin_dashboard_stats,
    list_order_shipment_logs,
    render_code128_svg,
    resolve_order_by_scan_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[PersistDep],
)


@router.post("/uploads")
async def admin_upload_image(
    file: UploadFile = File(...),
    _: models.User = Depends(get_current_admin),
):
    url = await save_uploaded_image(file)
    return {"url": url}


# ──────────────────────── Cards ──────────────────────────────

@router.get("/cards", response_model=schemas.PaginatedCards)
def admin_list_cards(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    query = db.query(models.Card)
    if q:
        query = _apply_card_search(query, q)
    if is_active is not None:
        query = query.filter(models.Card.is_active == is_active)
    query = query.order_by(models.Card.created_at.desc())

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total > 0 else 1,
    }


@router.post("/cards", response_model=schemas.CardOut, status_code=status.HTTP_201_CREATED)
def admin_create_card(
    payload: schemas.CardCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    card = models.Card(**payload.model_dump())
    db.add(card)
    safe_commit(db, action="カード作成")
    db.refresh(card)
    return card


@router.get("/cards/{card_id}", response_model=schemas.CardOut)
def admin_get_card(
    card_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    card = db.query(models.Card).filter(models.Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")
    return card


@router.put("/cards/{card_id}", response_model=schemas.CardOut)
def admin_update_card(
    card_id: int,
    payload: schemas.CardUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    card = db.query(models.Card).filter(models.Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    safe_commit(db, action="カード作成")
    db.refresh(card)
    return card


@router.patch("/cards/{card_id}/shipping-methods", response_model=schemas.CardOut)
def admin_update_card_shipping_methods(
    card_id: int,
    payload: schemas.CardShippingMethodsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    card = db.query(models.Card).filter(models.Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")
    card.allowed_shipping_methods = payload.allowed_shipping_methods
    safe_commit(db, action="カード作成")
    db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    card = db.query(models.Card).filter(models.Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")
    
    # 注文履歴(order_items)に関連付けられている場合は物理削除せずに非表示にする
    has_orders = db.query(models.OrderItem).filter(models.OrderItem.card_id == card_id).first()
    if has_orders:
        card.is_active = False
        safe_commit(db, action="カード作成")
        return None

    # カートからは削除
    db.query(models.CartItem).filter(models.CartItem.card_id == card_id).delete()
    
    db.delete(card)
    safe_commit(db, action="カード作成")


# ──────────────────────── Categories ─────────────────────────

@router.get("/categories", response_model=list[schemas.CategoryOut])
def admin_list_categories(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    return db.query(models.Category).order_by(models.Category.sort_order).all()


@router.post("/categories", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def admin_create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from services.localize_name import fill_name_en

    existing = db.query(models.Category).filter(models.Category.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="このスラッグは既に使用されています")
    data = payload.model_dump()
    data["name_en"] = fill_name_en(db, data.get("name") or "", data.get("name_en"))
    category = models.Category(**data)
    db.add(category)
    safe_commit(db, action="カード作成")
    db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=schemas.CategoryOut)
def admin_update_category(
    category_id: int,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from services.localize_name import fill_name_en

    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリーが見つかりません")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(category, field, value)
    # Re-translate when Japanese name changes and English was not explicitly set.
    if "name" in updates and "name_en" not in updates:
        category.name_en = fill_name_en(db, category.name, None)
    elif not (category.name_en or "").strip():
        category.name_en = fill_name_en(db, category.name, None)
    safe_commit(db, action="カード作成")
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリーが見つかりません")
    db.delete(category)
    safe_commit(db, action="カード作成")


# ──────────────────────── Packs ──────────────────────────────

@router.get("/packs", response_model=list[schemas.PackOut])
def admin_list_packs(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    return db.query(models.Pack).order_by(models.Pack.sort_order, models.Pack.name).all()


@router.post("/packs", response_model=schemas.PackOut, status_code=status.HTTP_201_CREATED)
def admin_create_pack(
    payload: schemas.PackCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from services.localize_name import fill_name_en

    existing = db.query(models.Pack).filter(models.Pack.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="このスラッグは既に使用されています")
    data = payload.model_dump()
    data["name_en"] = fill_name_en(db, data.get("name") or "", data.get("name_en"))
    pack = models.Pack(**data)
    db.add(pack)
    safe_commit(db, action="カード作成")
    db.refresh(pack)
    return pack


@router.put("/packs/{pack_id}", response_model=schemas.PackOut)
def admin_update_pack(
    pack_id: int,
    payload: schemas.PackUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from services.localize_name import fill_name_en

    pack = db.query(models.Pack).filter(models.Pack.id == pack_id).first()
    if not pack:
        raise HTTPException(status_code=404, detail="パックが見つかりません")
    updates = payload.model_dump(exclude_unset=True)
    if "slug" in updates and updates["slug"] != pack.slug:
        existing = db.query(models.Pack).filter(
            models.Pack.slug == updates["slug"],
            models.Pack.id != pack_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="このスラッグは既に使用されています")
    for field, value in updates.items():
        setattr(pack, field, value)
    if "name" in updates and "name_en" not in updates:
        pack.name_en = fill_name_en(db, pack.name, None)
    elif not (pack.name_en or "").strip():
        pack.name_en = fill_name_en(db, pack.name, None)
    safe_commit(db, action="パック更新")
    db.refresh(pack)
    return pack


@router.delete("/packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_pack(
    pack_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    pack = db.query(models.Pack).filter(models.Pack.id == pack_id).first()
    if not pack:
        raise HTTPException(status_code=404, detail="パックが見つかりません")
    # カードは削除せず、パック紐付けのみ解除
    db.query(models.Card).filter(models.Card.pack_id == pack_id).update(
        {models.Card.pack_id: None},
        synchronize_session=False,
    )
    db.delete(pack)
    safe_commit(db, action="カード作成")


# ──────────────────────── Announcements ──────────────────────

def _normalize_create_payload(payload: schemas.AnnouncementCreate) -> dict:
    title_ja = (payload.title_ja or payload.title or "").strip()
    title_en = (payload.title_en or "").strip()
    content_ja = payload.content_ja or payload.content or ""
    content_en = payload.content_en or ""
    status_value = payload.status
    if status_value is None:
        status_value = "published" if payload.is_active else "draft"
    return {
        "title_ja": title_ja,
        "title_en": title_en,
        "content_ja": content_ja,
        "content_en": content_en,
        "status_value": status_value,
        "publish_at": payload.publish_at,
        "expire_at": payload.expire_at,
        "thumbnail": payload.thumbnail,
        "priority": payload.priority,
        "image_urls": payload.image_urls,
        "show_on_site": payload.show_on_site,
        "send_email": payload.send_email,
        "email_template_key": payload.email_template_key,
        "email_audience_key": payload.email_audience_key,
        "email_audience_params": payload.email_audience_params,
    }


def _serialize_admin(row: models.Announcement) -> schemas.AnnouncementAdminOut:
    return schemas.AnnouncementAdminOut(
        id=row.id,
        title=row.title,
        content=row.content,
        title_ja=row.title_ja or row.title,
        title_en=row.title_en or row.title,
        content_ja=row.content_ja or row.content,
        content_en=row.content_en or row.content,
        status=row.status or ("published" if row.is_active else "draft"),
        is_active=row.is_active,
        priority=row.priority or 0,
        publish_at=row.publish_at,
        expire_at=row.expire_at,
        thumbnail=row.thumbnail,
        show_on_site=getattr(row, "show_on_site", True),
        send_email=getattr(row, "send_email", False),
        email_template_key=getattr(row, "email_template_key", None),
        email_audience_key=getattr(row, "email_audience_key", None),
        email_audience_params_json=getattr(row, "email_audience_params_json", None),
        email_campaign_id=getattr(row, "email_campaign_id", None),
        email_send_status=getattr(row, "email_send_status", "none") or "none",
        email_scheduled_at=getattr(row, "email_scheduled_at", None),
        created_at=row.created_at,
        updated_at=row.updated_at,
        images=[
            schemas.AnnouncementImageOut.model_validate(img)
            for img in sorted(row.images or [], key=lambda item: item.sort_order)
        ],
    )


@router.get("/announcements", response_model=list[schemas.AnnouncementAdminOut])
def admin_list_announcements(
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from services.announcements import search_admin_announcements

    rows = search_admin_announcements(db, q=q)
    return [_serialize_admin(row) for row in rows]


@router.post("/announcements/upload-image")
async def admin_upload_announcement_image(
    file: UploadFile = File(...),
    _: models.User = Depends(get_current_admin),
):
    return {"url": await save_uploaded_image(file)}


@router.get("/announcements/{ann_id}", response_model=schemas.AnnouncementAdminOut)
def admin_get_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from sqlalchemy.orm import joinedload

    ann = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .filter(models.Announcement.id == ann_id)
        .first()
    )
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")
    return _serialize_admin(ann)


@router.post("/announcements", response_model=schemas.AnnouncementAdminOut, status_code=status.HTTP_201_CREATED)
def admin_create_announcement(
    payload: schemas.AnnouncementCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    from services.announcements import create_announcement

    fields = _normalize_create_payload(payload)
    announcement = create_announcement(db, **fields)
    safe_commit(db, action="お知らせ作成")
    db.refresh(announcement)
    logger.info("admin=%s created announcement id=%s", admin.id, announcement.id)
    return _serialize_admin(announcement)


@router.put("/announcements/{ann_id}", response_model=schemas.AnnouncementAdminOut)
def admin_update_announcement(
    ann_id: int,
    payload: schemas.AnnouncementUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    from sqlalchemy.orm import joinedload
    from services.announcements import update_announcement

    ann = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .filter(models.Announcement.id == ann_id)
        .first()
    )
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")

    data = payload.model_dump(exclude_unset=True)
    status_value = data.pop("status", None)
    if status_value is None and "is_active" in data:
        status_value = "published" if data.pop("is_active") else "draft"
    elif "is_active" in data:
        data.pop("is_active")

    if "title" in data and "title_ja" not in data:
        data["title_ja"] = data.pop("title")
    if "content" in data and "content_ja" not in data:
        data["content_ja"] = data.pop("content")
    else:
        data.pop("title", None)
        data.pop("content", None)

    update_announcement(
        db,
        ann,
        status_value=status_value,
        **data,
    )
    safe_commit(db, action="お知らせ更新")
    db.refresh(ann)
    logger.info("admin=%s updated announcement id=%s", admin.id, ann.id)
    return _serialize_admin(ann)


@router.delete("/announcements/{ann_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    from services.announcements import delete_announcement

    ann = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")
    delete_announcement(db, ann)
    safe_commit(db, action="お知らせ削除")
    logger.info("admin=%s deleted announcement id=%s", admin.id, ann_id)


@router.get("/announcements/{ann_id}/email-preview", response_model=schemas_email.AnnouncementEmailPreviewOut)
def admin_announcement_email_preview(
    ann_id: int,
    audience_key: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from sqlalchemy.orm import joinedload
    from services.email_broadcast import build_announcement_email_preview

    ann = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .filter(models.Announcement.id == ann_id)
        .first()
    )
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")
    if not ann.send_email:
        raise HTTPException(status_code=400, detail="このお知らせはメール配信が有効になっていません")
    return build_announcement_email_preview(db, ann, audience_key=audience_key)


@router.post("/announcements/{ann_id}/send-email")
def admin_announcement_send_email(
    ann_id: int,
    payload: schemas_email.AnnouncementEmailSendIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    from services.email_broadcast import create_announcement_campaign
    from services.email_rate_limit import check_rate_limit

    if not payload.confirm:
        raise HTTPException(status_code=400, detail="送信前の確認が必要です（confirm=true）")

    rl = check_rate_limit(str(admin.id), limit_key="campaign_confirm")
    if not rl.allowed:
        raise HTTPException(status_code=429, detail="送信操作の上限に達しました。しばらく待ってから再試行してください。")

    ann = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")

    try:
        campaign = create_announcement_campaign(
            db,
            ann,
            admin_user_id=admin.id,
            send_mode=payload.send_mode,
            scheduled_at=payload.scheduled_at,
            idempotency_key=payload.idempotency_key,
            audience_key=payload.audience_key,
            audience_params=payload.audience_params or None,
            template_key=payload.template_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    safe_commit(db, action="お知らせメール配信")
    if payload.send_mode == "scheduled":
        return {
            "message": "メール配信を予約しました",
            "campaign_id": campaign.id,
            "scheduled_at": campaign.scheduled_at,
        }
    return {
        "message": "メール配信を開始しました",
        "campaign_id": campaign.id,
        "success_count": campaign.success_count,
        "failed_count": campaign.failed_count,
    }


# ──────────────────────── Orders ─────────────────────────────

@router.get("/dashboard/stats", response_model=schemas.AdminDashboardStatsOut)
def admin_dashboard_stats_route(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    from services.barcode_render import get_admin_dashboard_stats

    return schemas.AdminDashboardStatsOut(**get_admin_dashboard_stats(db))


_SHIPPING_TO_LEGACY_STATUS = {
    "unshipped": models.OrderStatus.pending,
    "preparing": models.OrderStatus.processing,
    "packing": models.OrderStatus.processing,
    "shipped": models.OrderStatus.shipped,
    "in_transit": models.OrderStatus.shipped,
    "delivered": models.OrderStatus.delivered,
    "received": models.OrderStatus.delivered,
    "cancelled": models.OrderStatus.cancelled,
}


def _order_query_options():
    return (
        joinedload(models.Order.items).joinedload(models.OrderItem.card),
        joinedload(models.Order.user),
    )


def _to_admin_order(order: models.Order) -> schemas.AdminOrderOut:
    base = schemas.OrderOut.model_validate(order)
    user = order.user
    return schemas.AdminOrderOut(
        **base.model_dump(),
        buyer_name=user.name if user else None,
        buyer_email=user.email if user else None,
    )


def _to_admin_order_detail(order: models.Order) -> schemas.AdminOrderDetailOut:
    base = _to_admin_order(order)
    return schemas.AdminOrderDetailOut(
        **base.model_dump(),
        stripe_checkout_session_id=order.stripe_checkout_session_id,
    )


def _sync_legacy_status_from_shipping(order: models.Order) -> None:
    target = _SHIPPING_TO_LEGACY_STATUS.get(order.shipping_status or "")
    if target is not None:
        order.status = target


@router.get("/users", response_model=list[schemas.UserOut])
def admin_list_users(
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    query = db.query(models.User)
    if q:
        term = q.strip()
        if term:
            query = query.filter(
                or_(
                    models.User.email.ilike(f"%{term}%"),
                    models.User.name.ilike(f"%{term}%"),
                )
            )
    return query.order_by(models.User.created_at.desc()).all()


@router.get("/orders", response_model=list[schemas.AdminOrderOut])
def admin_list_orders(
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    shipping_status: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    query = (
        db.query(models.Order)
        .options(*_order_query_options())
        .order_by(models.Order.created_at.desc())
    )
    if status:
        try:
            order_status = models.OrderStatus(status)
            query = query.filter(models.Order.status == order_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効なステータスです")
    if payment_status:
        query = query.filter(models.Order.payment_status == payment_status)
    if shipping_status:
        query = query.filter(models.Order.shipping_status == shipping_status)
    if q:
        term = q.strip()
        if term:
            query = query.join(models.User)
            filters = [
                models.Order.order_number.ilike(f"%{term}%"),
                models.Order.tracking_number.ilike(f"%{term}%"),
                models.User.name.ilike(f"%{term}%"),
                models.User.email.ilike(f"%{term}%"),
            ]
            if term.isdigit():
                filters.append(models.Order.id == int(term))
            query = query.filter(or_(*filters))
    orders = query.all()
    return [_to_admin_order(o) for o in orders]


@router.get("/orders/{order_id}", response_model=schemas.AdminOrderDetailOut)
def admin_get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = (
        db.query(models.Order)
        .options(*_order_query_options())
        .filter(models.Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    return _to_admin_order_detail(order)


@router.put("/orders/{order_id}/status", response_model=schemas.AdminOrderOut)
def admin_update_order_status(
    order_id: int,
    payload: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = (
        db.query(models.Order)
        .options(*_order_query_options())
        .filter(models.Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    order.status = payload.status
    safe_commit(db, action="注文ステータス更新")
    db.refresh(order)
    return _to_admin_order(order)


@router.patch("/orders/{order_id}/shipping", response_model=schemas.AdminOrderOut)
def admin_update_order_shipping(
    order_id: int,
    payload: schemas.OrderShippingUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_current_admin),
):
    order = (
        db.query(models.Order)
        .options(*_order_query_options())
        .filter(models.Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")

    data = payload.model_dump(exclude_unset=True)
    if "shipping_status" in data and data["shipping_status"]:
        allowed = {s.value for s in models.ShippingStatus}
        if data["shipping_status"] not in allowed:
            raise HTTPException(status_code=400, detail="無効な発送ステータスです")

    prev_status = order.shipping_status
    prev_tracking = order.tracking_number

    for field, value in data.items():
        setattr(order, field, value)

    if order.shipping_status == "shipped" and order.shipped_at is None:
        order.shipped_at = datetime.utcnow()

    if order.shipping_status in ("packing", "preparing") and prev_status == "unshipped":
        from services.barcode_render import append_order_shipment_log, ensure_order_barcode

        ensure_order_barcode(db, order=order)

    status_changed = prev_status != order.shipping_status
    tracking_changed = prev_tracking != order.tracking_number
    if status_changed or tracking_changed or data:
        from services.barcode_render import append_order_shipment_log

        append_order_shipment_log(
            db,
            order=order,
            event_type="shipping_updated",
            from_shipping_status=prev_status,
            to_shipping_status=order.shipping_status,
            tracking_number=order.tracking_number,
            shipping_carrier=order.shipping_carrier,
            admin_user_id=admin_user.id,
        )

    _sync_legacy_status_from_shipping(order)
    safe_commit(db, action="発送情報更新")

    if status_changed and order.shipping_status == "shipped":
        try:
            from services.admin_notify_emails import send_admin_notify_event

            send_admin_notify_event(
                db,
                "admin_notify_shipping_completed",
                reference_type="order",
                reference_id=str(order.id),
                in_app_title="発送完了",
                in_app_body=f"注文 {order.order_number or order.id} を発送しました",
            )
            safe_commit(db, action="発送完了通知")
        except Exception:
            logger.exception("Failed to send shipping completed admin notify for order %s", order.id)

    db.refresh(order)
    return _to_admin_order(order)


@router.post("/orders/{order_id}/confirm-payment", response_model=schemas.OrderOut)
def admin_confirm_payment(
    order_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    if order.payment_status != "awaiting_payment":
        raise HTTPException(status_code=400, detail="入金待ちの注文のみ入金確認できます")
    return fulfill_order_inventory(db, order_id)


@router.post("/orders/{order_id}/send-purchase-email", response_model=schemas.OrderOut)
def admin_send_purchase_email(
    order_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    """Manually send purchase confirmation (fallback if Stripe auto-send failed)."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    if order.payment_status != "paid":
        raise HTTPException(status_code=400, detail="支払い済みの注文のみ送信できます")
    ok, err = send_purchase_confirmation_email(db, order_id, force=force)
    if not ok:
        raise HTTPException(status_code=502, detail=err or "メール送信に失敗しました")
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/send-shipping-email", response_model=schemas.AdminOrderOut)
def admin_send_shipping_email(
    order_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    """Send shipping completion email with tracking info (requires tracking number)."""
    order = (
        db.query(models.Order)
        .options(*_order_query_options())
        .filter(models.Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    if order.payment_status != "paid":
        raise HTTPException(status_code=400, detail="支払い済みの注文のみ送信できます")
    ok, err = send_shipping_completion_email(db, order_id, force=force)
    if not ok:
        status_code = 400 if err and "追跡番号" in err else 502
        raise HTTPException(status_code=status_code, detail=err or "メール送信に失敗しました")
    db.refresh(order)
    return _to_admin_order(order)


@router.post("/orders/{order_id}/cancel", response_model=schemas.OrderOut)
def admin_cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="支払い済みの注文はキャンセルできません")
    cancel_unpaid_order(db, order, as_expired=False)
    db.refresh(order)
    return order


@router.patch("/orders/{order_id}/payment-deadline", response_model=schemas.OrderOut)
def admin_extend_payment_deadline(
    order_id: int,
    payload: schemas.PaymentDeadlineExtend,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    return extend_payment_deadline(
        db,
        order,
        hours=payload.hours,
        new_deadline=payload.payment_deadline,
    )


def _format_order_datetime_jst(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jst = timezone(timedelta(hours=9))
    return dt.astimezone(jst).strftime("%Y/%m/%d %H:%M")


def _order_product_names(order: models.Order) -> str:
    parts = []
    for item in order.items:
        name = item.card.name if item.card else f"商品#{item.card_id}"
        parts.append(f"{name} x{item.quantity}")
    return " / ".join(parts)


def _serialize_click_post_order(order: models.Order) -> schemas.AdminClickPostOrderOut:
    buyer = order.user.name if order.user else ""
    return schemas.AdminClickPostOrderOut(
        id=order.id,
        buyer_name=buyer,
        postal_code=order.postal_code,
        region=order.region,
        city=order.city,
        address_line1=order.address_line1,
        address_line2=order.address_line2,
        product_names=_order_product_names(order),
        created_at=order.created_at,
        payment_status=order.payment_status,
        click_post_csv_exported_at=order.click_post_csv_exported_at,
    )


@router.get("/orders/click-post", response_model=list[schemas.AdminClickPostOrderOut])
def admin_list_click_post_orders(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    orders = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.user),
            joinedload(models.Order.items).joinedload(models.OrderItem.card),
        )
        .filter(models.Order.shipping_method == "click_post")
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return [_serialize_click_post_order(o) for o in orders]


@router.post("/orders/click-post/export")
def admin_export_click_post_csv(
    payload: schemas.ClickPostExportRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    if not payload.order_ids:
        raise HTTPException(status_code=400, detail="出力する注文を選択してください")

    orders = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.user),
            joinedload(models.Order.items).joinedload(models.OrderItem.card),
        )
        .filter(
            models.Order.id.in_(payload.order_ids),
            models.Order.shipping_method == "click_post",
        )
        .order_by(models.Order.created_at.asc())
        .all()
    )
    if not orders:
        raise HTTPException(status_code=404, detail="対象のクリックポスト注文が見つかりません")

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([
        "注文番号",
        "購入者氏名",
        "郵便番号",
        "都道府県",
        "市区町村",
        "番地",
        "建物名",
        "商品名",
        "注文日時",
    ])
    for order in orders:
        writer.writerow([
            order.id,
            order.user.name if order.user else "",
            order.postal_code or "",
            order.region or "",
            order.city or "",
            order.address_line1 or "",
            order.address_line2 or "",
            _order_product_names(order),
            _format_order_datetime_jst(order.created_at),
        ])
        if payload.mark_exported:
            order.click_post_csv_exported_at = datetime.utcnow()

    safe_commit(db, action="クリックポストCSV出力")

    filename = f"click_post_orders_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    content = output.getvalue()
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ──────────────────────── Shipping ───────────────────────────

@router.patch("/shipping-rates/{method_code}", response_model=schemas.ShippingRateOut)
def admin_update_shipping_rate(
    method_code: str,
    rate_update: schemas.ShippingRateUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    db_rate = db.query(models.ShippingRate).filter(
        models.ShippingRate.method_code == method_code
    ).first()
    if not db_rate:
        raise HTTPException(status_code=404, detail="Shipping rate not found")

    update_data = rate_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_rate, key, value)

    safe_commit(db, action="送料更新")
    db.refresh(db_rate)
    return db_rate


@router.post("/shipping-rates/refresh")
async def admin_refresh_shipping_rates(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    await refresh_all_rates(db)
    return {"message": "Shipping rates refreshed"}


# ──────────────────────── Shop settings ───────────────────────────

@router.get("/shop/invoice-settings", response_model=schemas.InvoiceConfigOut)
def admin_get_invoice_settings(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    return get_invoice_config(db)


@router.put("/shop/invoice-settings", response_model=schemas.InvoiceConfigOut)
def admin_update_invoice_settings(
    payload: schemas.InvoiceSettingsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    try:
        return update_invoice_settings(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/orders/{order_id}/shipment-logs", response_model=list[schemas.OrderShipmentLogOut])
def admin_order_shipment_logs(
    order_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    return list_order_shipment_logs(db, order_id)


@router.get("/orders/{order_id}/barcode", response_model=schemas.OrderBarcodeOut)
def admin_get_order_barcode(
    order_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    row = ensure_order_barcode(db, order=order)
    safe_commit(db, action="order barcode")
    return row


@router.get("/orders/{order_id}/barcode.svg")
def admin_order_barcode_svg(
    order_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    barcode = ensure_order_barcode(db, order=order)
    safe_commit(db, action="order barcode svg")
    svg = render_code128_svg(barcode.scan_token, aria_label="order barcode")
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store, private"},
    )


@router.post("/orders/scan", response_model=schemas.OrderScanOut)
def admin_scan_order(
    payload: schemas.OrderScanIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    resolved = resolve_order_by_scan_code(db, payload.code)
    if not resolved:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    if not resolved.user:
        resolved = (
            db.query(models.Order)
            .options(joinedload(models.Order.user))
            .filter(models.Order.id == resolved.id)
            .first()
        )
    user = resolved.user if resolved else None
    return schemas.OrderScanOut(
        order_id=resolved.id,
        order_number=resolved.order_number,
        shipping_status=resolved.shipping_status,
        tracking_number=resolved.tracking_number,
        buyer_name=user.name if user else None,
        detail_url=f"/admin/orders/{resolved.id}",
    )
