from __future__ import annotations

import json

import pytest

import models_buyback
from tests.conftest import auth_headers, create_admin_user
from services.admin_auth import get_admin_user_for_user, load_permissions


def _request(db, user, *, status="submitted", suffix="1"):
    row = models_buyback.BuybackRequest(
        user_id=user.id,
        request_number=f"KBB-RBAC-{suffix}",
        status=status,
        estimated_total=1000,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_viewer_can_list_requests_but_pii_is_masked(api_client, db, test_user):
    request = _request(db, test_user)
    viewer = create_admin_user(db, email="viewer@test.com", role_code="viewer")

    response = api_client.get(
        "/api/admin/buyback/requests",
        headers=auth_headers(viewer),
    )

    assert response.status_code == 200
    result = next(item for item in response.json() if item["id"] == request.id)
    assert result["user_email"] == ""
    assert result["user_name"] == ""
    assert test_user.email not in response.text

    pii_search = api_client.get(
        "/api/admin/buyback/requests",
        headers=auth_headers(viewer),
        params={"q": test_user.email},
    )
    assert pii_search.status_code == 200
    assert pii_search.json() == []

    detail = api_client.get(
        f"/api/admin/buyback/requests/{request.id}",
        headers=auth_headers(viewer),
    )
    assert detail.status_code == 200
    assert detail.json()["user_email"] == ""
    assert detail.json()["customer_note"] is None
    assert detail.json()["payout_account"] is None
    assert detail.json()["allowed_next_statuses"] == []


def test_viewer_cannot_view_identity_pii_or_mutate_request(
    api_client, db, test_user
):
    request = _request(db, test_user)
    identity = models_buyback.IdentityVerification(
        user_id=test_user.id,
        status=models_buyback.IdentityVerificationStatus.pending.value,
        document_type="drivers_license",
    )
    db.add(identity)
    db.commit()
    viewer = create_admin_user(db, email="viewer-denied@test.com", role_code="viewer")
    headers = auth_headers(viewer)
    copied_token = "Z" * 43

    pii = api_client.get("/api/admin/buyback/identity", headers=headers)
    mutation = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=headers,
        json={"status": "cancelled", "admin_note": copied_token},
    )
    payout = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/complete-payout",
        headers=headers,
        json={"send_email": False},
    )

    db.refresh(request)
    assert pii.status_code == 403
    assert test_user.email not in pii.text
    assert mutation.status_code == 403
    assert payout.status_code == 403
    assert request.status == "submitted"

    denials = (
        db.query(models_buyback.BuybackAuditLog)
        .filter(
            models_buyback.BuybackAuditLog.actor_user_id == viewer.id,
            models_buyback.BuybackAuditLog.action == "permission_denied",
        )
        .all()
    )
    assert len(denials) == 3
    assert all(
        json.loads(row.details_json)["failure_reason"] == "insufficient_permission"
        for row in denials
    )
    assert all(test_user.email not in (row.details_json or "") for row in denials)
    assert all(copied_token not in (row.details_json or "") for row in denials)


def test_appraiser_can_assess_but_cannot_manage_other_statuses(
    api_client, db, test_user
):
    request = _request(db, test_user, status="received", suffix="APPRAISE")
    appraiser = create_admin_user(
        db, email="appraiser@test.com", role_code="appraiser"
    )
    headers = auth_headers(appraiser)

    allowed = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=headers,
        json={"status": "assessing", "assessed_total": 900},
    )
    denied = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=headers,
        json={"status": "cancelled"},
    )

    db.refresh(request)
    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert request.status == "assessing"
    assert request.assessed_total == 900
    assert allowed.json()["user_email"] == ""


@pytest.mark.parametrize(
    ("role_code", "expected_status"),
    [
        ("shipping_manager", 403),
        ("buyback_manager", 200),
        ("admin", 200),
        ("owner", 200),
    ],
)
def test_status_management_permission_by_role(
    api_client, db, test_user, role_code, expected_status
):
    request = _request(db, test_user, suffix=role_code)
    admin = create_admin_user(
        db,
        email=f"{role_code}@test.com",
        role_code=role_code,
    )

    response = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=auth_headers(admin),
        json={"status": "cancelled"},
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("role_code", "expected_status"),
    [
        ("viewer", 403),
        ("appraiser", 403),
        ("shipping_manager", 403),
        ("payment_manager", 400),
        ("buyback_manager", 400),
        ("admin", 400),
        ("owner", 400),
    ],
)
def test_payout_endpoint_permission_by_role(
    api_client, db, test_user, role_code, expected_status
):
    request = _request(db, test_user, suffix=f"PAY-{role_code}")
    admin = create_admin_user(
        db,
        email=f"pay-{role_code}@test.com",
        role_code=role_code,
    )

    response = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/complete-payout",
        headers=auth_headers(admin),
        json={"send_email": False},
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize("target", ["received", "returned", "paid", "shipped", "completed"])
def test_generic_status_api_cannot_enter_dedicated_operation_states(
    api_client, db, test_user, target
):
    request = _request(db, test_user, suffix=f"PROTECTED-{target}")
    manager = create_admin_user(
        db,
        email=f"protected-{target}@test.com",
        role_code="buyback_manager",
    )

    response = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=auth_headers(manager),
        json={"status": target},
    )

    db.refresh(request)
    assert response.status_code == 400
    assert request.status == "submitted"


def test_shipping_manager_has_only_shipping_scope(api_client, db, test_user):
    request = _request(db, test_user, suffix="SHIPPING-SCOPE")
    user = create_admin_user(
        db, email="shipping-scope@test.com", role_code="shipping_manager"
    )
    admin_user = get_admin_user_for_user(db, user, require_active=True)
    assert admin_user is not None
    permissions = load_permissions(admin_user)

    assert "buyback.ship.read" in permissions
    assert "buyback.ship.confirm" in permissions
    assert "buyback.request.read" in permissions
    assert "admin.pii.read" not in permissions
    assert "buyback.ship.pii.read" in permissions
    assert "buyback.receive" not in permissions
    assert "buyback.request.status.write" not in permissions
    assert "buyback.payout.complete" not in permissions

    detail = api_client.get(
        f"/api/admin/buyback/requests/{request.id}",
        headers=auth_headers(user),
    )
    assert detail.status_code == 200
    assert detail.json()["user_email"] == ""
    assert detail.json()["payout_account"] is None
