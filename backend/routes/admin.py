import math
import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from database import get_db
from auth import get_current_admin
import models
import schemas
from routes.cards import _apply_card_search
from services.db_persist import PersistDep, safe_commit
from services.image_upload import save_uploaded_image
from services.shipping_rates import refresh_all_rates

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
    existing = db.query(models.Category).filter(models.Category.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="このスラッグは既に使用されています")
    category = models.Category(**payload.model_dump())
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
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="カテゴリーが見つかりません")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
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
    existing = db.query(models.Pack).filter(models.Pack.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="このスラッグは既に使用されています")
    pack = models.Pack(**payload.model_dump())
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

@router.get("/announcements", response_model=list[schemas.AnnouncementOut])
def admin_list_announcements(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    return (
        db.query(models.Announcement)
        .order_by(models.Announcement.priority.desc(), models.Announcement.created_at.desc())
        .all()
    )


@router.post("/announcements", response_model=schemas.AnnouncementOut, status_code=status.HTTP_201_CREATED)
def admin_create_announcement(
    payload: schemas.AnnouncementCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    announcement = models.Announcement(**payload.model_dump())
    db.add(announcement)
    safe_commit(db, action="カード作成")
    db.refresh(announcement)
    return announcement


@router.put("/announcements/{ann_id}", response_model=schemas.AnnouncementOut)
def admin_update_announcement(
    ann_id: int,
    payload: schemas.AnnouncementUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    ann = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ann, field, value)
    safe_commit(db, action="カード作成")
    db.refresh(ann)
    return ann


@router.delete("/announcements/{ann_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    ann = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="お知らせが見つかりません")
    db.delete(ann)
    safe_commit(db, action="カード作成")


# ──────────────────────── Orders ─────────────────────────────

@router.get("/users", response_model=list[schemas.UserOut])
def admin_list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.get("/orders", response_model=list[schemas.OrderOut])
def admin_list_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    query = db.query(models.Order).order_by(models.Order.created_at.desc())
    if status:
        try:
            order_status = models.OrderStatus(status)
            query = query.filter(models.Order.status == order_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効なステータスです")
    return query.all()


@router.put("/orders/{order_id}/status", response_model=schemas.OrderOut)
def admin_update_order_status(
    order_id: int,
    payload: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    order.status = payload.status
    safe_commit(db, action="注文ステータス更新")
    db.refresh(order)
    return order


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
