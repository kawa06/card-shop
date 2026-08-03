"""Admin in-app notification routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import schemas_email
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.admin_notify_in_app import (
    count_unread_notifications,
    list_admin_notifications,
    mark_notification_read,
)
from services.db_persist import PersistDep, safe_commit

router = APIRouter(
    prefix="/api/admin/notifications",
    tags=["admin-notifications"],
    dependencies=[PersistDep],
)


def _require_admin(ctx: AdminContext = Depends(get_current_admin_context)) -> AdminContext:
    try:
        require_permission(ctx, "admin.email.read")
    except AdminAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return ctx


@router.get("/unread-count")
def unread_count(
    ctx: AdminContext = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    return {"count": count_unread_notifications(db, ctx.admin_user.id)}


@router.get("", response_model=list[schemas_email.AdminInAppNotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    ctx: AdminContext = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = list_admin_notifications(db, ctx.admin_user.id, unread_only=unread_only, limit=limit)
    return rows


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    ctx: AdminContext = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    ok = mark_notification_read(db, notification_id, ctx.admin_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知が見つかりません")
    safe_commit(db, action="通知既読")
    return {"ok": True}
