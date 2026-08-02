"""Tests for admin email API."""

from __future__ import annotations

from auth import create_access_token, hash_password
import models
from services.admin_seed import seed_admin_rbac
from services.email_template_seed import seed_email_templates


def _admin_headers(db):
    admin = models.User(
        email="email-admin@example.com",
        name="Email Admin",
        password_hash=hash_password("adminpass"),
        is_admin=True,
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    seed_admin_rbac(db)
    db.refresh(admin)
    token = create_access_token({"sub": str(admin.id)})
    return {"Authorization": f"Bearer {token}"}


def test_admin_email_templates_list(api_client, db):
    seed_email_templates(db)
    headers = _admin_headers(db)

    res = api_client.get("/api/admin/email/templates", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 40
    assert any(item["template_key"] == "member_login_notify" for item in data)


def test_admin_email_template_update(api_client, db):
    seed_email_templates(db)
    headers = _admin_headers(db)

    res = api_client.put(
        "/api/admin/email/templates/member_login_notify",
        headers=headers,
        json={"name": "ログイン通知", "subject": "【TEST】ログイン", "html_body": "<p>{{name}} 様</p>"},
    )
    assert res.status_code == 200
    assert res.json()["subject"] == "【TEST】ログイン"


def test_admin_email_requires_permission(api_client, db):
    seed_email_templates(db)
    user = models.User(
        email="noperm@example.com",
        name="No Perm",
        password_hash=hash_password("x"),
        is_admin=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    token = create_access_token({"sub": str(user.id)})
    res = api_client.get("/api/admin/email/templates", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
