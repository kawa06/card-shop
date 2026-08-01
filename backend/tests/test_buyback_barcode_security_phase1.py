"""Security regressions for buyback barcode Phase 1."""

from __future__ import annotations

from datetime import datetime, timedelta

import models_buyback
from services.buyback_barcodes import (
    create_barcode,
    get_active_barcode_for_entity,
    revoke_barcode,
)
from tests.conftest import auth_headers, create_admin_user
from tests.test_buyback_receiving import _create_customer, _submit_request
from tests.test_buyback_shipping import ALL_CHECKS, _customer, _prepare_packed_package


INVALID_MESSAGE = "無効なバーコードです"


def _inbound_and_barcode(db, request):
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .one()
    )
    barcode = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
    )
    assert barcode is not None
    return inbound, barcode


def _receive_state(db, request_id: int, inbound_id: int) -> tuple:
    db.expire_all()
    request = db.query(models_buyback.BuybackRequest).filter_by(id=request_id).one()
    inbound = db.query(models_buyback.BuybackInboundShipment).filter_by(id=inbound_id).one()
    items = (
        db.query(models_buyback.BuybackRequestItem)
        .filter_by(request_id=request_id)
        .order_by(models_buyback.BuybackRequestItem.id)
        .all()
    )
    return (
        request.status,
        request.received_at,
        request.received_by_user_id,
        request.updated_at,
        inbound.status,
        inbound.actual_item_count,
        inbound.condition_note,
        inbound.updated_at,
        db.query(models_buyback.BuybackPackageReceipt).filter_by(
            inbound_shipment_id=inbound_id
        ).count(),
        db.query(models_buyback.BuybackStatusHistory).filter_by(
            request_id=request_id
        ).count(),
        tuple((item.id, item.line_status, item.return_status) for item in items),
    )


def _ship_state(db, request_id: int, package_id: int) -> tuple:
    db.expire_all()
    request = db.query(models_buyback.BuybackRequest).filter_by(id=request_id).one()
    package = (
        db.query(models_buyback.BuybackShipmentPackage).filter_by(id=package_id).one()
    )
    items = (
        db.query(models_buyback.BuybackRequestItem)
        .filter_by(request_id=request_id)
        .order_by(models_buyback.BuybackRequestItem.id)
        .all()
    )
    return (
        request.status,
        request.updated_at,
        package.status,
        package.shipped_at,
        package.updated_at,
        db.query(models_buyback.BuybackShipmentConfirmation).filter_by(
            package_id=package_id
        ).count(),
        db.query(models_buyback.BuybackShipmentAddressSnapshot).count(),
        db.query(models_buyback.BuybackStatusHistory).filter_by(
            request_id=request_id
        ).count(),
        tuple(
            (item.id, item.line_status, item.return_status, item.return_tracking_number)
            for item in items
        ),
    )


