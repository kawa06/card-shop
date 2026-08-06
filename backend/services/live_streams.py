"""Live stream domain services (Phase 3-1)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_live
import schemas_live
from services.live_events import emit_live_event


def _utcnow() -> datetime:
    return datetime.utcnow()


def _serialize_product(db: Session, product: models_live.LiveProduct) -> schemas_live.LiveProductOut:
    card = db.query(models.Card).filter(models.Card.id == product.card_id).first()
    return schemas_live.LiveProductOut(
        id=product.id,
        stream_id=product.stream_id,
        card_id=product.card_id,
        sort_order=product.sort_order,
        display_price=product.display_price,
        is_active=product.is_active,
        is_pinned=product.is_pinned,
        card_name=card.name if card else None,
        card_image_url=card.image_url if card else None,
        card_price=int(card.price) if card and card.price is not None else None,
        created_at=product.created_at,
    )


def _active_product(db: Session, stream_id: int) -> Optional[models_live.LiveProduct]:
    return (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.stream_id == stream_id,
            models_live.LiveProduct.is_active.is_(True),
        )
        .order_by(models_live.LiveProduct.sort_order.asc(), models_live.LiveProduct.id.asc())
        .first()
    )


def _pinned_product(db: Session, stream_id: int) -> Optional[models_live.LiveProduct]:
    return (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.stream_id == stream_id,
            models_live.LiveProduct.is_pinned.is_(True),
        )
        .order_by(models_live.LiveProduct.id.desc())
        .first()
    )


def serialize_stream(
    db: Session,
    stream: models_live.LiveStream,
    *,
    include_products: bool = True,
) -> schemas_live.LiveStreamOut:
    active = _active_product(db, stream.id) if include_products else None
    pinned = _pinned_product(db, stream.id) if include_products else None
    product_count = (
        db.query(func.count(models_live.LiveProduct.id))
        .filter(models_live.LiveProduct.stream_id == stream.id)
        .scalar()
        or 0
    )
    comment_count = (
        db.query(func.count(models_live.LiveComment.id))
        .filter(
            models_live.LiveComment.stream_id == stream.id,
            models_live.LiveComment.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    return schemas_live.LiveStreamOut(
        id=stream.id,
        shop_id=stream.shop_id,
        title=stream.title,
        description=stream.description,
        thumbnail_url=stream.thumbnail_url,
        embed_url=stream.embed_url,
        status=stream.status,
        visibility=stream.visibility,
        scheduled_at=stream.scheduled_at,
        started_at=stream.started_at,
        ended_at=stream.ended_at,
        created_at=stream.created_at,
        updated_at=stream.updated_at,
        active_product=_serialize_product(db, active) if active else None,
        pinned_product=_serialize_product(db, pinned) if pinned else None,
        product_count=int(product_count),
        comment_count=int(comment_count),
    )


def get_stream_or_404(db: Session, stream_id: int) -> models_live.LiveStream:
    stream = db.query(models_live.LiveStream).filter(models_live.LiveStream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ配信が見つかりません")
    return stream


def list_streams(
    db: Session,
    *,
    shop_id: int = 1,
    status_filter: Optional[str] = None,
    visibility: Optional[str] = None,
    public_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[models_live.LiveStream], int]:
    query = db.query(models_live.LiveStream).filter(models_live.LiveStream.shop_id == shop_id)
    if public_only:
        query = query.filter(
            models_live.LiveStream.visibility == "public",
            models_live.LiveStream.status.in_(["scheduled", "live", "paused", "ended"]),
        )
    if status_filter:
        query = query.filter(models_live.LiveStream.status == status_filter)
    if visibility:
        query = query.filter(models_live.LiveStream.visibility == visibility)
    total = query.count()
    items = (
        query.order_by(models_live.LiveStream.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )
    return items, total


def create_stream(
    db: Session,
    *,
    payload: schemas_live.LiveStreamCreateIn,
    admin_user_id: int,
    shop_id: int = 1,
) -> models_live.LiveStream:
    stream = models_live.LiveStream(
        shop_id=shop_id,
        title=payload.title,
        description=payload.description,
        thumbnail_url=payload.thumbnail_url,
        embed_url=payload.embed_url,
        visibility=payload.visibility,
        scheduled_at=payload.scheduled_at,
        status="scheduled" if payload.scheduled_at else "draft",
        created_by_admin_id=admin_user_id,
    )
    db.add(stream)
    db.commit()
    db.refresh(stream)
    return stream


def _emit_stream_event(db: Session, stream: models_live.LiveStream) -> None:
    emit_live_event(
        stream.id,
        "stream.updated",
        serialize_stream(db, stream).model_dump(mode="json"),
    )


def update_stream(
    db: Session,
    stream: models_live.LiveStream,
    payload: schemas_live.LiveStreamUpdateIn,
) -> models_live.LiveStream:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(stream, key, value)
    stream.updated_at = _utcnow()
    db.commit()
    db.refresh(stream)
    _emit_stream_event(db, stream)
    return stream


def start_stream(db: Session, stream: models_live.LiveStream) -> models_live.LiveStream:
    if stream.status == "ended":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="終了済みの配信は開始できません")
    stream.status = "live"
    stream.started_at = stream.started_at or _utcnow()
    stream.ended_at = None
    stream.updated_at = _utcnow()
    db.commit()
    db.refresh(stream)
    _emit_stream_event(db, stream)
    return stream


def pause_stream(db: Session, stream: models_live.LiveStream) -> models_live.LiveStream:
    if stream.status != "live":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="配信中のみ一時停止できます")
    stream.status = "paused"
    stream.updated_at = _utcnow()
    db.commit()
    db.refresh(stream)
    _emit_stream_event(db, stream)
    return stream


def resume_stream(db: Session, stream: models_live.LiveStream) -> models_live.LiveStream:
    if stream.status != "paused":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="一時停止中のみ再開できます")
    stream.status = "live"
    stream.updated_at = _utcnow()
    db.commit()
    db.refresh(stream)
    return stream


def end_stream(db: Session, stream: models_live.LiveStream) -> models_live.LiveStream:
    if stream.status == "ended":
        return stream
    stream.status = "ended"
    stream.ended_at = _utcnow()
    stream.updated_at = _utcnow()
    db.commit()
    db.refresh(stream)
    _emit_stream_event(db, stream)
    return stream


def add_product(
    db: Session,
    stream: models_live.LiveStream,
    payload: schemas_live.LiveProductCreateIn,
) -> models_live.LiveProduct:
    card = db.query(models.Card).filter(models.Card.id == payload.card_id).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品が見つかりません")
    existing = (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.stream_id == stream.id,
            models_live.LiveProduct.card_id == payload.card_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="この商品は既に登録されています")
    max_sort = (
        db.query(func.max(models_live.LiveProduct.sort_order))
        .filter(models_live.LiveProduct.stream_id == stream.id)
        .scalar()
    )
    product = models_live.LiveProduct(
        stream_id=stream.id,
        card_id=payload.card_id,
        sort_order=payload.sort_order if payload.sort_order is not None else int(max_sort or 0) + 1,
        display_price=payload.display_price,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def set_active_product(db: Session, stream: models_live.LiveStream, product_id: int) -> models_live.LiveProduct:
    product = (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.id == product_id,
            models_live.LiveProduct.stream_id == stream.id,
        )
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ商品が見つかりません")
    (
        db.query(models_live.LiveProduct)
        .filter(models_live.LiveProduct.stream_id == stream.id)
        .update({models_live.LiveProduct.is_active: False}, synchronize_session=False)
    )
    product.is_active = True
    db.commit()
    db.refresh(product)
    emit_live_event(
        stream.id,
        "product.activated",
        _serialize_product(db, product).model_dump(mode="json"),
    )
    return product


def set_pinned_product(db: Session, stream: models_live.LiveStream, product_id: int) -> models_live.LiveProduct:
    product = (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.id == product_id,
            models_live.LiveProduct.stream_id == stream.id,
        )
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ商品が見つかりません")
    (
        db.query(models_live.LiveProduct)
        .filter(models_live.LiveProduct.stream_id == stream.id)
        .update({models_live.LiveProduct.is_pinned: False}, synchronize_session=False)
    )
    product.is_pinned = True
    db.commit()
    db.refresh(product)
    emit_live_event(
        stream.id,
        "product.pinned",
        _serialize_product(db, product).model_dump(mode="json"),
    )
    return product


def list_products(db: Session, stream_id: int) -> list[models_live.LiveProduct]:
    return (
        db.query(models_live.LiveProduct)
        .filter(models_live.LiveProduct.stream_id == stream_id)
        .order_by(models_live.LiveProduct.sort_order.asc(), models_live.LiveProduct.id.asc())
        .all()
    )


def count_live_sessions(db: Session, *, shop_id: int = 1) -> int:
    return (
        db.query(func.count(models_live.LiveStream.id))
        .filter(
            models_live.LiveStream.shop_id == shop_id,
            models_live.LiveStream.status.in_(["live", "paused"]),
        )
        .scalar()
        or 0
    )
