"""Announcement business logic — publishing, reads, search, notifications."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

import models
from services.announcement_sanitize import sanitize_announcement_html

logger = logging.getLogger(__name__)

NEW_BADGE_DAYS = 7
STATUSES = {"draft", "published", "scheduled"}


def now_utc() -> datetime:
    return datetime.utcnow()


def _sync_legacy_fields(announcement: models.Announcement) -> None:
    """Keep legacy title/content columns in sync for backward-compatible API consumers."""
    announcement.title = (announcement.title_ja or announcement.title or "").strip()
    announcement.content = announcement.content_ja or announcement.content or ""
    announcement.is_active = announcement.status == "published"


def _plain_text_from_html(html: str) -> str:
    import re

    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _validate_japanese(title_ja: str, content_ja: str) -> None:
    if not (title_ja or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="タイトルを入力してください")
    if not _plain_text_from_html(content_ja):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本文を入力してください")


def _auto_english_from_japanese(db: Session, title_ja: str, content_ja: str) -> tuple[str, str]:
    """Fill English fields from Japanese using the shared translation service."""
    from services.localize_name import translate_ja_to_en

    title_ja = (title_ja or "").strip()
    content_ja = content_ja or ""
    results = translate_ja_to_en(db, [title_ja, content_ja])
    title_en = (results[0] or title_ja).strip()
    content_en = sanitize_announcement_html(results[1] or content_ja)
    return title_en, content_en


def _normalize_status(raw: str | None, *, publish_at: datetime | None) -> str:
    value = (raw or "draft").strip().lower()
    if value not in STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ステータスが不正です")
    if value == "scheduled" and publish_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="公開予約には公開日時が必要です")
    return value


def is_visible_now(announcement: models.Announcement, at: datetime | None = None) -> bool:
    at = at or now_utc()
    if getattr(announcement, "show_on_site", True) is False:
        return False
    if announcement.status == "draft":
        return False
    if announcement.status == "scheduled":
        if not announcement.publish_at or announcement.publish_at > at:
            return False
    elif announcement.status == "published":
        if announcement.publish_at and announcement.publish_at > at:
            return False
    if announcement.expire_at and announcement.expire_at <= at:
        return False
    return True


def localized_title(announcement: models.Announcement, lang: str) -> str:
    if lang == "en":
        return announcement.title_en or announcement.title_ja or announcement.title or ""
    return announcement.title_ja or announcement.title or ""


def localized_content(announcement: models.Announcement, lang: str) -> str:
    if lang == "en":
        return announcement.content_en or announcement.content_ja or announcement.content or ""
    return announcement.content_ja or announcement.content or ""


def publish_at_for_sort(announcement: models.Announcement) -> datetime:
    return announcement.publish_at or announcement.created_at or now_utc()


def is_new(announcement: models.Announcement, at: datetime | None = None) -> bool:
    at = at or now_utc()
    start = publish_at_for_sort(announcement)
    return (at - start) <= timedelta(days=NEW_BADGE_DAYS)


def _replace_images(
    db: Session,
    announcement: models.Announcement,
    image_urls: list[str] | None,
) -> None:
    if image_urls is None:
        return
    announcement.images.clear()
    db.flush()
    for index, url in enumerate(image_urls):
        clean_url = (url or "").strip()
        if not clean_url:
            continue
        announcement.images.append(
            models.AnnouncementImage(
                image_url=clean_url,
                sort_order=index,
            )
        )


def create_announcement(
    db: Session,
    *,
    title_ja: str,
    title_en: str = "",
    content_ja: str,
    content_en: str = "",
    status_value: str = "draft",
    publish_at: datetime | None = None,
    expire_at: datetime | None = None,
    thumbnail: str | None = None,
    priority: int = 0,
    image_urls: list[str] | None = None,
    show_on_site: bool = True,
    send_email: bool = False,
) -> models.Announcement:
    title_ja = title_ja.strip()
    content_ja = sanitize_announcement_html(content_ja)
    _validate_japanese(title_ja, content_ja)
    title_en, content_en = _auto_english_from_japanese(db, title_ja, content_ja)
    status_value = _normalize_status(status_value, publish_at=publish_at)

    announcement = models.Announcement(
        title_ja=title_ja,
        title_en=title_en,
        content_ja=content_ja,
        content_en=content_en,
        status=status_value,
        publish_at=publish_at,
        expire_at=expire_at,
        thumbnail=(thumbnail or "").strip() or None,
        priority=max(0, int(priority)),
        show_on_site=show_on_site,
        send_email=send_email,
        email_send_status="none",
        title=title_ja,
        content=content_ja,
        is_active=status_value == "published",
    )
    _sync_legacy_fields(announcement)
    db.add(announcement)
    db.flush()
    _replace_images(db, announcement, image_urls or [])
    if status_value == "published":
        notify_announcement_published(db, announcement)
    return announcement


def update_announcement(
    db: Session,
    announcement: models.Announcement,
    *,
    title_ja: str | None = None,
    title_en: str | None = None,
    content_ja: str | None = None,
    content_en: str | None = None,
    status_value: str | None = None,
    publish_at: datetime | None = None,
    expire_at: datetime | None = None,
    thumbnail: str | None = None,
    priority: int | None = None,
    image_urls: list[str] | None = None,
    clear_expire_at: bool = False,
    clear_publish_at: bool = False,
    show_on_site: bool | None = None,
    send_email: bool | None = None,
) -> models.Announcement:
    was_published = announcement.status == "published"
    ja_updated = False

    if title_ja is not None:
        announcement.title_ja = title_ja.strip()
        ja_updated = True
    if content_ja is not None:
        announcement.content_ja = sanitize_announcement_html(content_ja)
        ja_updated = True
    if title_en is not None and not ja_updated:
        announcement.title_en = title_en.strip()
    if content_en is not None and not ja_updated:
        announcement.content_en = sanitize_announcement_html(content_en)
    if publish_at is not None or clear_publish_at:
        announcement.publish_at = None if clear_publish_at else publish_at
    if expire_at is not None or clear_expire_at:
        announcement.expire_at = None if clear_expire_at else expire_at
    if thumbnail is not None:
        announcement.thumbnail = (thumbnail or "").strip() or None
    if priority is not None:
        announcement.priority = max(0, int(priority))
    if show_on_site is not None:
        announcement.show_on_site = show_on_site
    if send_email is not None:
        announcement.send_email = send_email
    if status_value is not None:
        announcement.status = _normalize_status(status_value, publish_at=announcement.publish_at)

    if ja_updated:
        title_en, content_en = _auto_english_from_japanese(
            db,
            announcement.title_ja or "",
            announcement.content_ja or "",
        )
        announcement.title_en = title_en
        announcement.content_en = content_en

    _validate_japanese(announcement.title_ja or "", announcement.content_ja or "")
    _sync_legacy_fields(announcement)
    announcement.updated_at = now_utc()
    _replace_images(db, announcement, image_urls)

    if not was_published and announcement.status == "published":
        notify_announcement_published(db, announcement)
    return announcement


def delete_announcement(db: Session, announcement: models.Announcement) -> None:
    db.delete(announcement)


def list_public_announcements(db: Session, *, lang: str = "ja") -> list[models.Announcement]:
    """Legacy public banner list — backward compatible with home page."""
    at = now_utc()
    rows = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .order_by(models.Announcement.priority.desc(), models.Announcement.created_at.desc())
        .all()
    )
    visible = [row for row in rows if is_visible_now(row, at)]
    for row in visible:
        row.title = localized_title(row, lang)
        row.content = localized_content(row, lang)
    return visible


def list_published_announcements(
    db: Session,
    *,
    lang: str = "ja",
    q: str | None = None,
    user_id: int | None = None,
) -> list[dict]:
    at = now_utc()
    query = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .order_by(models.Announcement.priority.desc(), models.Announcement.publish_at.desc(), models.Announcement.created_at.desc())
    )
    rows = [row for row in query.all() if is_visible_now(row, at)]

    read_ids: set[int] = set()
    if user_id:
        read_ids = {
            row.announcement_id
            for row in db.query(models.AnnouncementRead)
            .filter(models.AnnouncementRead.user_id == user_id)
            .all()
        }

    needle = (q or "").strip().lower()
    results: list[dict] = []
    for row in rows:
        title = localized_title(row, lang)
        content = localized_content(row, lang)
        if needle:
            haystack = f"{title}\n{content}".lower()
            if needle not in haystack:
                continue
        results.append(
            {
                "announcement": row,
                "title": title,
                "content_excerpt": _excerpt(content),
                "is_new": is_new(row, at),
                "is_read": row.id in read_ids,
                "publish_at": publish_at_for_sort(row),
            }
        )
    return results


def get_published_announcement(
    db: Session,
    announcement_id: int,
    *,
    lang: str = "ja",
    user_id: int | None = None,
    mark_read: bool = False,
) -> dict:
    row = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .filter(models.Announcement.id == announcement_id)
        .first()
    )
    if not row or not is_visible_now(row):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="お知らせが見つかりません")

    if mark_read and user_id:
        mark_announcement_read(db, row.id, user_id)

    is_read = False
    if user_id:
        is_read = (
            db.query(models.AnnouncementRead)
            .filter(
                models.AnnouncementRead.announcement_id == row.id,
                models.AnnouncementRead.user_id == user_id,
            )
            .first()
            is not None
        )

    return {
        "announcement": row,
        "title": localized_title(row, lang),
        "content": localized_content(row, lang),
        "is_new": is_new(row),
        "is_read": is_read,
        "publish_at": publish_at_for_sort(row),
    }


def mark_announcement_read(db: Session, announcement_id: int, user_id: int) -> None:
    existing = (
        db.query(models.AnnouncementRead)
        .filter(
            models.AnnouncementRead.announcement_id == announcement_id,
            models.AnnouncementRead.user_id == user_id,
        )
        .first()
    )
    if existing:
        return
    db.add(
        models.AnnouncementRead(
            announcement_id=announcement_id,
            user_id=user_id,
            read_at=now_utc(),
        )
    )


def unread_count(db: Session, user_id: int) -> int:
    at = now_utc()
    published_ids = [
        row.id
        for row in db.query(models.Announcement).all()
        if is_visible_now(row, at)
    ]
    if not published_ids:
        return 0
    read_ids = {
        r.announcement_id
        for r in db.query(models.AnnouncementRead)
        .filter(
            models.AnnouncementRead.user_id == user_id,
            models.AnnouncementRead.announcement_id.in_(published_ids),
        )
        .all()
    }
    return max(0, len(published_ids) - len(read_ids))


def notify_announcement_published(db: Session, announcement: models.Announcement) -> None:
    """Site publish hook — email delivery requires explicit admin confirmation."""
    logger.info(
        "announcement_published id=%s title=%s publish_at=%s show_on_site=%s send_email=%s",
        announcement.id,
        announcement.title_ja,
        announcement.publish_at,
        getattr(announcement, "show_on_site", True),
        getattr(announcement, "send_email", False),
    )


def _excerpt(html: str, limit: int = 120) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def search_admin_announcements(db: Session, q: str | None = None) -> list[models.Announcement]:
    query = (
        db.query(models.Announcement)
        .options(joinedload(models.Announcement.images))
        .order_by(models.Announcement.priority.desc(), models.Announcement.updated_at.desc())
    )
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        query = query.filter(
            or_(
                models.Announcement.title_ja.ilike(like),
                models.Announcement.title_en.ilike(like),
                models.Announcement.content_ja.ilike(like),
                models.Announcement.content_en.ilike(like),
                models.Announcement.title.ilike(like),
                models.Announcement.content.ilike(like),
            )
        )
    return query.all()
