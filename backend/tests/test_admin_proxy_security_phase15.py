from __future__ import annotations

import time

import pytest

import models
import models_admin
import models_buyback
from admin_emails import ADMIN_EMAILS
from auth import hash_password
from tests.conftest import admin_headers
from internal_admin_auth import build_admin_proxy_signature


def _signed_headers(secret: str, email: str = "rikukai0609@icloud.com") -> dict[str, str]:
    timestamp = str(int(time.time()))
    return {
        "X-Admin-Email": email,
        "X-Admin-Timestamp": timestamp,
        "X-Admin-Signature": build_admin_proxy_signature(
            secret=secret,
            email=email,
            timestamp=timestamp,
        ),
    }


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_proxy_auth_fails_closed_without_configured_secret(
    api_client, monkeypatch, configured
):
    if configured is None:
        monkeypatch.delenv("ADMIN_PROXY_SECRET", raising=False)
    else:
        monkeypatch.setenv("ADMIN_PROXY_SECRET", configured)

    response = api_client.get(
        "/api/admin/security/me",
        headers=_signed_headers("card-shop-internal-admin-v1"),
    )

    assert response.status_code == 401
    assert "ADMIN_PROXY_SECRET" not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Admin-Email": "rikukai0609@icloud.com"},
        {
            "X-Admin-Email": "rikukai0609@icloud.com",
            "X-Admin-Timestamp": "not-a-timestamp",
            "X-Admin-Signature": "invalid",
        },
        _signed_headers("wrong-secret"),
    ],
)
def test_proxy_auth_rejects_email_only_or_invalid_signature(api_client, headers):
    response = api_client.get("/api/admin/security/me", headers=headers)
    assert response.status_code == 401


def test_proxy_auth_rejects_missing_or_unknown_admin_email(api_client):
    missing = _signed_headers("test-only-admin-proxy-secret")
    missing.pop("X-Admin-Email")
    assert api_client.get("/api/admin/security/me", headers=missing).status_code == 401

    unknown = _signed_headers(
        "test-only-admin-proxy-secret", email="ordinary-user@example.com"
    )
    response = api_client.get("/api/admin/security/me", headers=unknown)
    assert response.status_code == 401
    assert "ordinary-user@example.com" not in response.text


def test_proxy_auth_accepts_only_valid_signed_active_admin(api_client):
    response = api_client.get("/api/admin/security/me", headers=admin_headers())
    assert response.status_code == 200
    assert response.json()["is_admin"] is True


def test_proxy_auth_rejects_inactive_admin(api_client, db):
    owner_user = (
        db.query(models.User)
        .filter(models.User.email == "rikukai0609@icloud.com")
        .one()
    )
    admin_user = (
        db.query(models_admin.AdminUser)
        .filter(models_admin.AdminUser.user_id == owner_user.id)
        .one()
    )
    admin_user.is_active = False
    db.commit()

    response = api_client.get("/api/admin/security/me", headers=admin_headers())

    assert response.status_code == 401


def test_configured_email_alone_never_promotes_or_authenticates_admin(api_client, db):
    email = "email-only-admin@test.com"
    ADMIN_EMAILS.add(email)
    try:
        user = models.User(
            email=email,
            name="Email Only",
            password_hash=hash_password("test-password"),
            is_admin=False,
            is_verified=True,
        )
        db.add(user)
        db.commit()

        response = api_client.get(
            "/api/admin/security/me",
            headers=_signed_headers("test-only-admin-proxy-secret", email=email),
        )

        db.refresh(user)
        assert response.status_code == 401
        assert user.is_admin is False
    finally:
        ADMIN_EMAILS.discard(email)


def test_proxy_rejection_does_not_mutate_buyback_or_return_pii(
    api_client, db, test_user, caplog
):
    buyback_request = models_buyback.BuybackRequest(
        user_id=test_user.id,
        request_number="KBB-PROXY-SECURITY",
        status=models_buyback.BuybackRequestStatus.submitted.value,
        estimated_total=1000,
    )
    db.add(buyback_request)
    db.commit()
    original_status = buyback_request.status
    forged = _signed_headers(
        "card-shop-internal-admin-v1", email="rikukai0609@icloud.com"
    )

    response = api_client.patch(
        f"/api/admin/buyback/requests/{buyback_request.id}",
        headers=forged,
        json={"status": "received"},
    )

    db.refresh(buyback_request)
    assert response.status_code == 401
    assert buyback_request.status == original_status
    assert test_user.email not in response.text
    assert "card-shop-internal-admin-v1" not in caplog.text
    assert "rikukai0609@icloud.com" not in caplog.text
    assert (
        db.query(models_buyback.BuybackStatusHistory)
        .filter(models_buyback.BuybackStatusHistory.request_id == buyback_request.id)
        .count()
        == 0
    )
