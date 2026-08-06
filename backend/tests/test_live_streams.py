"""Tests for Phase 3-1 live stream foundation."""

from __future__ import annotations

import models
import models_live
from services.live_comments import post_customer_comment
from services.live_moderation import add_ng_word
from services.live_streams import (
    add_product,
    count_live_sessions,
    create_stream,
    end_stream,
    serialize_stream,
    set_active_product,
    start_stream,
)
import schemas_live
from tests.conftest import admin_headers, auth_headers, create_admin_user


def _card(db) -> models.Card:
    card = models.Card(name="Live Card", price=1200, stock=5)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def test_create_and_start_stream(db):
    admin = create_admin_user(db)
    from services.admin_auth import get_admin_user_for_user

    admin_user = get_admin_user_for_user(db, admin)
    stream = create_stream(
        db,
        payload=schemas_live.LiveStreamCreateIn(title="Test Live"),
        admin_user_id=admin_user.id,
    )
    assert stream.status == "draft"
    started = start_stream(db, stream)
    assert started.status == "live"
    assert started.started_at is not None
    assert count_live_sessions(db) == 1
    ended = end_stream(db, started)
    assert ended.status == "ended"
    assert count_live_sessions(db) == 0


def test_product_switch(db):
    admin = create_admin_user(db)
    from services.admin_auth import get_admin_user_for_user

    admin_user = get_admin_user_for_user(db, admin)
    stream = create_stream(
        db,
        payload=schemas_live.LiveStreamCreateIn(title="Product Live"),
        admin_user_id=admin_user.id,
    )
    card_a = _card(db)
    card_b = models.Card(name="Live Card B", price=900, stock=2)
    db.add(card_b)
    db.commit()
    db.refresh(card_b)
    product_a = add_product(db, stream, schemas_live.LiveProductCreateIn(card_id=card_a.id))
    product_b = add_product(db, stream, schemas_live.LiveProductCreateIn(card_id=card_b.id))
    set_active_product(db, stream, product_a.id)
    out = serialize_stream(db, stream)
    assert out.active_product is not None
    assert out.active_product.id == product_a.id
    set_active_product(db, stream, product_b.id)
    out2 = serialize_stream(db, stream)
    assert out2.active_product is not None
    assert out2.active_product.id == product_b.id


def test_ng_word_blocks_comment(db, test_user):
    admin = create_admin_user(db)
    from services.admin_auth import get_admin_user_for_user

    admin_user = get_admin_user_for_user(db, admin)
    stream = create_stream(
        db,
        payload=schemas_live.LiveStreamCreateIn(title="Comment Live"),
        admin_user_id=admin_user.id,
    )
    start_stream(db, stream)
    add_ng_word(db, "badword")
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        post_customer_comment(
            db,
            stream=stream,
            user=test_user,
            payload=schemas_live.LiveCommentCreateIn(message="this has badword inside"),
        )
    assert exc.value.status_code == 400


def test_admin_live_api_rbac_and_crud(api_client, db):
    create_admin_user(db, email="admin@test.com", role_code="viewer")
    denied = api_client.get("/api/admin/live/streams", headers=admin_headers("admin@test.com"))
    assert denied.status_code == 403

    admin = create_admin_user(db, email="sales@test.com", role_code="sales_manager")
    listed = api_client.get("/api/admin/live/streams", headers=admin_headers("sales@test.com"))
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    created = api_client.post(
        "/api/admin/live/streams",
        headers=admin_headers("sales@test.com"),
        json={"title": "API Live"},
    )
    assert created.status_code == 201
    stream_id = created.json()["id"]

    card = _card(db)
    product = api_client.post(
        f"/api/admin/live/streams/{stream_id}/products",
        headers=admin_headers("sales@test.com"),
        json={"card_id": card.id},
    )
    assert product.status_code == 201

    started = api_client.post(
        f"/api/admin/live/streams/{stream_id}/start",
        headers=admin_headers("sales@test.com"),
    )
    assert started.status_code == 200
    assert started.json()["status"] == "live"


