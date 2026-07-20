"""Admin buyback inbound scan / receive tests (Phase 4)."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_barcodes import get_active_barcode_for_entity
from services.buyback_cart import add_cart_item
from services.buyback_requests import submit_request_from_cart
from tests.conftest import auth_headers, create_admin_user


def _create_customer(db, email: str = "recv-customer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="受付テスト客",
        password_hash=hash_password("secret123"),
        is_verified=True,
        phone_number="09012345678",
        postal_code="6500001",
        region="兵庫県",
        city="神戸市",
        address_line1="中央区1-1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _submit_request(db, user: models.User) -> models_buyback.BuybackRequest:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_recv_001",
        product_name="受付テストカード",
        category="raw",
        condition_code="A",
        unit_price=1200,
        quantity=2,
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


def _application_token(db, request: models_buyback.BuybackRequest) -> str:
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .first()
    )
    assert inbound is not None
    barcode = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
    )
    assert barcode is not None
    return barcode.scan_token


def test_scan_not_found(api_client, db, seed_admin_rbac_data):
    admin = create_admin_user(db, email="recv-admin@test.com", role_code="buyback_manager")
    res = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(admin),
        json={"code": "NO-SUCH-TOKEN"},
    )
    assert res.status_code == 200
    assert res.json()["found"] is False


def test_scan_and_receive_flow(api_client, db, seed_admin_rbac_data):
    admin = create_admin_user(db, email="recv-flow@test.com", role_code="buyback_manager")
    customer = _create_customer(db)
    request = _submit_request(db, customer)
    token = _application_token(db, request)

    scan = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(admin),
        json={"code": token, "device_info": "pytest"},
    )
    assert scan.status_code == 200
    body = scan.json()
    assert body["found"] is True
    assert body["can_receive"] is True
    assert body["applicant_name"] == "受付テスト客"
    assert body["public_buyback_code"].startswith("KRX-BUY-")
    assert body["inbound_mgmt_id"].startswith("KRX-PKG-")
    assert body["user_email"] == customer.email  # buyback_manager has pii
    assert len(body["items"]) == 1

    receive = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(admin),
        json={
            "inbound_shipment_id": body["inbound_shipment_id"],
            "scanned_code": token,
            "box_count": 1,
            "actual_item_count": 2,
            "admin_note": "受付OK",
            "device_info": "pytest",
        },
    )
    assert receive.status_code == 200
    after = receive.json()
    assert after["request_status"] == "received"
    assert after["inbound_status"] == "received"
    assert after["can_receive"] is False
    assert after["already_received"] is True
    assert len(after["receipts"]) >= 1

    db.refresh(request)
    assert request.status == "received"
    assert request.received_by_user_id == admin.id


def test_scan_by_inbound_mgmt_id(api_client, db, seed_admin_rbac_data):
    admin = create_admin_user(db, email="recv-mgmt@test.com", role_code="appraiser")
    customer = _create_customer(db, email="recv2@example.com")
    request = _submit_request(db, customer)

    scan = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(admin),
        json={"code": request.inbound_mgmt_id},
    )
    assert scan.status_code == 200
    body = scan.json()
    assert body["found"] is True
    # appraiser lacks admin.pii.read
    assert body["user_email"] is None
    assert body["phone_number"] is None
    assert body["address"] is None
    assert body["applicant_name"] == "受付テスト客"


def test_viewer_cannot_scan(api_client, db, seed_admin_rbac_data):
    viewer = create_admin_user(db, email="recv-viewer@test.com", role_code="viewer")
    res = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(viewer),
        json={"code": "anything"},
    )
    assert res.status_code == 403


def test_cancelled_cannot_receive(api_client, db, seed_admin_rbac_data):
    admin = create_admin_user(db, email="recv-cancel@test.com", role_code="admin")
    customer = _create_customer(db, email="recv3@example.com")
    request = _submit_request(db, customer)
    request.status = models_buyback.BuybackRequestStatus.cancelled.value
    db.commit()

    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .first()
    )
    res = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(admin),
        json={"inbound_shipment_id": inbound.id, "box_count": 1},
    )
    assert res.status_code == 400
