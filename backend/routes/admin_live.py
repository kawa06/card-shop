"""Admin live sales routes (Phase 3-1)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import models_admin
import schemas_live
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.live_comments import (
    delete_comment,
    list_comments,
    pin_comment,
    post_staff_comment,
    serialize_comment,
)
from services.live_moderation import add_ng_word, ban_user, deactivate_ng_word, mute_user
from services.live_streams import (
    add_product,
    create_stream,
    end_stream,
    get_stream_or_404,
    list_products,
    list_streams,
    pause_stream,
    resume_stream,
    serialize_stream,
    set_active_product,
    set_pinned_product,
    start_stream,
    update_stream,
    _serialize_product,
)
from services.live_events import live_event_hub

router = APIRouter(prefix="/api/admin/live", tags=["admin-live"])


def _handle_admin_error(exc: AdminAccessError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/streams", response_model=schemas_live.LiveStreamListOut)
def admin_list_streams(
    status: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    items, total = list_streams(db, status_filter=status, visibility=visibility, limit=limit, offset=offset)
    return schemas_live.LiveStreamListOut(
        items=[serialize_stream(db, s) for s in items],
        total=total,
    )


@router.post("/streams", response_model=schemas_live.LiveStreamOut, status_code=201)
def admin_create_stream(
    payload: schemas_live.LiveStreamCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = create_stream(db, payload=payload, admin_user_id=ctx.admin_user.id)
    return serialize_stream(db, stream)


@router.get("/streams/{stream_id}", response_model=schemas_live.LiveStreamOut)
def admin_get_stream(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = get_stream_or_404(db, stream_id)
    return serialize_stream(db, stream)


@router.get("/streams/{stream_id}/events")
async def admin_stream_events(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    get_stream_or_404(db, stream_id)
    return StreamingResponse(
        live_event_hub.stream(stream_id, "admin"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/streams/{stream_id}", response_model=schemas_live.LiveStreamOut)
def admin_update_stream(
    stream_id: int,
    payload: schemas_live.LiveStreamUpdateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = get_stream_or_404(db, stream_id)
    stream = update_stream(db, stream, payload)
    return serialize_stream(db, stream)


@router.post("/streams/{stream_id}/start", response_model=schemas_live.LiveStreamOut)
def admin_start_stream(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.broadcast")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = start_stream(db, get_stream_or_404(db, stream_id))
    return serialize_stream(db, stream)


@router.post("/streams/{stream_id}/pause", response_model=schemas_live.LiveStreamOut)
def admin_pause_stream(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.broadcast")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = pause_stream(db, get_stream_or_404(db, stream_id))
    return serialize_stream(db, stream)


@router.post("/streams/{stream_id}/resume", response_model=schemas_live.LiveStreamOut)
def admin_resume_stream(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.broadcast")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = resume_stream(db, get_stream_or_404(db, stream_id))
    return serialize_stream(db, stream)


@router.post("/streams/{stream_id}/end", response_model=schemas_live.LiveStreamOut)
def admin_end_stream(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.broadcast")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    stream = end_stream(db, get_stream_or_404(db, stream_id))
    return serialize_stream(db, stream)


@router.get("/streams/{stream_id}/products", response_model=list[schemas_live.LiveProductOut])
def admin_list_products(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    get_stream_or_404(db, stream_id)
    return [_serialize_product(db, p) for p in list_products(db, stream_id)]


@router.post("/streams/{stream_id}/products", response_model=schemas_live.LiveProductOut, status_code=201)
def admin_add_product(
    stream_id: int,
    payload: schemas_live.LiveProductCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    product = add_product(db, get_stream_or_404(db, stream_id), payload)
    return _serialize_product(db, product)


@router.post("/streams/{stream_id}/products/{product_id}/activate", response_model=schemas_live.LiveProductOut)
def admin_activate_product(
    stream_id: int,
    product_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    product = set_active_product(db, get_stream_or_404(db, stream_id), product_id)
    return _serialize_product(db, product)


@router.post("/streams/{stream_id}/products/{product_id}/pin", response_model=schemas_live.LiveProductOut)
def admin_pin_product(
    stream_id: int,
    product_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    product = set_pinned_product(db, get_stream_or_404(db, stream_id), product_id)
    return _serialize_product(db, product)


@router.get("/streams/{stream_id}/comments", response_model=schemas_live.LiveCommentListOut)
def admin_list_comments(
    stream_id: int,
    q: Optional[str] = Query(None),
    sender_type: Optional[str] = Query(None),
    pinned_only: bool = Query(False),
    cursor: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    get_stream_or_404(db, stream_id)
    items, total, next_cursor = list_comments(
        db,
        stream_id=stream_id,
        q=q,
        sender_type=sender_type,
        include_deleted=True,
        pinned_only=pinned_only,
        cursor=cursor,
        limit=limit,
    )
    return schemas_live.LiveCommentListOut(
        items=[serialize_comment(db, c) for c in items],
        total=total,
        next_cursor=next_cursor,
    )


@router.post("/streams/{stream_id}/comments", response_model=schemas_live.LiveCommentOut, status_code=201)
def admin_post_comment(
    stream_id: int,
    payload: schemas_live.LiveStaffCommentCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    comment = post_staff_comment(
        db,
        stream=get_stream_or_404(db, stream_id),
        admin_user_id=ctx.admin_user.id,
        payload=payload,
    )
    return serialize_comment(db, comment)


@router.post("/streams/{stream_id}/comments/{comment_id}/pin", response_model=schemas_live.LiveCommentOut)
def admin_pin_comment(
    stream_id: int,
    comment_id: int,
    pinned: bool = Query(True),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    comment = pin_comment(
        db,
        stream_id=stream_id,
        comment_id=comment_id,
        admin_user_id=ctx.admin_user.id,
        pinned=pinned,
    )
    return serialize_comment(db, comment)


@router.delete("/streams/{stream_id}/comments/{comment_id}", response_model=schemas_live.LiveCommentOut)
def admin_delete_comment(
    stream_id: int,
    comment_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    comment = delete_comment(
        db,
        stream_id=stream_id,
        comment_id=comment_id,
        admin_user_id=ctx.admin_user.id,
    )
    return serialize_comment(db, comment)


@router.post("/streams/{stream_id}/mutes", status_code=201)
def admin_mute_user(
    stream_id: int,
    payload: schemas_live.LiveUserMuteIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    mute_user(
        db,
        stream_id=stream_id,
        user_id=payload.user_id,
        admin_user_id=ctx.admin_user.id,
        muted_until=payload.muted_until,
    )
    return {"ok": True}


@router.post("/bans", status_code=201)
def admin_ban_user(
    payload: schemas_live.LiveUserBanIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    ban_user(
        db,
        user_id=payload.user_id,
        admin_user_id=ctx.admin_user.id,
        stream_id=payload.stream_id,
        banned_until=payload.banned_until,
        reason=payload.reason,
    )
    return {"ok": True}


@router.get("/ng-words", response_model=list[schemas_live.LiveNgWordOut])
def admin_list_ng_words(
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    from models_live import LiveNgWord

    rows = db.query(LiveNgWord).order_by(LiveNgWord.word.asc()).all()
    return rows


@router.post("/ng-words", response_model=schemas_live.LiveNgWordOut, status_code=201)
def admin_create_ng_word(
    payload: schemas_live.LiveNgWordCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    return add_ng_word(db, payload.word)


@router.delete("/ng-words/{ng_word_id}", response_model=schemas_live.LiveNgWordOut)
def admin_delete_ng_word(
    ng_word_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.moderate")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    return deactivate_ng_word(db, ng_word_id)


@router.get("/moderators", response_model=list[schemas_live.LiveModeratorOut])
def admin_list_moderators(
    stream_id: Optional[int] = Query(None),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    from models_live import LiveModerator

    query = db.query(LiveModerator)
    if stream_id is not None:
        query = query.filter(
            (LiveModerator.stream_id == stream_id) | (LiveModerator.stream_id.is_(None))
        )
    rows = query.order_by(LiveModerator.id.desc()).all()
    out: list[schemas_live.LiveModeratorOut] = []
    for row in rows:
        admin = db.query(models_admin.AdminUser).filter(models_admin.AdminUser.id == row.admin_user_id).first()
        out.append(
            schemas_live.LiveModeratorOut(
                id=row.id,
                stream_id=row.stream_id,
                admin_user_id=row.admin_user_id,
                admin_email=admin.user.email if admin and admin.user else None,
                admin_name=admin.user.name if admin and admin.user else None,
                created_at=row.created_at,
            )
        )
    return out


@router.post("/moderators", response_model=schemas_live.LiveModeratorOut, status_code=201)
def admin_create_moderator(
    payload: schemas_live.LiveModeratorCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "live.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    from models_live import LiveModerator

    admin = db.query(models_admin.AdminUser).filter(models_admin.AdminUser.id == payload.admin_user_id).first()
    if admin is None:
        raise HTTPException(status_code=404, detail="管理者が見つかりません")
    existing = (
        db.query(LiveModerator)
        .filter(
            LiveModerator.admin_user_id == payload.admin_user_id,
            LiveModerator.stream_id == payload.stream_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="既にモデレーターです")
    row = LiveModerator(
        stream_id=payload.stream_id,
        admin_user_id=payload.admin_user_id,
        granted_by_admin_id=ctx.admin_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return schemas_live.LiveModeratorOut(
        id=row.id,
        stream_id=row.stream_id,
        admin_user_id=row.admin_user_id,
        admin_email=admin.user.email if admin.user else None,
        admin_name=admin.user.name if admin.user else None,
        created_at=row.created_at,
    )
