"""Public and authenticated announcement routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import schemas
from auth import get_current_user
from database import get_db
import models
from services.announcements import (
    get_published_announcement,
    list_public_announcements,
    list_published_announcements,
    localized_content,
    localized_title,
    publish_at_for_sort,
    unread_count,
)

router = APIRouter(prefix="/api", tags=["announcements"])


def _serialize_public(row: models.Announcement, *, lang: str, is_read: bool | None = None) -> schemas.AnnouncementOut:
    from services.announcements import is_new

    return schemas.AnnouncementOut(
        id=row.id,
        title=localized_title(row, lang),
        content=localized_content(row, lang),
        is_active=row.is_active,
        priority=row.priority or 0,
        created_at=row.created_at,
        title_ja=row.title_ja,
        title_en=row.title_en,
        content_ja=row.content_ja,
        content_en=row.content_en,
        status=row.status,
        publish_at=row.publish_at,
        expire_at=row.expire_at,
        thumbnail=row.thumbnail,
        updated_at=row.updated_at,
        images=[
            schemas.AnnouncementImageOut.model_validate(img)
            for img in sorted(row.images or [], key=lambda item: item.sort_order)
        ],
        is_new=is_new(row),
        is_read=is_read,
    )


def _serialize_feed_item(item: dict, lang: str) -> schemas.AnnouncementOut:
    row = item["announcement"]
    return schemas.AnnouncementOut(
        id=row.id,
        title=item["title"],
        content=item["content_excerpt"],
        content_excerpt=item["content_excerpt"],
        is_active=True,
        priority=row.priority or 0,
        created_at=row.created_at,
        title_ja=row.title_ja,
        title_en=row.title_en,
        thumbnail=row.thumbnail,
        publish_at=item["publish_at"],
        expire_at=row.expire_at,
        updated_at=row.updated_at,
        images=[
            schemas.AnnouncementImageOut.model_validate(img)
            for img in sorted(row.images or [], key=lambda image: image.sort_order)
        ],
        is_new=item["is_new"],
        is_read=item["is_read"],
    )


@router.get("/announcements", response_model=list[schemas.AnnouncementOut])
def list_announcements_legacy(
    lang: str = Query("ja", pattern="^(ja|en)$"),
    db: Session = Depends(get_db),
):
    """Backward-compatible public banner list for the home page."""
    rows = list_public_announcements(db, lang=lang)
    return [_serialize_public(row, lang=lang) for row in rows]


@router.get("/announcements/feed", response_model=schemas.AnnouncementFeedOut)
def list_announcements_feed(
    lang: str = Query("ja", pattern="^(ja|en)$"),
    q: Optional[str] = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = list_published_announcements(db, lang=lang, q=q, user_id=current_user.id)
    return schemas.AnnouncementFeedOut(
        items=[_serialize_feed_item(item, lang) for item in items],
        unread_count=unread_count(db, current_user.id),
    )


@router.get("/announcements/unread-count", response_model=schemas.AnnouncementUnreadCountOut)
def get_unread_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return schemas.AnnouncementUnreadCountOut(count=unread_count(db, current_user.id))


@router.get("/announcements/{announcement_id}", response_model=schemas.AnnouncementOut)
def get_announcement_detail(
    announcement_id: int,
    lang: str = Query("ja", pattern="^(ja|en)$"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = get_published_announcement(
        db,
        announcement_id,
        lang=lang,
        user_id=current_user.id,
        mark_read=True,
    )
    row = detail["announcement"]
    return schemas.AnnouncementOut(
        id=row.id,
        title=detail["title"],
        content=detail["content"],
        is_active=True,
        priority=row.priority or 0,
        created_at=row.created_at,
        title_ja=row.title_ja,
        title_en=row.title_en,
        content_ja=row.content_ja,
        content_en=row.content_en,
        status=row.status,
        publish_at=detail["publish_at"],
        expire_at=row.expire_at,
        thumbnail=row.thumbnail,
        updated_at=row.updated_at,
        images=[
            schemas.AnnouncementImageOut.model_validate(img)
            for img in sorted(row.images or [], key=lambda image: image.sort_order)
        ],
        is_new=detail["is_new"],
        is_read=True,
    )
