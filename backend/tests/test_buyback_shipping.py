"""Pre-shipment verification and confirm tests (Phase 6)."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_cart import add_cart_item
from services.buyback_requests import submit_request_from_cart
from tests.conftest import auth_headers, create_admin_user

ALL_CHECKS = {
    "name_ok": True,
    "address_ok": True,
    "building_ok": True,
    "method_ok": True,
    "timeslot_ok": True,
    "owner_match": True,
    "docs_ok": True,
    "box_count_ok": True,
    "tracking_ok": True,
}


def _customer(db, email: str = "ship-customer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="発送テスト客",
        password_hash=hash_password("secret123"),
        is_verified=True,
        phone_number="09011112222",
        postal_code="6500001",
        region="兵庫県",
        city="神戸市",
        address_line1="中央区テスト1-1",
        address_line2="101",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _prepare_packed_package(db, api_client, admin, customer):
    add_cart_item(
        db,
        user_id=customer.id,
        firestore_item_id="fs_ship_001",
        product_name="発送テストカード",
        category="raw",
        condition_code="A",
        unit_price=500,
        quantity=1,
    )
    with patch("services.buyback_requests.notify_buyback_request_submitted"):
        request = submit_request_from_cart(
            db,
            user=customer,
            rejected_item_handling="return_rejected_only",
            agreed_prepaid_shipping=True,
            agreed_cod_consequence=True,
            agreed_condition_rejection=True,
        )
    request.status = models_buyback.BuybackRequestStatus.rejected.value
    for item in request.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "返送テスト"
    db.commit()

    issued = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
        json={
            "total_boxes": 1,
            "package_kind": "return",
            "preferred_time_slot": "14-16時",
        },
    )
    assert issued.status_code == 200
    package = issued.json()[0]
    done = api_client.post(
        f"/api/admin/buyback/packages/{package['id']}/complete",
        headers=auth_headers(admin),
        json={"tracking_number": "SHIP-TRACK-001"},
    )
    assert done.status_code == 200
    return request, package


def test_ship_scan_and_confirm(api_client, db):
    admin = create_admin_user(db, email="ship-admin@test.com", role_code="shipping_manager")
    customer = _customer(db)
    request, package = _prepare_packed_package(db, api_client, admin, customer)

    scan = api_client.post(
        "/api/admin/buyback/ship/scan",
        headers=auth_headers(admin),
        json={"code": package["scan_token"]},
    )
    assert scan.status_code == 200
    body = scan.json()
    assert body["found"] is True
    assert body["can_confirm"] is True
    assert body["destination_name"] == "発送テスト客"
    assert body["destination_address"]["postal_code"] == "6500001"
    assert body["preferred_time_slot"] == "14-16時"
    assert len(body["checklist_items"]) == 9

    confirm = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={
            "package_id": package["id"],
            "checklist": ALL_CHECKS,
            "scanned_code": package["scan_token"],
        },
    )
    assert confirm.status_code == 200
    after = confirm.json()
    assert after["already_shipped"] is True
    assert after["can_confirm"] is False
    assert after["package_status"] == "shipped"

    conf = (
        db.query(models_buyback.BuybackShipmentConfirmation)
        .filter(models_buyback.BuybackShipmentConfirmation.package_id == package["id"])
        .first()
    )
    assert conf is not None
    snap = (
        db.query(models_buyback.BuybackShipmentAddressSnapshot)
        .filter(models_buyback.BuybackShipmentAddressSnapshot.confirmation_id == conf.id)
        .first()
    )
    assert snap is not None
    assert snap.recipient_name == "発送テスト客"
    assert snap.postal_code == "6500001"

    db.refresh(request)
    assert request.status == "returned"


def test_double_ship_blocked(api_client, db):
    admin = create_admin_user(db, email="ship-dup@test.com", role_code="shipping_manager")
    customer = _customer(db, email="ship2@example.com")
    _, package = _prepare_packed_package(db, api_client, admin, customer)

    first = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={"package_id": package["id"], "checklist": ALL_CHECKS},
    )
    assert first.status_code == 200

    second = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={"package_id": package["id"], "checklist": ALL_CHECKS},
    )
    assert second.status_code == 400
    assert "二重発送" in second.json()["detail"] or "発送済み" in second.json()["detail"]

    rescan = api_client.post(
        "/api/admin/buyback/ship/scan",
        headers=auth_headers(admin),
        json={"code": package["package_code"]},
    )
    assert rescan.status_code == 200
    assert rescan.json()["already_shipped"] is True


def test_incomplete_checklist_blocked(api_client, db):
    admin = create_admin_user(db, email="ship-check@test.com", role_code="buyback_manager")
    customer = _customer(db, email="ship3@example.com")
    _, package = _prepare_packed_package(db, api_client, admin, customer)

    incomplete = dict(ALL_CHECKS)
    incomplete["address_ok"] = False
    res = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={"package_id": package["id"], "checklist": incomplete},
    )
    assert res.status_code == 400


def test_incomplete_address_blocks_confirm(api_client, db):
    admin = create_admin_user(db, email="ship-addr@test.com", role_code="shipping_manager")
    customer = _customer(db, email="ship4@example.com")
    customer.address_line1 = None
    customer.city = None
    db.commit()
    _, package = _prepare_packed_package(db, api_client, admin, customer)

    res = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={"package_id": package["id"], "checklist": ALL_CHECKS},
    )
    assert res.status_code == 400
    assert "住所" in res.json()["detail"]


def test_cancelled_blocks_confirm(api_client, db):
    admin = create_admin_user(db, email="ship-cancel@test.com", role_code="admin")
    customer = _customer(db, email="ship5@example.com")
    request, package = _prepare_packed_package(db, api_client, admin, customer)
    request.status = models_buyback.BuybackRequestStatus.cancelled.value
    db.commit()

    res = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={"package_id": package["id"], "checklist": ALL_CHECKS},
    )
    assert res.status_code == 400
