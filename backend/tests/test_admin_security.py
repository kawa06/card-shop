"""Admin security RBAC, audit logs, and access control tests."""

from __future__ import annotations

import models_admin
from tests.conftest import admin_headers, auth_headers, create_admin_user


def test_unauthenticated_admin_security_me(api_client):
    res = api_client.get("/api/admin/security/me")
    assert res.status_code == 401


def test_regular_user_cannot_access_admin_security(api_client, db, test_user):
    res = api_client.get(
        "/api/admin/security/admins",
        headers=auth_headers(test_user),
    )
    assert res.status_code == 403


def test_internal_admin_can_list_admins(api_client, db):
    create_admin_user(db, email="manager@test.com", role_code="admin")
    res = api_client.get("/api/admin/security/admins", headers=admin_headers())
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1


def test_admin_login_success_audit_log(api_client, db):
    create_admin_user(db, email="audit-admin@test.com", role_code="admin")
    res = api_client.post(
        "/api/admin/security/session/login",
        headers=admin_headers("audit-admin@test.com"),
    )
    assert res.status_code == 200
    assert res.json()["is_admin"] is True

    logs = db.query(models_admin.AdminAuditLog).filter(
        models_admin.AdminAuditLog.action == "admin.login.success"
    ).all()
    assert any(log.actor_email == "audit-admin@test.com" for log in logs)


def test_deactivated_admin_cannot_login(api_client, db):
    create_admin_user(
        db,
        email="disabled-admin@test.com",
        role_code="admin",
        is_active=False,
    )
    res = api_client.post(
        "/api/admin/security/session/login",
        headers=admin_headers("disabled-admin@test.com"),
    )
    assert res.status_code == 403


def test_viewer_cannot_create_admin(api_client, db):
    create_admin_user(db, email="viewer@test.com", role_code="viewer")
    res = api_client.post(
        "/api/admin/security/admins",
        headers=admin_headers("viewer@test.com"),
        json={
            "email": "new-admin@test.com",
            "name": "New Admin",
            "role_code": "viewer",
        },
    )
    assert res.status_code == 403


def test_admin_can_create_viewer(api_client, db):
    owner = create_admin_user(db, email="owner-create@test.com", role_code="owner")
    res = api_client.post(
        "/api/admin/security/admins",
        headers=admin_headers(owner.email),
        json={
            "email": "new-viewer@test.com",
            "name": "Viewer User",
            "role_code": "viewer",
        },
    )
    assert res.status_code == 201
    assert res.json()["role"]["code"] == "viewer"


def test_permission_change_writes_audit_log(api_client, db):
    owner = create_admin_user(db, email="owner-perm@test.com", role_code="owner")
    target = create_admin_user(db, email="target-perm@test.com", role_code="viewer")
    admin_user = (
        db.query(models_admin.AdminUser)
        .filter(models_admin.AdminUser.user_id == target.id)
        .first()
    )
    res = api_client.patch(
        f"/api/admin/security/admins/{admin_user.id}",
        headers=admin_headers(owner.email),
        json={"role_code": "support_manager", "reason": "role update test"},
    )
    assert res.status_code == 200

    logs = (
        db.query(models_admin.AdminAuditLog)
        .filter(models_admin.AdminAuditLog.action == "admin.permission.changed")
        .all()
    )
    assert any(str(log.resource_id) == str(admin_user.id) for log in logs)


def test_login_failure_audit_log(api_client, db, test_user):
    res = api_client.get(
        "/api/admin/security/me",
        headers=auth_headers(test_user),
    )
    assert res.status_code == 200
    assert res.json()["is_admin"] is False

    logs = db.query(models_admin.AdminAuditLog).filter(
        models_admin.AdminAuditLog.action == "admin.login.failed"
    ).all()
    assert len(logs) >= 1


def test_regular_user_cannot_call_admin_cards(api_client, db, test_user):
    res = api_client.get("/api/admin/cards", headers=auth_headers(test_user))
    assert res.status_code == 403


def test_viewer_can_read_audit_logs(api_client, db):
    create_admin_user(db, email="viewer-audit@test.com", role_code="viewer")
    res = api_client.get(
        "/api/admin/security/audit-logs",
        headers=admin_headers("viewer-audit@test.com"),
    )
    assert res.status_code == 200


def test_admin_cannot_assign_owner_without_owner_role(api_client, db):
    manager = create_admin_user(db, email="manager-role@test.com", role_code="admin")
    res = api_client.post(
        "/api/admin/security/admins",
        headers=admin_headers(manager.email),
        json={
            "email": "fake-owner@test.com",
            "name": "Fake Owner",
            "role_code": "owner",
        },
    )
    assert res.status_code == 403