def test_receive_rejects_missing_invalid_and_predictable_values_without_mutation(
    api_client, db
):
    admin = create_admin_user(db, email="phase1-receive-invalid@test.com")
    request = _submit_request(db, _create_customer(db, "phase1-recv@example.com"))
    inbound, _ = _inbound_and_barcode(db, request)
    before = _receive_state(db, request.id, inbound.id)

    attempts = [
        {},
        {"scanned_code": None},
        {"scanned_code": ""},
        {"scanned_code": "not-a-token"},
        {"scanned_code": "A" * 43},
        {"scanned_code": request.public_buyback_code},
        {"scanned_code": request.request_number},
        {"scanned_code": request.inbound_mgmt_id},
        {"scanned_code": inbound.inbound_mgmt_id},
        {"scanned_code": str(request.id)},
        {"scanned_code": str(inbound.id)},
    ]
    for attempt in attempts:
        response = api_client.post(
            "/api/admin/buyback/inbound/receive",
            headers=auth_headers(admin),
            json={
                "inbound_shipment_id": inbound.id,
                "box_count": 9,
                "actual_item_count": 99,
                "admin_note": "must not persist",
                **attempt,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_MESSAGE
        assert _receive_state(db, request.id, inbound.id) == before

    direct_status = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=auth_headers(admin),
        json={"status": "received", "admin_note": "direct bypass"},
    )
    assert direct_status.status_code == 400
    assert direct_status.json()["detail"] == INVALID_MESSAGE
    assert _receive_state(db, request.id, inbound.id) == before

    logs = db.query(models_buyback.BuybackPackageScanLog).all()
    assert logs
    assert all(log.scan_token == "[redacted]" for log in logs)


def test_receive_rejects_inactive_expired_wrong_purpose_and_other_request_tokens(
    api_client, db
):
    admin = create_admin_user(db, email="phase1-receive-binding@test.com")
    request = _submit_request(db, _create_customer(db, "phase1-bind1@example.com"))
    inbound, barcode = _inbound_and_barcode(db, request)
    other_request = _submit_request(
        db, _create_customer(db, "phase1-bind2@example.com")
    )
    _, other_barcode = _inbound_and_barcode(db, other_request)
    before = _receive_state(db, request.id, inbound.id)

    wrong_purpose = create_barcode(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound.id,
        barcode_type=models_buyback.BuybackBarcodeType.package_outbound.value,
    )
    db.commit()

    for token in (other_barcode.scan_token, wrong_purpose.scan_token):
        response = api_client.post(
            "/api/admin/buyback/inbound/receive",
            headers=auth_headers(admin),
            json={"inbound_shipment_id": inbound.id, "scanned_code": token},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_MESSAGE
        assert _receive_state(db, request.id, inbound.id) == before

    barcode.expires_at = datetime.utcnow() - timedelta(seconds=1)
    response = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(admin),
        json={"inbound_shipment_id": inbound.id, "scanned_code": barcode.scan_token},
    )
    assert response.status_code == 400
    assert _receive_state(db, request.id, inbound.id) == before
    del barcode.expires_at

    revoke_barcode(db, barcode)
    db.commit()
    response = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(admin),
        json={"inbound_shipment_id": inbound.id, "scanned_code": barcode.scan_token},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == INVALID_MESSAGE
    assert _receive_state(db, request.id, inbound.id) == before


def test_receive_permission_denied_does_not_mutate(api_client, db):
    viewer = create_admin_user(
        db, email="phase1-receive-viewer@test.com", role_code="viewer"
    )
    request = _submit_request(db, _create_customer(db, "phase1-perm@example.com"))
    inbound, barcode = _inbound_and_barcode(db, request)
    before = _receive_state(db, request.id, inbound.id)

    response = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(viewer),
        json={"inbound_shipment_id": inbound.id, "scanned_code": barcode.scan_token},
    )
    assert response.status_code == 403
    assert _receive_state(db, request.id, inbound.id) == before
    assert (
        db.query(models_buyback.BuybackAuditLog)
        .filter_by(actor_user_id=viewer.id, action="permission_denied")
        .count()
        == 1
    )


def test_receive_duplicate_is_rejected_without_second_state_change(api_client, db):
    admin = create_admin_user(db, email="phase1-receive-duplicate@test.com")
    request = _submit_request(db, _create_customer(db, "phase1-dup@example.com"))
    inbound, barcode = _inbound_and_barcode(db, request)
    payload = {
        "inbound_shipment_id": inbound.id,
        "scanned_code": barcode.scan_token,
        "actual_item_count": 2,
    }

    first = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(admin),
        json=payload,
    )
    assert first.status_code == 200
    after_first = _receive_state(db, request.id, inbound.id)

    second = api_client.post(
        "/api/admin/buyback/inbound/receive",
        headers=auth_headers(admin),
        json={**payload, "actual_item_count": 999},
    )
    assert second.status_code == 409
    assert _receive_state(db, request.id, inbound.id) == after_first


