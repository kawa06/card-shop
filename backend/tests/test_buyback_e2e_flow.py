"""Buyback API end-to-end flow (Phase 9).

Exercises products → cart → request → KYC → admin status → payout over HTTP
against an isolated in-memory database.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_firestore_import import import_firestore_buylist_export
from tests.conftest import admin_headers, auth_headers


def _seed_product(db) -> models_buyback.BuybackProduct:
    import_firestore_buylist_export(
        db,
        {
            "items": [
                {
                    "id": 9001,
                    "name": "E2Eテストカード",
                    "category": "raw",
                    "isPublished": True,
                    "conditionPrices": [
                        {
                            "conditionCode": "A",
                            "conditionName": "極美品",
                            "price": 1500,
                            "isVisible": True,
                        }
                    ],
                }
            ],
            "images": {},
        },
    )
    return (
        db.query(models_buyback.BuybackProduct)
        .filter(models_buyback.BuybackProduct.firestore_item_id == "9001")
        .one()
    )


def _create_customer(db) -> models.User:
    user = models.User(
        email="e2e-customer@example.com",
        name="E2E Customer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@patch("services.buyback_requests.notify_buyback_request_submitted", return_value=(True, None))
@patch("services.buyback_admin.notify_buyback_payout_completed", return_value=(True, None))
def test_buyback_full_api_flow(mock_payout_email, mock_request_email, api_client, db):
    _seed_product(db)
    customer = _create_customer(db)
    headers = auth_headers(customer)
    admin = admin_headers()

    health = api_client.get("/api/buyback/health")
    assert health.status_code == 200
    assert health.json()["phase"] == "10"
    assert health.json()["products_source"] == "postgresql"

    products = api_client.get("/api/buyback/products")
    assert products.status_code == 200
    product_list = products.json()
    assert len(product_list) == 1
    assert product_list[0]["name"] == "E2Eテストカード"
    assert product_list[0]["firestore_item_id"] == "9001"

    cart_add = api_client.post(
        "/api/buyback/cart/items",
        headers=headers,
        json={
            "firestore_item_id": "9001",
            "product_name": "E2Eテストカード",
            "category": "raw",
            "condition_code": "A",
            "unit_price": 1500,
            "quantity": 2,
        },
    )
    assert cart_add.status_code == 201

    cart = api_client.get("/api/buyback/cart", headers=headers)
    assert cart.status_code == 200
    cart_body = cart.json()
    assert cart_body["item_count"] == 2
    assert cart_body["estimated_total"] == 3000

    request_res = api_client.post(
        "/api/buyback/requests",
        headers=headers,
        json={
            "customer_note": "E2E申込テスト",
            "rejected_item_handling": "return_rejected_only",
            "agreed_prepaid_shipping": True,
            "agreed_cod_consequence": True,
            "agreed_condition_rejection": True,
        },
    )
    assert request_res.status_code == 201
    request_id = request_res.json()["id"]
    assert request_res.json()["status"] == "submitted"
    assert request_res.json()["estimated_total"] == 3000

    empty_cart = api_client.get("/api/buyback/cart", headers=headers)
    assert empty_cart.json()["item_count"] == 0

    payout_res = api_client.post(
        "/api/buyback/payout-accounts",
        headers=headers,
        json={
            "bank_name": "テスト銀行",
            "branch_name": "本店",
            "account_type": "ordinary",
            "account_number": "1234567",
            "account_holder": "E2E タロウ",
            "set_default": True,
        },
    )
    assert payout_res.status_code == 201

    front = api_client.post(
        "/api/buyback/identity/documents?side=front",
        headers=headers,
        files={"file": ("front.jpg", BytesIO(b"\xff\xd8\xfffakejpeg"), "image/jpeg")},
    )
    assert front.status_code == 200
    back = api_client.post(
        "/api/buyback/identity/documents?side=back",
        headers=headers,
        files={"file": ("back.png", BytesIO(b"\x89PNG\r\nfakepng"), "image/png")},
    )
    assert back.status_code == 200
    identity_submit = api_client.post(
        "/api/buyback/identity/submit",
        headers=headers,
        json={"document_type": "drivers_license"},
    )
    assert identity_submit.status_code == 200

    verification = (
        db.query(models_buyback.IdentityVerification)
        .filter_by(user_id=customer.id)
        .one()
    )
    verification_id = verification.id

    approve = api_client.post(
        f"/api/admin/buyback/identity/{verification_id}/approve",
        headers=admin,
    )
    assert approve.status_code == 200

    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request_id)
        .one()
    )
    inbound_barcode = (
        db.query(models_buyback.BuybackBarcode)
        .filter(
            models_buyback.BuybackBarcode.entity_type
            == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
            models_buyback.BuybackBarcode.entity_id == inbound.id,
            models_buyback.BuybackBarcode.is_active.is_(True),
        )
        .one()
    )
    scan = api_client.post(
        "/api/admin/buyback/scan",
        headers=admin,
        json={"code": inbound_barcode.scan_token},
    )
    assert scan.status_code == 200
    assert scan.json()["found"] is True
    assert "scan_token" not in scan.json()
    received = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=admin,
        json={
            "inbound_shipment_id": inbound.id,
            "scanned_code": inbound_barcode.scan_token,
            "actual_item_count": 1,
        },
    )
    assert received.status_code == 200
    assert received.json()["request_status"] == "received"
    assert "scan_token" not in received.json()

    transitions = [
        ("assessing", {}),
        ("assessed", {"assessed_total": 2800}),
        ("accepted", {}),
        ("payout_pending", {"payout_total": 2800}),
    ]
    for status, extra in transitions:
        payload = {"status": status, **extra}
        res = api_client.patch(
            f"/api/admin/buyback/requests/{request_id}",
            headers=admin,
            json=payload,
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == status

    payout_done = api_client.post(
        f"/api/admin/buyback/requests/{request_id}/complete-payout",
        headers=admin,
        json={"send_email": True},
    )
    assert payout_done.status_code == 200
    assert payout_done.json()["status"] == "paid"
    assert payout_done.json()["payout_total"] == 2800

    user_requests = api_client.get("/api/buyback/requests", headers=headers)
    assert user_requests.status_code == 200
    assert user_requests.json()[0]["status"] == "paid"

    mock_request_email.assert_called_once()
    mock_payout_email.assert_called_once()


def test_firestore_import_idempotent_via_admin_api(api_client, db):
    payload = {
        "items": [
            {
                "id": 9100,
                "name": "移行テスト",
                "category": "box",
                "price": 3000,
            }
        ],
        "images": {},
    }
    admin = admin_headers()
    first = api_client.post(
        "/api/admin/buyback/import-firestore",
        headers=admin,
        json={"items": payload["items"], "images": payload["images"], "dry_run": False},
    )
    assert first.status_code == 200
    assert first.json()["created"] == 1

    second = api_client.post(
        "/api/admin/buyback/import-firestore",
        headers=admin,
        json={"items": payload["items"], "images": payload["images"], "dry_run": False},
    )
    assert second.status_code == 200
    assert second.json()["updated"] == 1
    assert second.json()["created"] == 0

    stats = api_client.get("/api/buyback/health")
    assert stats.json()["products_source"] == "postgresql"
