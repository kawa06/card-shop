"""Phase 8: buyback logistics RBAC and unified logs."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.admin_rbac import permission_codes_for_role
from services.buyback_cart import add_cart_item
from services.buyback_requests import submit_request_from_cart
from tests.conftest import auth_headers, create_admin_user


def _customer(db, email: str = "logs-customer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="ログテスト客",
        password_hash=hash_password("secret123"),
        is_verified=True,
        phone_number="09099998888",
        postal_code="6500001",
        region="兵庫県",
        city="神戸市",
        address_line1="中央区1-1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _issue_one_package(db, api_client, admin, customer):
    add_cart_item(
        db,
        user_id=customer.id,
        firestore_item_id="fs_logs_001",
        product_name="ログカード",
        category="raw",
        condition_code="A",
        unit_price=300,
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
    request.status = models_buyback.BuybackRequestStatus.assessed.value
    for item in request.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "返送"
    db.commit()
    issued = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=auth_headers(admin),
        json={"total_boxes": 1, "package_kind": "return"},
    )
    assert issued.status_code == 200
    return request, issued.json()[0]


def test_role_permissions_phase8():
    appraiser = permission_codes_for_role("appraiser")
    assert "buyback.receive" in appraiser
    assert "admin.pii.read" not in appraiser
    assert "buyback.ship.confirm" not in appraiser
    assert "buyback.logs.read" in appraiser

    shipping = permission_codes_for_role("shipping_manager")
    assert "admin.pii.read" in shipping
    assert "buyback.ship.confirm" in shipping
    assert "buyback.logs.read" in shipping

    viewer = permission_codes_for_role("viewer")
    assert "buyback.logs.read" in viewer
    assert "admin.csv.export" not in viewer
    assert "buyback.receive" not in viewer


def test_appraiser_scan_hides_address(api_client, db):
    admin = create_admin_user(db, email="appraiser-pii@test.com", role_code="appraiser")
    customer = _customer(db)
    with patch("services.buyback_requests.notify_buyback_request_submitted"):
        add_cart_item(
            db,
            user_id=customer.id,
            firestore_item_id="fs_app_pii",
            product_name="PIIカード",
            category="raw",
            condition_code="A",
            unit_price=100,
            quantity=1,
        )
        request = submit_request_from_cart(
            db,
            user=customer,
            rejected_item_handling="return_rejected_only",
            agreed_prepaid_shipping=True,
            agreed_cod_consequence=True,
            agreed_condition_rejection=True,
        )

    barcode = (
        db.query(models_buyback.BuybackBarcode)
        .filter(
            models_buyback.BuybackBarcode.entity_type
            == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
            models_buyback.BuybackBarcode.barcode_type
            == models_buyback.BuybackBarcodeType.application_inbound.value,
        )
        .order_by(models_buyback.BuybackBarcode.id.desc())
        .first()
    )
    assert barcode is not None
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .first()
    )
    assert inbound is not None
    assert barcode.entity_id == inbound.id

    scan = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(admin),
        json={"code": barcode.scan_token},
    )
    assert scan.status_code == 200
    body = scan.json()
    assert body["found"] is True
    assert body.get("address") in (None, {})
    assert body.get("user_email") in (None, "")
    assert body.get("phone_number") in (None, "")


def test_appraiser_cannot_ship_confirm(api_client, db):
    admin = create_admin_user(db, email="appraiser-ship@test.com", role_code="appraiser")
    res = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={
            "package_id": 1,
            "checklist": {k: True for k in [
                "name_ok", "address_ok", "building_ok", "method_ok", "timeslot_ok",
                "owner_match", "docs_ok", "box_count_ok", "tracking_ok",
            ]},
        },
    )
    assert res.status_code == 403


def test_csv_export_writes_print_and_audit_logs(api_client, db):
    admin = create_admin_user(db, email="logs-csv@test.com", role_code="buyback_manager")
    customer = _customer(db, email="logs-csv-c@example.com")
    _, package = _issue_one_package(db, api_client, admin, customer)

    res = api_client.post(
        "/api/admin/buyback/labels/csv",
        headers=auth_headers(admin),
        json={"package_ids": [package["id"]]},
    )
    assert res.status_code == 200

    print_log = (
        db.query(models_buyback.BuybackPackagePrintLog)
        .filter(
            models_buyback.BuybackPackagePrintLog.print_type == "label_yasan_csv",
            models_buyback.BuybackPackagePrintLog.entity_id == package["id"],
        )
        .first()
    )
    assert print_log is not None
    assert print_log.includes_pii is False

    audit = (
        db.query(models_buyback.BuybackAuditLog)
        .filter(models_buyback.BuybackAuditLog.action == "label_yasan_csv_exported")
        .order_by(models_buyback.BuybackAuditLog.id.desc())
        .first()
    )
    assert audit is not None


def test_list_logistics_logs(api_client, db):
    admin = create_admin_user(db, email="logs-list@test.com", role_code="shipping_manager")
    customer = _customer(db, email="logs-list-c@example.com")
    _, package = _issue_one_package(db, api_client, admin, customer)

    api_client.post(
        "/api/admin/buyback/labels/sheet",
        headers=auth_headers(admin),
        json={"package_ids": [package["id"]], "start_position": 1, "copies": 1},
    )

    res = api_client.get(
        "/api/admin/buyback/logs",
        headers=auth_headers(admin),
        params={"log_type": "print", "per_page": 20},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert any(item["action"] == "label_sheet_72265" for item in body["items"])


def test_sales_manager_cannot_read_buyback_logs(api_client, db):
    admin = create_admin_user(db, email="sales-logs@test.com", role_code="sales_manager")
    res = api_client.get("/api/admin/buyback/logs", headers=auth_headers(admin))
    assert res.status_code == 403
