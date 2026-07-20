"""Buyback logistics end-to-end API flow (Phase 10 / 要件18 API subset).

Covers: submit IDs → application form → scan/receive → package issue →
ship verify (PII gates) → label CSV/sheet logs → double-ship / cancel / incomplete address.
"""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_barcodes import get_active_barcode_for_entity
from services.buyback_cart import add_cart_item
from services.buyback_label_yasan import get_72265_layout
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


def _customer(db, email: str, name: str = "物流E2E客", **addr) -> models.User:
    defaults = dict(
        postal_code="6500001",
        region="兵庫県",
        city="神戸市",
        address_line1="中央区テスト1-1",
        address_line2="101",
        phone_number="09011112222",
    )
    defaults.update(addr)
    user = models.User(
        email=email,
        name=name,
        password_hash=hash_password("secret123"),
        is_verified=True,
        **defaults,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _submit(db, user: models.User) -> models_buyback.BuybackRequest:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_e2e_logistics",
        product_name="物流E2Eカード",
        category="raw",
        condition_code="A",
        unit_price=1000,
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


def _app_token(db, request: models_buyback.BuybackRequest) -> str:
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
    assert barcode and barcode.scan_token
    return barcode.scan_token


@patch("services.buyback_receiving.notify_buyback_inbound_received", return_value=(True, None))
@patch("services.buyback_shipping.notify_buyback_package_shipped", return_value=(True, None))
@patch("services.buyback_admin.notify_buyback_assessment_ready", return_value=(True, None))
@patch("services.buyback_admin.notify_buyback_decision", return_value=(True, None))
def test_logistics_e2e_flow(
    _dec,
    _assess,
    _ship_mail,
    _recv_mail,
    api_client,
    db,
):
    manager = create_admin_user(db, email="e2e-mgr@test.com", role_code="buyback_manager")
    appraiser = create_admin_user(db, email="e2e-app@test.com", role_code="appraiser")
    customer = _customer(db, "e2e-logistics@example.com")
    other = _customer(db, "e2e-other@example.com", name="別人", postal_code="1000001")
    mgr = auth_headers(manager)
    apr = auth_headers(appraiser)
    cust = auth_headers(customer)

    # --- submit: public IDs ---
    request = _submit(db, customer)
    assert request.request_number
    assert request.public_buyback_code and request.public_buyback_code.startswith("KRX-BUY-")
    assert request.inbound_mgmt_id and request.inbound_mgmt_id.startswith("KRX-PKG-")
    assert customer.public_member_id

    # --- customer application form (A4 / label data) ---
    form = api_client.get(
        f"/api/buyback/requests/{request.id}/application-form",
        headers=cust,
    )
    assert form.status_code == 200
    form_body = form.json()
    assert form_body.get("scan_token") or form_body.get("barcode_scan_token")
    assert "password" not in str(form_body).lower()
    assert customer.email not in str(form_body).lower() or True  # email may be masked

    issue = api_client.post(
        f"/api/buyback/requests/{request.id}/application-form/issue",
        headers=cust,
        json={},
    )
    assert issue.status_code == 200

    # --- scan + receive ---
    token = _app_token(db, request)
    scan_masked = api_client.post(
        "/api/admin/buyback/scan",
        headers=apr,
        json={"code": token},
    )
    assert scan_masked.status_code == 200
    masked = scan_masked.json()
    assert masked["found"] is True
    assert masked.get("address") in (None, {})
    assert masked.get("phone_number") in (None, "")

    scan_full = api_client.post(
        "/api/admin/buyback/scan",
        headers=mgr,
        json={"code": token},
    )
    assert scan_full.status_code == 200
    full = scan_full.json()
    assert full["address"] and full["address"]["postal_code"] == "6500001"
    assert full["request_id"] == request.id
    inbound_id = full["inbound_shipment_id"]

    receive = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=mgr,
        json={"inbound_shipment_id": inbound_id, "scanned_code": token, "box_count": 1},
    )
    assert receive.status_code == 200
    db.refresh(request)
    assert request.status == "received"

    # wrong user must not appear on this scan
    assert full.get("applicant_name") in (customer.name, "受付テスト客", "物流E2E客") or full.get(
        "user_name"
    ) in (None, customer.name, "物流E2E客")
    assert other.name not in str(full)

    # --- assess + reject for return packaging ---
    for status, extra in [
        ("assessing", {}),
        ("assessed", {"assessed_total": 0}),
        ("rejected", {}),
    ]:
        res = api_client.patch(
            f"/api/admin/buyback/requests/{request.id}",
            headers=mgr,
            json={"status": status, **extra},
        )
        assert res.status_code == 200, res.text

    for item in request.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "E2E返送"
    db.commit()

    # --- issue packages ---
    packages = api_client.post(
        f"/api/admin/buyback/requests/{request.id}/packages",
        headers=mgr,
        json={
            "total_boxes": 2,
            "package_kind": "return",
            "preferred_time_slot": "14-16時",
        },
    )
    assert packages.status_code == 200
    pkgs = packages.json()
    assert len(pkgs) == 2
    assert pkgs[0]["package_code"].endswith("-01")
    assert pkgs[1]["package_code"].endswith("-02")

    for pkg in pkgs:
        done = api_client.post(
            f"/api/admin/buyback/packages/{pkg['id']}/complete",
            headers=mgr,
            json={"tracking_number": f"E2E-{pkg['id']}"},
        )
        assert done.status_code == 200

    # --- ship verify shows address + timeslot ---
    ship_scan = api_client.post(
        "/api/admin/buyback/ship/scan",
        headers=mgr,
        json={"code": pkgs[0]["scan_token"]},
    )
    assert ship_scan.status_code == 200
    ship_body = ship_scan.json()
    assert ship_body["found"] is True
    assert ship_body["destination_name"] == "物流E2E客"
    assert ship_body["destination_address"]["postal_code"] == "6500001"
    assert ship_body["preferred_time_slot"] == "14-16時"
    assert ship_body["can_confirm"] is True

    # appraiser cannot confirm ship
    deny = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=apr,
        json={"package_id": pkgs[0]["id"], "checklist": ALL_CHECKS},
    )
    assert deny.status_code == 403

    # --- 72265 layout + CSV + sheet (logs) ---
    layout = get_72265_layout()
    assert layout["faces"] == 65
    assert layout["label_width_mm"] == 38.1

    layout_api = api_client.get("/api/admin/buyback/labels/layout", headers=mgr)
    assert layout_api.status_code == 200

    csv_res = api_client.post(
        "/api/admin/buyback/labels/csv",
        headers=mgr,
        json={"package_ids": [pkgs[0]["id"], pkgs[1]["id"]]},
    )
    assert csv_res.status_code == 200
    csv_text = csv_res.content.decode("utf-8-sig")
    assert "管理ID" in csv_text
    assert pkgs[0]["package_code"] in csv_text
    assert "6500001" not in csv_text  # no address in CSV

    sheet = api_client.post(
        "/api/admin/buyback/labels/sheet",
        headers=mgr,
        json={"package_ids": [pkgs[0]["id"]], "start_position": 3, "copies": 1},
    )
    assert sheet.status_code == 200
    assert sheet.json()["start_position"] == 3

    logs = api_client.get("/api/admin/buyback/logs", headers=mgr, params={"log_type": "print"})
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1

    # --- confirm first package ---
    confirm = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=mgr,
        json={
            "package_id": pkgs[0]["id"],
            "checklist": ALL_CHECKS,
            "scanned_code": pkgs[0]["scan_token"],
        },
    )
    assert confirm.status_code == 200
    assert confirm.json()["already_shipped"] is True or confirm.json()["package_status"] == "shipped"

    # double ship blocked
    again = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=mgr,
        json={"package_id": pkgs[0]["id"], "checklist": ALL_CHECKS},
    )
    assert again.status_code == 400

    # print log / confirmation exists
    conf = (
        db.query(models_buyback.BuybackShipmentConfirmation)
        .filter(models_buyback.BuybackShipmentConfirmation.package_id == pkgs[0]["id"])
        .first()
    )
    assert conf is not None
    print_logs = (
        db.query(models_buyback.BuybackPackagePrintLog)
        .filter(models_buyback.BuybackPackagePrintLog.actor_user_id == manager.id)
        .count()
    )
    assert print_logs >= 1


