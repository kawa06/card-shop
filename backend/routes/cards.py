import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

router = APIRouter(prefix="/api", tags=["cards"])


def _apply_card_search(query, q: str):
    pattern = f"%{q}%"
    return query.outerjoin(models.Pack, models.Card.pack_id == models.Pack.id).filter(
        or_(
            models.Card.name.ilike(pattern),
            models.Card.name_en.ilike(pattern),
            models.Pack.name.ilike(pattern),
        )
    )


@router.get("/cards", response_model=schemas.PaginatedCards)
def list_cards(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    pack_id: Optional[int] = None,
    rarity: Optional[str] = None,
    set_name: Optional[str] = None,
    condition: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    q: Optional[str] = None,
    sort: str = Query("created_at_desc", regex="^(price_asc|price_desc|name_asc|created_at_desc)$"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Card).filter(models.Card.is_active == True)

    if category_id is not None:
        query = query.filter(models.Card.category_id == category_id)
    if pack_id is not None:
        query = query.filter(models.Card.pack_id == pack_id)
    if rarity:
        query = query.filter(models.Card.rarity == rarity)
    if set_name:
        query = query.filter(models.Card.set_name == set_name)
    if condition:
        query = query.filter(models.Card.condition == condition)
    if min_price is not None:
        query = query.filter(models.Card.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Card.price <= max_price)
    if q:
        query = _apply_card_search(query, q)

    sort_map = {
        "price_asc": models.Card.price.asc(),
        "price_desc": models.Card.price.desc(),
        "name_asc": models.Card.name.asc(),
        "created_at_desc": models.Card.created_at.desc(),
    }
    query = query.order_by(sort_map[sort])

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    from services.localize_name import backfill_name_en_fields

    backfill_name_en_fields(
        db,
        [c.category for c in items if c.category] + [c.pack for c in items if c.pack],
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total > 0 else 1,
    }


@router.get("/cards/{card_id}", response_model=schemas.CardOut)
def get_card(card_id: int, db: Session = Depends(get_db)):
    from services.localize_name import backfill_name_en_fields

    card = db.query(models.Card).filter(
        models.Card.id == card_id,
        models.Card.is_active == True,
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")
    backfill_name_en_fields(
        db,
        [x for x in (card.category, card.pack) if x is not None],
    )
    return card


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    from services.localize_name import backfill_name_en_fields

    # Return only root categories; children are loaded via relationship
    roots = db.query(models.Category).filter(models.Category.parent_id == None).order_by(
        models.Category.sort_order
    ).all()
    backfill_name_en_fields(db, roots)
    for root in roots:
        children = list(getattr(root, "children", None) or [])
        if children:
            backfill_name_en_fields(db, children)
    return roots


@router.get("/packs", response_model=list[schemas.PackOut])
def list_packs(db: Session = Depends(get_db)):
    from services.localize_name import backfill_name_en_fields

    packs = db.query(models.Pack).order_by(models.Pack.sort_order, models.Pack.name).all()
    backfill_name_en_fields(db, packs)
    return packs
