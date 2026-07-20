"""Outbound package barcode issuance tests (Phase 5)."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_cart import add_cart_item
from services.buyback_requests import submit_request_from_cart
from tests.conftest import auth_headers, create_admin_user


def _customer(db, email: str = "pkg-customer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="梱包テスト客",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _submitted(db, user: models.User) -> models_buyback.BuybackRequest:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_pkg_001",
        product_name="梱包テストカード",
        category="raw",
        condition_code="A",
        unit_price=800,
        quantity=1,
    )
    with patch("services.buyback_requests.notify_buyback_request_submitted"):
        return submit_request_from_cart(
            db,
            user=user,
            rejected_item_handling="return_rejected_only",
            agreed_prepaid_shipping=True,
            agreed_cod_consequence=True,
            agreed_condition_rejection=True,
        )


def _to_assessed(db, request: models_buyback.BuybackRequest) -> None:
    request.status = models_buyback.BuybackRequestStatus.assessed.value
    for item in request.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "テスト返送"
    db.commit()


def test_issue_multi_box_packages(api_client, db):
    admin = create_admin_user(db, email="pkg-admin@test.com", role_code="buyback_manager")
    customer = _customer(db)
    request = _submitted(db, customer)
    _to_assessed(db, request)

    res = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
        json={
            "total_boxes": 3,
            "package_kind": "return",
            "preferred_time_slot": "14-16時",
        },
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 3
    assert rows[0]["package_code"].endswith("-01")
    assert rows[1]["package_code"].endswith("-02")
    assert rows[2]["package_code"].endswith("-03")
    assert rows[0]["scan_token"]
    assert rows[0]["preferred_time_slot"] == "14-16時"
    assert rows[0]["status"] == "packing"
    # Box 1 has return items attached
    assert len(rows[0]["items"]) >= 1

    listed = api_client.get(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 3


def test_complete_package_and_label(api_client, db):
    admin = create_admin_user(db, email="pkg-complete@test.com", role_code="shipping_manager")
    customer = _customer(db, email="pkg2@example.com")
    request = _submitted(db, customer)
    _to_assessed(db, request)

    issued = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
        json={"total_boxes": 1, "package_kind": "return"},
    )
    assert issued.status_code == 200
    package_id = issued.json()[0]["id"]

    done = api_client.post(
        f"/api/admin/buyback/packages/{package_id}/complete",
        headers=auth_headers(admin),
        json={"tracking_number": "TRACK-PKG-001"},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "packed"
    assert done.json()["tracking_number"] == "TRACK-PKG-001"

    label = api_client.get(
        f"/api/admin/buyback/packages/{package_id}/label",
        headers=auth_headers(admin),
    )
    assert label.status_code == 200
    body = label.json()
    assert body["package_code"].endswith("-01")
    assert body["applicant_name"] == "梱包テスト客"
    assert body["scan_token"]


def test_cannot_issue_while_submitted(api_client, db):
    admin = create_admin_user(db, email="pkg-early@test.com", role_code="admin")
    customer = _customer(db, email="pkg3@example.com")
    request = _submitted(db, customer)

    res = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
        json={"total_boxes": 1},
    )
    assert res.status_code == 400


def test_viewer_cannot_issue_packages(api_client, db):
    viewer = create_admin_user(db, email="pkg-viewer@test.com", role_code="viewer")
    customer = _customer(db, email="pkg4@example.com")
    request = _submitted(db, customer)
    _to_assessed(db, request)

    res = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(viewer),
        json={"total_boxes": 1},
    )
    assert res.status_code == 403
