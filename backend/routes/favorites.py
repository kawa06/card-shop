from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.get("", response_model=list[schemas.FavoriteOut])
def list_favorites(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Favorite)
        .filter(models.Favorite.user_id == current_user.id)
        .order_by(models.Favorite.created_at.desc())
        .all()
    )


@router.get("/ids", response_model=list[int])
def list_favorite_ids(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Favorite.card_id)
        .filter(models.Favorite.user_id == current_user.id)
        .all()
    )
    return [row[0] for row in rows]


@router.post("/{card_id}", response_model=schemas.FavoriteOut, status_code=status.HTTP_201_CREATED)
def add_favorite(
    card_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    card = db.query(models.Card).filter(
        models.Card.id == card_id,
        models.Card.is_active == True,
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")

    existing = db.query(models.Favorite).filter(
        models.Favorite.user_id == current_user.id,
        models.Favorite.card_id == card_id,
    ).first()
    if existing:
        return existing

    favorite = models.Favorite(user_id=current_user.id, card_id=card_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    card_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = db.query(models.Favorite).filter(
        models.Favorite.user_id == current_user.id,
        models.Favorite.card_id == card_id,
    ).first()
    if not favorite:
        raise HTTPException(status_code=404, detail="お気に入りが見つかりません")

    db.delete(favorite)
    db.commit()
    return None