def test_public_live_list_and_comment(api_client, db, test_user):
    admin = create_admin_user(db, email="ops@test.com", role_code="admin")
    created = api_client.post(
        "/api/admin/live/streams",
        headers=admin_headers("ops@test.com"),
        json={"title": "Public Live", "visibility": "public"},
    )
    stream_id = created.json()["id"]
    api_client.post(f"/api/admin/live/streams/{stream_id}/start", headers=admin_headers("ops@test.com"))

    public = api_client.get("/api/live/streams")
    assert public.status_code == 200
    assert public.json()["total"] >= 1

    comment = api_client.post(
        f"/api/live/streams/{stream_id}/comments",
        headers=auth_headers(test_user),
        json={"message": "hello live"},
    )
    assert comment.status_code == 201
    assert comment.json()["message"] == "hello live"

    listed = api_client.get(f"/api/live/streams/{stream_id}/comments")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_comment_moderation_flow(api_client, db, test_user):
    create_admin_user(db, email="mod@test.com", role_code="sales_manager")
    created = api_client.post(
        "/api/admin/live/streams",
        headers=admin_headers("mod@test.com"),
        json={"title": "Mod Live", "visibility": "public"},
    )
    stream_id = created.json()["id"]
    api_client.post(f"/api/admin/live/streams/{stream_id}/start", headers=admin_headers("mod@test.com"))

    posted = api_client.post(
        f"/api/live/streams/{stream_id}/comments",
        headers=auth_headers(test_user),
        json={"message": "please pin me"},
    )
    comment_id = posted.json()["id"]

    pinned = api_client.post(
        f"/api/admin/live/streams/{stream_id}/comments/{comment_id}/pin?pinned=true",
        headers=admin_headers("mod@test.com"),
    )
    assert pinned.status_code == 200
    assert pinned.json()["is_pinned"] is True

    filtered = api_client.get(
        f"/api/admin/live/streams/{stream_id}/comments",
        headers=admin_headers("mod@test.com"),
        params={"pinned_only": True},
    )
    assert filtered.status_code == 200
    assert any(c["id"] == comment_id for c in filtered.json()["items"])

    api_client.post(
        f"/api/live/streams/{stream_id}/comments/{comment_id}/report",
        headers=auth_headers(test_user),
        json={"reason": "spam"},
    )

    muted = api_client.post(
        f"/api/admin/live/streams/{stream_id}/mutes",
        headers=admin_headers("mod@test.com"),
        json={"user_id": test_user.id},
    )
    assert muted.status_code == 201

    blocked = api_client.post(
        f"/api/live/streams/{stream_id}/comments",
        headers=auth_headers(test_user),
        json={"message": "muted user tries"},
    )
    assert blocked.status_code == 403

    ng = api_client.post(
        "/api/admin/live/ng-words",
        headers=admin_headers("mod@test.com"),
        json={"word": "blockedterm"},
    )
    assert ng.status_code == 201

    other = models.User(email="other@example.com", password_hash="x", name="Other")
    db.add(other)
    db.commit()
    db.refresh(other)

    ng_blocked = api_client.post(
        f"/api/live/streams/{stream_id}/comments",
        headers=auth_headers(other),
        json={"message": "contains blockedterm here"},
    )
    assert ng_blocked.status_code == 400


def test_live_event_hub_stream_and_publish():
    import asyncio

    from services.live_events import emit_live_event, live_event_hub

    async def run() -> None:
        gen = live_event_hub.stream(99, "public")
        first = await gen.__anext__()
        assert "connected" in first
        emit_live_event(99, "comment.created", {"message": "hub test", "id": 1})
        msg = await gen.__anext__()
        assert "comment.created" in msg
        await gen.aclose()

    asyncio.run(run())
    assert live_event_hub.global_connections == 0
