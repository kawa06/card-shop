import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_admin
import models
import schemas

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
        query = query.filter(models.Card.name.ilike(f"%{q}%"))
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
    db.commit()
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
    db.commit()
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
        db.commit()
        return None

    # カートからは削除
    db.query(models.CartItem).filter(models.CartItem.card_id == card_id).delete()
    
    db.delete(card)
    db.commit()


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
    db.commit()
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
    db.commit()
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
    db.commit()


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
    db.commit()
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
    db.commit()
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
    db.commit()


# ──────────────────────── Orders ─────────────────────────────

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
    db.commit()
    db.refresh(order)
    return order
