"""User-facing notifications API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas_notifications
from auth import get_current_user
from database import get_db
from services import notification_settings as settings_svc
from services import user_notifications as notif_svc

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=schemas_notifications.NotificationListOut)
def list_my_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total, unread = notif_svc.list_notifications(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return schemas_notifications.NotificationListOut(
        items=[schemas_notifications.NotificationOut.model_validate(i) for i in items],
        total=total,
        unread_count=unread,
    )


@router.get("/unread-count", response_model=schemas_notifications.UnreadCountOut)
def get_unread_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return schemas_notifications.UnreadCountOut(unread_count=notif_svc.unread_count(db, user_id=current_user.id))


@router.post("/{notification_id}/read", response_model=schemas_notifications.NotificationOut)
def mark_one_read(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = notif_svc.mark_read(db, user_id=current_user.id, notification_id=notification_id)
    if not row:
        raise HTTPException(status_code=404, detail="通知が見つかりません")
    db.commit()
    db.refresh(row)
    return schemas_notifications.NotificationOut.model_validate(row)


@router.post("/read-all", response_model=schemas_notifications.UnreadCountOut)
def mark_all_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif_svc.mark_all_read(db, user_id=current_user.id)
    db.commit()
    return schemas_notifications.UnreadCountOut(unread_count=0)


@router.get("/settings", response_model=schemas_notifications.NotificationSettingsOut)
def get_settings(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = settings_svc.get_or_create_settings(db, current_user.id)
    db.commit()
    return schemas_notifications.NotificationSettingsOut.model_validate(row)


@router.patch("/settings", response_model=schemas_notifications.NotificationSettingsOut)
def patch_settings(
    payload: schemas_notifications.NotificationSettingsUpdateIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = settings_svc.update_settings(db, current_user.id, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(row)
    return schemas_notifications.NotificationSettingsOut.model_validate(row)
