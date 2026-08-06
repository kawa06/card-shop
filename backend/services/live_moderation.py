"""Live moderation helpers (Phase 3-1)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models_live
from services.live_events import emit_live_event


def _utcnow() -> datetime:
    return datetime.utcnow()


def write_moderation_audit(
    db: Session,
    *,
    stream_id: Optional[int],
    action: str,
    target_type: str,
    target_id: Optional[int],
    admin_user_id: Optional[int],
    detail: Optional[dict[str, Any]] = None,
) -> models_live.LiveModerationAuditLog:
    log = models_live.LiveModerationAuditLog(
        stream_id=stream_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        admin_user_id=admin_user_id,
        detail_json=json.dumps(detail or {}, ensure_ascii=False),
    )
    db.add(log)
    return log


def contains_ng_word(db: Session, message: str) -> bool:
    words = (
        db.query(models_live.LiveNgWord.word)
        .filter(models_live.LiveNgWord.is_active.is_(True))
        .all()
    )
    lowered = message.lower()
    return any(word for (word,) in words if word and word in lowered)


def assert_user_can_comment(db: Session, *, stream_id: int, user_id: int) -> None:
    now = _utcnow()
    ban = (
        db.query(models_live.LiveUserBan)
        .filter(
            models_live.LiveUserBan.user_id == user_id,
            (models_live.LiveUserBan.stream_id == stream_id) | (models_live.LiveUserBan.stream_id.is_(None)),
        )
        .order_by(models_live.LiveUserBan.id.desc())
        .first()
    )
    if ban is not None and (ban.banned_until is None or ban.banned_until > now):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="コメントが制限されています")
    mute = (
        db.query(models_live.LiveUserMute)
        .filter(
            models_live.LiveUserMute.stream_id == stream_id,
            models_live.LiveUserMute.user_id == user_id,
        )
        .first()
    )
    if mute is not None and (mute.muted_until is None or mute.muted_until > now):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="一時的にコメントできません")


def mute_user(
    db: Session,
    *,
    stream_id: int,
    user_id: int,
    admin_user_id: int,
    muted_until: Optional[datetime] = None,
) -> models_live.LiveUserMute:
    mute = (
        db.query(models_live.LiveUserMute)
        .filter(
            models_live.LiveUserMute.stream_id == stream_id,
            models_live.LiveUserMute.user_id == user_id,
        )
        .first()
    )
    if mute is None:
        mute = models_live.LiveUserMute(
            stream_id=stream_id,
            user_id=user_id,
            muted_by_admin_id=admin_user_id,
        )
        db.add(mute)
    mute.muted_until = muted_until
    mute.muted_by_admin_id = admin_user_id
    db.commit()
    db.refresh(mute)
    write_moderation_audit(
        db,
        stream_id=stream_id,
        action="user.mute",
        target_type="user",
        target_id=user_id,
        admin_user_id=admin_user_id,
        detail={"muted_until": muted_until.isoformat() if muted_until else None},
    )
    db.commit()
    emit_live_event(stream_id, "user.muted", {"user_id": user_id}, audience="admin")
    return mute


def ban_user(
    db: Session,
    *,
    user_id: int,
    admin_user_id: int,
    stream_id: Optional[int] = None,
    banned_until: Optional[datetime] = None,
    reason: Optional[str] = None,
) -> models_live.LiveUserBan:
    ban = models_live.LiveUserBan(
        stream_id=stream_id,
        user_id=user_id,
        banned_until=banned_until,
        reason=reason,
        banned_by_admin_id=admin_user_id,
    )
    db.add(ban)
    db.commit()
    db.refresh(ban)
    write_moderation_audit(
        db,
        stream_id=stream_id,
        action="user.ban",
        target_type="user",
        target_id=user_id,
        admin_user_id=admin_user_id,
        detail={"reason": reason, "banned_until": banned_until.isoformat() if banned_until else None},
    )
    db.commit()
    return ban


def add_ng_word(db: Session, word: str) -> models_live.LiveNgWord:
    existing = db.query(models_live.LiveNgWord).filter(models_live.LiveNgWord.word == word).first()
    if existing is not None:
        if existing.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="既に登録されています")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    ng = models_live.LiveNgWord(word=word, is_active=True)
    db.add(ng)
    db.commit()
    db.refresh(ng)
    return ng


def deactivate_ng_word(db: Session, ng_word_id: int) -> models_live.LiveNgWord:
    ng = db.query(models_live.LiveNgWord).filter(models_live.LiveNgWord.id == ng_word_id).first()
    if ng is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NGワードが見つかりません")
    ng.is_active = False
    db.commit()
    db.refresh(ng)
    return ng
