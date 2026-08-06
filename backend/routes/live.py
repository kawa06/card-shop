"""Public live sales routes (Phase 3-1)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import models
import schemas_live
from auth import get_current_user
from database import get_db
from services.live_comments import (
    list_comments,
    post_customer_comment,
    report_comment,
    serialize_comment,
)
from services.live_streams import get_stream_or_404, list_streams, serialize_stream
from services.live_events import live_event_hub

router = APIRouter(prefix="/api/live", tags=["live"])


@router.get("/streams", response_model=schemas_live.LiveStreamListOut)
def public_list_streams(
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = list_streams(
        db,
        public_only=True,
        status_filter=status,
        limit=limit,
        offset=offset,
    )
    return schemas_live.LiveStreamListOut(
        items=[serialize_stream(db, s) for s in items],
        total=total,
    )


@router.get("/streams/{stream_id}", response_model=schemas_live.LiveStreamOut)
def public_get_stream(
    stream_id: int,
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ配信が見つかりません")
    return serialize_stream(db, stream)


@router.get("/streams/{stream_id}/events")
async def public_stream_events(
    stream_id: int,
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ配信が見つかりません")
    return StreamingResponse(
        live_event_hub.stream(stream_id, "public"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/streams/{stream_id}/comments", response_model=schemas_live.LiveCommentListOut)
def public_list_comments(
    stream_id: int,
    q: Optional[str] = Query(None),
    sender_type: Optional[str] = Query(None),
    pinned_only: bool = Query(False),
    cursor: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ配信が見つかりません")
    items, total, next_cursor = list_comments(
        db,
        stream_id=stream_id,
        q=q,
        sender_type=sender_type,
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
def public_post_comment(
    stream_id: int,
    payload: schemas_live.LiveCommentCreateIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ配信が見つかりません")
    comment = post_customer_comment(db, stream=stream, user=current_user, payload=payload)
    return serialize_comment(db, comment)


@router.post("/streams/{stream_id}/comments/{comment_id}/report", status_code=201)
def public_report_comment(
    stream_id: int,
    comment_id: int,
    payload: schemas_live.LiveCommentReportIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ライブ配信が見つかりません")
    report_comment(
        db,
        stream_id=stream.id,
        comment_id=comment_id,
        reporter_user_id=current_user.id,
        payload=payload,
    )
    return {"ok": True}
