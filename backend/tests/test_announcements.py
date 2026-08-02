"""Tests for announcement publishing, i18n, reads, and security."""

from datetime import datetime, timedelta

import models
from services.announcement_sanitize import sanitize_announcement_html
from services.announcements import (
    create_announcement,
    get_published_announcement,
    is_visible_now,
    list_published_announcements,
    mark_announcement_read,
    unread_count,
    update_announcement,
)
from tests.conftest import auth_headers, admin_headers


def _published(db, **overrides):
    payload = {
        "title_ja": "日本語タイトル",
        "content_ja": "<p>日本語本文</p>",
        "status_value": "published",
        "publish_at": datetime.utcnow() - timedelta(hours=1),
        "priority": 1,
        "image_urls": ["https://example.com/a.jpg"],
        "thumbnail": "https://example.com/thumb.jpg",
    }
    payload.update(overrides)
    row = create_announcement(db, **payload)
    db.commit()
    db.refresh(row)
    return row


def test_sanitize_strips_script_tags():
    raw = '<p>Hello</p><script>alert(1)</script><img src="x" onerror="alert(1)">'
    cleaned = sanitize_announcement_html(raw)
    assert "<script" not in cleaned
    assert "onerror" not in cleaned
    assert "Hello" in cleaned


def test_create_requires_japanese_fields(db):
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        create_announcement(
            db,
            title_ja="",
            content_ja="",
        )
    assert exc.value.status_code == 400


def test_create_auto_fills_english(db):
    ann = create_announcement(
        db,
        title_ja="テストタイトル",
        content_ja="<p>テスト本文</p>",
        status_value="draft",
    )
    db.commit()
    assert ann.title_en
    assert ann.content_en


def test_public_feed_localizes_by_lang(db, test_user):
    ann = _published(db)
    ja_items = list_published_announcements(db, lang="ja", user_id=test_user.id)
    en_items = list_published_announcements(db, lang="en", user_id=test_user.id)
    assert ja_items[0]["title"] == ann.title_ja
    assert en_items[0]["title"] == ann.title_en


def test_detail_marks_read(db, test_user):
    ann = _published(db)
    assert unread_count(db, test_user.id) == 1
    get_published_announcement(db, ann.id, lang="ja", user_id=test_user.id, mark_read=True)
    db.commit()
    assert unread_count(db, test_user.id) == 0


def test_search_filters_title_and_body(db, test_user):
    _published(db, title_ja="配送遅延", title_en="Shipping delay", content_ja="<p>遅延</p>", content_en="<p>delay</p>")
    _published(
        db,
        title_ja="キャンペーン",
        title_en="Campaign",
        content_ja="<p>セール</p>",
        content_en="<p>sale</p>",
    )
    results = list_published_announcements(db, lang="ja", q="配送", user_id=test_user.id)
    assert len(results) == 1
    assert "配送" in results[0]["title"]


def test_scheduled_not_visible_until_publish_at(db):
    future = datetime.utcnow() + timedelta(days=2)
    ann = _published(db, status_value="scheduled", publish_at=future)
    assert not is_visible_now(ann)


def test_expired_not_visible(db):
    ann = _published(
        db,
        expire_at=datetime.utcnow() - timedelta(minutes=1),
    )
    assert not is_visible_now(ann)


def test_legacy_public_api_still_works(api_client, db):
    _published(db)
    res = api_client.get("/api/announcements?lang=ja")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["title"] == "日本語タイトル"
    assert data[0]["is_active"] is True


def test_feed_requires_auth(api_client, db):
    _published(db)
    res = api_client.get("/api/announcements/feed")
    assert res.status_code == 401


def test_admin_crud(api_client, db):
    create_res = api_client.post(
        "/api/admin/announcements",
        headers=admin_headers(),
        json={
            "title": "legacy",
            "content": "<p>legacy</p>",
            "title_ja": "日本語",
            "content_ja": "<p>ja</p>",
            "status": "draft",
            "priority": 2,
            "image_urls": [],
            "is_active": False,
        },
    )
    assert create_res.status_code == 201
    ann_id = create_res.json()["id"]

    list_res = api_client.get("/api/admin/announcements", headers=admin_headers())
    assert list_res.status_code == 200
    assert any(row["id"] == ann_id for row in list_res.json())

    update_res = api_client.put(
        f"/api/admin/announcements/{ann_id}",
        headers=admin_headers(),
        json={"status": "published", "publish_at": datetime.utcnow().isoformat()},
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "published"

    delete_res = api_client.delete(f"/api/admin/announcements/{ann_id}", headers=admin_headers())
    assert delete_res.status_code == 204


def test_authenticated_detail(api_client, db, test_user):
    ann = _published(db)
    res = api_client.get(
        f"/api/announcements/{ann.id}?lang=en",
        headers=auth_headers(test_user),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == ann.title_en
    assert body["is_read"] is True
    assert len(body["images"]) == 1
