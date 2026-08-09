"""Admin customer notification broadcast (Phase 3-6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import schemas_notifications
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.notification_events import notify_admin_broadcast

router = APIRouter(prefix="/api/admin/user-notifications", tags=["admin-user-notifications"])


@router.post("/broadcast")
def admin_broadcast_user_notification(
    payload: schemas_notifications.AdminBroadcastNotificationIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "notification.write")
    except AdminAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    count = notify_admin_broadcast(
        db,
        title=payload.title,
        body=payload.body,
        user_id=payload.user_id,
        action_url=payload.action_url,
        category=payload.category,
        type=payload.type,
    )
    db.commit()
    return {"created": count}
