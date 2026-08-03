"""Tests for email broadcast, preview, and announcement email integration."""

from __future__ import annotations

from unittest.mock import patch

import models
from auth import create_access_token, hash_password
from services.admin_seed import seed_admin_rbac
from services.announcements import create_announcement
from services.email_broadcast import build_announcement_email_preview, create_announcement_campaign
from services.email_delivery import preview_draft, render_template_string
from services.email_template_seed import seed_email_templates


def _admin_headers(db):
    admin = models.User(
        email="broadcast-admin@example.com",
        name="Broadcast Admin",
        password_hash=hash_password("adminpass"),
        is_admin=True,
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    seed_admin_rbac(db)
    db.refresh(admin)
    token = create_access_token({"sub": str(admin.id)})
    return {"Authorization": f"Bearer {token}"}, admin


def test_render_japanese_variable_alias():
    rendered = render_template_string("{{名前}} 様、注文 {{注文番号}}", {"name": "太郎", "orderNo": "ORD-1"})
    assert rendered == "太郎 様、注文 ORD-1"


def test_preview_draft_with_brand(db):
    seed_email_templates(db)
    result = preview_draft(
        db,
        template_key="member_login_notify",
        subject="【{{shopName}}】テスト",
        html_body="<p>{{name}} 様</p>",
        variables={"name": "テスト"},
    )
    assert "テスト" in result["html"]
    assert "DOCTYPE html" in result["html"]


def test_announcement_email_preview(db, test_user):
    seed_email_templates(db)
    ann = create_announcement(
        db,
        title_ja="テストお知らせ",
        content_ja="<p>本文です</p>",
        status_value="published",
        send_email=True,
    )
    db.commit()
    preview = build_announcement_email_preview(db, ann)
    assert preview["recipient_count"] >= 1
    assert "テストお知らせ" in preview["subject"]


def test_announcement_email_requires_confirm(api_client, db, test_user):
    seed_email_templates(db)
    headers, _ = _admin_headers(db)
    ann = create_announcement(
        db,
        title_ja="配信テスト",
        content_ja="<p>本文</p>",
        status_value="published",
        send_email=True,
    )
    db.commit()

    res = api_client.post(
        f"/api/admin/announcements/{ann.id}/send-email",
        headers=headers,
        json={"confirm": False, "send_mode": "immediate"},
    )
    assert res.status_code == 400


def test_announcement_email_send_mocked(api_client, db, test_user):
    seed_email_templates(db)
    headers, admin = _admin_headers(db)
    ann = create_announcement(
        db,
        title_ja="配信テスト",
        content_ja="<p>本文</p>",
        status_value="published",
        send_email=True,
    )
    db.commit()

    with patch("services.email_delivery._send_email", return_value=(True, None, "msg-1", None, None)):
        res = api_client.post(
            f"/api/admin/announcements/{ann.id}/send-email",
            headers=headers,
            json={"confirm": True, "send_mode": "immediate", "idempotency_key": "test-key-1"},
        )
    assert res.status_code == 200
    assert res.json()["campaign_id"]


def test_admin_email_preview_draft(api_client, db):
    seed_email_templates(db)
    headers, _ = _admin_headers(db)
    res = api_client.post(
        "/api/admin/email/templates/member_login_notify/preview",
        headers=headers,
        json={
            "subject": "【TEST】{{name}}",
            "html_body": "<p>{{name}} 様 / {{名前}} 様</p>",
            "variables": {"name": "山田"},
        },
    )
    assert res.status_code == 200
    assert "山田" in res.json()["html"]


def test_no_auto_email_on_publish(db, test_user):
    seed_email_templates(db)
    ann = create_announcement(
        db,
        title_ja="自動送信なし",
        content_ja="<p>本文</p>",
        status_value="published",
        send_email=True,
    )
    db.commit()
    assert ann.email_send_status == "none"
