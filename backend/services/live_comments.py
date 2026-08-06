"""Live comment services (Phase 3-1)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import models_live
import schemas_live
from services.live_moderation import (
    assert_user_can_comment,
    contains_ng_word,
    write_moderation_audit,
)
from services.live_rate_limit import check_live_comment_rate_limit
from services.live_events import emit_live_event


def _utcnow() -> datetime:
    return datetime.utcnow()


def _sender_name(
    db: Session,
    comment: models_live.LiveComment,
) -> Optional[str]:
    if comment.sender_type == "system":
        return "システム"
    if comment.sender_type in {"staff", "admin"} and comment.sender_admin_id:
        from models_admin import AdminUser

        admin = db.query(AdminUser).filter(AdminUser.id == comment.sender_admin_id).first()
        if admin and admin.user:
            return admin.user.name or "スタッフ"
        return "スタッフ"
    if comment.user_id:
        user = db.query(models.User).filter(models.User.id == comment.user_id).first()
        if user:
            return user.name
    return None


def serialize_comment(db: Session, comment: models_live.LiveComment) -> schemas_live.LiveCommentOut:
    return schemas_live.LiveCommentOut(
        id=comment.id,
        stream_id=comment.stream_id,
        sender_type=comment.sender_type,
        message=comment.message,
        is_pinned=comment.is_pinned,
        created_at=comment.created_at,
        sender_name=_sender_name(db, comment),
        user_id=comment.user_id,
    )


def list_comments(
    db: Session,
    *,
    stream_id: int,
    q: Optional[str] = None,
    sender_type: Optional[str] = None,
    include_deleted: bool = False,
    pinned_only: bool = False,
    cursor: Optional[int] = None,
    limit: int = 50,
) -> tuple[list[models_live.LiveComment], int, Optional[int]]:
    query = db.query(models_live.LiveComment).filter(models_live.LiveComment.stream_id == stream_id)
    if not include_deleted:
        query = query.filter(models_live.LiveComment.deleted_at.is_(None))
    if sender_type:
        query = query.filter(models_live.LiveComment.sender_type == sender_type)
    if pinned_only:
        query = query.filter(models_live.LiveComment.is_pinned.is_(True))
    if q:
        escaped = re.escape(q.strip())
        if escaped:
            query = query.filter(models_live.LiveComment.message.ilike(f"%{escaped}%"))
    if cursor:
        query = query.filter(models_live.LiveComment.id < cursor)
    total = query.count()
    items = query.order_by(models_live.LiveComment.id.desc()).limit(min(limit, 100)).all()
    next_cursor = items[-1].id if len(items) == limit else None
    return items, total, next_cursor


def post_customer_comment(
    db: Session,
    *,
    stream: models_live.LiveStream,
    user: models.User,
    payload: schemas_live.LiveCommentCreateIn,
) -> models_live.LiveComment:
    if stream.status not in {"live", "paused"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="配信中のみコメントできます")
    rl = check_live_comment_rate_limit(f"user:{user.id}")
    if not rl.allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=rl.reason or "投稿が多すぎます")
    assert_user_can_comment(db, stream_id=stream.id, user_id=user.id)
    if contains_ng_word(db, payload.message):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不適切な表現が含まれています")
    comment = models_live.LiveComment(
        stream_id=stream.id,
        user_id=user.id,
        sender_type="customer",
        message=payload.message,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    emit_live_event(
        stream.id,
        "comment.created",
        serialize_comment(db, comment).model_dump(mode="json"),
    )
    return comment


def post_staff_comment(
    db: Session,
    *,
    stream: models_live.LiveStream,
    admin_user_id: int,
    payload: schemas_live.LiveStaffCommentCreateIn,
) -> models_live.LiveComment:
    comment = models_live.LiveComment(
        stream_id=stream.id,
        sender_type=payload.sender_type,
        sender_admin_id=admin_user_id,
        message=payload.message,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    emit_live_event(
        stream.id,
        "comment.created",
        serialize_comment(db, comment).model_dump(mode="json"),
    )
    return comment


def pin_comment(
    db: Session,
    *,
    stream_id: int,
    comment_id: int,
    admin_user_id: int,
    pinned: bool,
) -> models_live.LiveComment:
    comment = (
        db.query(models_live.LiveComment)
        .filter(
            models_live.LiveComment.id == comment_id,
            models_live.LiveComment.stream_id == stream_id,
            models_live.LiveComment.deleted_at.is_(None),
        )
        .first()
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="コメントが見つかりません")
    if pinned:
        (
            db.query(models_live.LiveComment)
            .filter(
                models_live.LiveComment.stream_id == stream_id,
                models_live.LiveComment.is_pinned.is_(True),
            )
            .update({models_live.LiveComment.is_pinned: False}, synchronize_session=False)
        )
    comment.is_pinned = pinned
    db.commit()
    db.refresh(comment)
    write_moderation_audit(
        db,
        stream_id=stream_id,
        action="comment.pin" if pinned else "comment.unpin",
        target_type="comment",
        target_id=comment.id,
        admin_user_id=admin_user_id,
        detail={"comment_id": comment.id},
    )
    db.commit()
    _emit_comment_event(stream_id, "comment.pinned" if pinned else "comment.unpinned", comment, db)
    return comment


def delete_comment(
    db: Session,
    *,
    stream_id: int,
    comment_id: int,
    admin_user_id: int,
) -> models_live.LiveComment:
    comment = (
        db.query(models_live.LiveComment)
        .filter(
            models_live.LiveComment.id == comment_id,
            models_live.LiveComment.stream_id == stream_id,
            models_live.LiveComment.deleted_at.is_(None),
        )
        .first()
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="コメントが見つかりません")
    comment.deleted_at = _utcnow()
    comment.deleted_by_admin_id = admin_user_id
    comment.is_pinned = False
    db.commit()
    db.refresh(comment)
    write_moderation_audit(
        db,
        stream_id=stream_id,
        action="comment.delete",
        target_type="comment",
        target_id=comment.id,
        admin_user_id=admin_user_id,
    )
    db.commit()
    _emit_comment_event(stream_id, "comment.deleted", comment, db)
    return comment


def _emit_comment_event(stream_id: int, event_type: str, comment: models_live.LiveComment, db: Session) -> None:
    emit_live_event(stream_id, event_type, serialize_comment(db, comment).model_dump(mode="json"))


def report_comment(
    db: Session,
    *,
    stream_id: int,
    comment_id: int,
    reporter_user_id: int,
    payload: schemas_live.LiveCommentReportIn,
) -> models_live.LiveCommentReport:
    comment = (
        db.query(models_live.LiveComment)
        .filter(
            models_live.LiveComment.id == comment_id,
            models_live.LiveComment.stream_id == stream_id,
            models_live.LiveComment.deleted_at.is_(None),
        )
        .first()
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="コメントが見つかりません")
    report = models_live.LiveCommentReport(
        comment_id=comment.id,
        reporter_user_id=reporter_user_id,
        reason=payload.reason,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