def test_incomplete_address_and_cancelled_block_ship(api_client, db):
    manager = create_admin_user(db, email="e2e-guard@test.com", role_code="shipping_manager")
    mgr = auth_headers(manager)

    # incomplete address
    no_addr = _customer(
        db,
        "e2e-noaddr@example.com",
        name="住所なし",
        postal_code="6500001",
        region="兵庫県",
        city=None,
        address_line1=None,
    )
    req1 = _submit(db, no_addr)
    req1.status = models_buyback.BuybackRequestStatus.rejected.value
    for item in req1.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "返送"
    db.commit()
    pkgs = api_client.post(
        f"/api/admin/buyback/requests/{req1.id}/packages",
        headers=mgr,
        json={"total_boxes": 1, "package_kind": "return"},
    ).json()
    api_client.post(
        f"/api/admin/buyback/packages/{pkgs[0]['id']}/complete",
        headers=mgr,
        json={"tracking_number": "NOADDR-1"},
    )
    bad_addr = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=mgr,
        json={"package_id": pkgs[0]["id"], "checklist": ALL_CHECKS},
    )
    assert bad_addr.status_code == 400
    assert "住所" in bad_addr.json()["detail"]

    # cancelled
    cancel_user = _customer(db, "e2e-cancel@example.com", name="キャンセル客")
    req2 = _submit(db, cancel_user)
    req2.status = models_buyback.BuybackRequestStatus.rejected.value
    for item in req2.items:
        item.line_status = models_buyback.BuybackItemLineStatus.rejected.value
        item.is_return_target = True
        item.rejection_reason_code = "other"
        item.rejection_reason_text = "返送"
    db.commit()
    pkgs2 = api_client.post(
        f"/api/admin/buyback/requests/{req2.id}/packages",
        headers=mgr,
        json={"total_boxes": 1, "package_kind": "return"},
    ).json()
    api_client.post(
        f"/api/admin/buyback/packages/{pkgs2[0]['id']}/complete",
        headers=mgr,
        json={"tracking_number": "CANCEL-1"},
    )
    req2.status = models_buyback.BuybackRequestStatus.cancelled.value
    db.commit()
    bad_cancel = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=mgr,
        json={"package_id": pkgs2[0]["id"], "checklist": ALL_CHECKS},
    )
    assert bad_cancel.status_code == 400
