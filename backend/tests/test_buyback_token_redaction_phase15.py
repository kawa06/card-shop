from __future__ import annotations

import json
import logging
from unittest.mock import patch

from database import engine
import models_buyback
from tests.conftest import auth_headers, create_admin_user
from services.buyback_logistics_logs import write_buyback_audit, write_package_print_log
from tests.test_buyback_receiving import (
    _application_token,
    _create_customer,
    _submit_request,
)


def test_sqlalchemy_never_echoes_bind_parameters():
    assert engine.echo is False
    assert engine.hide_parameters is True


def test_invalid_scanner_input_is_redacted_from_audit_and_logs(
    api_client, db, caplog
):
    admin = create_admin_user(
        db, email="redaction-invalid@test.com", role_code="buyback_manager"
    )
    raw_input = "malformed scanner input with spaces"
    caplog.set_level(logging.DEBUG)

    response = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(admin),
        json={"code": raw_input, "device_info": raw_input},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "無効なバーコードです"
    assert raw_input not in caplog.text
    scan_log = (
        db.query(models_buyback.BuybackPackageScanLog)
        .filter(models_buyback.BuybackPackageScanLog.actor_user_id == admin.id)
        .one()
    )
    assert scan_log.scan_token == "[redacted]"
    assert raw_input not in (scan_log.details_json or "")


def test_structured_scanner_input_does_not_echo_nested_token(api_client, db):
    admin = create_admin_user(
        db, email="redaction-validation@test.com", role_code="buyback_manager"
    )
    token = "V" * 43

    response = api_client.post(
        "/api/admin/buyback/scan",
        headers=auth_headers(admin),
        json={"code": {"nested": token}},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "無効なバーコードです"
    assert token not in response.text
    scan_log = (
        db.query(models_buyback.BuybackPackageScanLog)
        .filter(models_buyback.BuybackPackageScanLog.actor_user_id == admin.id)
        .one()
    )
    assert token not in (scan_log.details_json or "")


def test_notification_exception_cannot_log_raw_scanner_token(
    api_client, db, caplog
):
    admin = create_admin_user(
        db, email="redaction-exception@test.com", role_code="buyback_manager"
    )
    customer = _create_customer(db, email="redaction-customer@example.com")
    request = _submit_request(db, customer)
    token = _application_token(db, request)
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .one()
    )
    caplog.set_level(logging.WARNING)

    with patch(
        "services.buyback_receiving.notify_buyback_inbound_received",
        side_effect=RuntimeError(token),
    ):
        response = api_client.post(
            "/api/admin/buyback/inbound/receive",
            headers=auth_headers(admin),
            json={
                "inbound_shipment_id": inbound.id,
                "scanned_code": token,
            },
        )

    assert response.status_code == 200
    assert token not in response.text
    assert token not in caplog.text


def test_central_audit_and_print_log_redact_token_like_values(db, test_user):
    token = "T" * 43
    write_buyback_audit(
        db,
        actor_user_id=test_user.id,
        action="redaction_test",
        entity_type="test",
        entity_id="1",
        details={
            "scan_token": token,
            "note": f"copied value {token}",
            "authorization": f"Bearer {token}",
        },
    )
    write_package_print_log(
        db,
        actor_user_id=test_user.id,
        print_type="redaction_test",
        entity_type="test",
        entity_id=1,
        device_info=f"device {token}",
    )
    db.commit()

    audit = (
        db.query(models_buyback.BuybackAuditLog)
        .filter(models_buyback.BuybackAuditLog.action == "redaction_test")
        .one()
    )
    details = json.loads(audit.details_json)
    assert details["scan_token"] == "[redacted]"
    assert token not in audit.details_json
    print_log = (
        db.query(models_buyback.BuybackPackagePrintLog)
        .filter(models_buyback.BuybackPackagePrintLog.print_type == "redaction_test")
        .one()
    )
    assert token not in (print_log.device_info or "")