def test_ship_rejects_missing_invalid_and_predictable_values_without_mutation(
    api_client, db
):
    admin = create_admin_user(
        db, email="phase1-ship-invalid@test.com", role_code="buyback_manager"
    )
    request, package = _prepare_packed_package(
        db, api_client, admin, _customer(db, "phase1-ship@example.com")
    )
    before = _ship_state(db, request.id, package["id"])

    attempts = [
        {},
        {"scanned_code": None},
        {"scanned_code": ""},
        {"scanned_code": "not-a-token"},
        {"scanned_code": "B" * 43},
        {"scanned_code": package["package_code"]},
        {"scanned_code": str(package["id"])},
        {"scanned_code": str(request.id)},
        {"scanned_code": request.public_buyback_code},
    ]
    for attempt in attempts:
        response = api_client.post(
            "/api/admin/buyback/ship/confirm",
            headers=auth_headers(admin),
            json={"package_id": package["id"], "checklist": ALL_CHECKS, **attempt},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_MESSAGE
        assert _ship_state(db, request.id, package["id"]) == before

    direct_status = api_client.patch(
        f"/api/admin/buyback/requests/{request.id}",
        headers=auth_headers(admin),
        json={"status": "returned", "admin_note": "direct bypass"},
    )
    assert direct_status.status_code == 400
    assert direct_status.json()["detail"] == INVALID_MESSAGE
    assert _ship_state(db, request.id, package["id"]) == before

    request_item = (
        db.query(models_buyback.BuybackRequestItem)
        .filter_by(request_id=request.id)
        .one()
    )
    for return_status in ("pending", "shipped", "completed"):
        direct_item = api_client.patch(
            f"/api/admin/buyback/requests/{request.id}/items",
            headers=auth_headers(admin),
            json={
                "items": [
                    {"id": request_item.id, "return_status": return_status}
                ],
                "recalculate_assessed_total": False,
                "apply_handling_policy": False,
            },
        )
        assert direct_item.status_code == 400
        assert direct_item.json()["detail"] == INVALID_MESSAGE
        assert _ship_state(db, request.id, package["id"]) == before


def test_ship_rejects_inactive_and_other_package_tokens_without_mutation(
    api_client, db
):
    admin = create_admin_user(
        db, email="phase1-ship-binding@test.com", role_code="shipping_manager"
    )
    request, package = _prepare_packed_package(
        db, api_client, admin, _customer(db, "phase1-ship-bind1@example.com")
    )
    stored_package = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter_by(id=package["id"])
        .one()
    )
    stored_package.tracking_number = "SHIP-TRACK-OTHER-1"
    db.commit()
    _, other_package = _prepare_packed_package(
        db, api_client, admin, _customer(db, "phase1-ship-bind2@example.com")
    )
    before = _ship_state(db, request.id, package["id"])

    response = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={
            "package_id": package["id"],
            "checklist": ALL_CHECKS,
            "scanned_code": other_package["test_scan_token"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == INVALID_MESSAGE
    assert _ship_state(db, request.id, package["id"]) == before

    barcode = (
        db.query(models_buyback.BuybackBarcode)
        .filter_by(scan_token=package["test_scan_token"])
        .one()
    )
    revoke_barcode(db, barcode)
    db.commit()
    response = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(admin),
        json={
            "package_id": package["id"],
            "checklist": ALL_CHECKS,
            "scanned_code": package["test_scan_token"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == INVALID_MESSAGE
    assert _ship_state(db, request.id, package["id"]) == before


def test_ship_permission_denied_does_not_mutate(api_client, db):
    packer = create_admin_user(
        db, email="phase1-ship-packer@test.com", role_code="buyback_manager"
    )
    request, package = _prepare_packed_package(
        db, api_client, packer, _customer(db, "phase1-ship-perm@example.com")
    )
    viewer = create_admin_user(
        db, email="phase1-ship-viewer@test.com", role_code="viewer"
    )
    before = _ship_state(db, request.id, package["id"])

    response = api_client.post(
        "/api/admin/buyback/ship/confirm",
        headers=auth_headers(viewer),
        json={
            "package_id": package["id"],
            "checklist": ALL_CHECKS,
            "scanned_code": package["test_scan_token"],
        },
    )
    assert response.status_code == 403
    assert _ship_state(db, request.id, package["id"]) == before
