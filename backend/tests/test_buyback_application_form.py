"""Customer application form API tests (Phase 3)."""

from __future__ import annotations

from unittest.mock import patch

from auth import create_access_token, hash_password
import models
import models_buyback
from services.buyback_application_form import can_print_application_form
from services.buyback_cart import add_cart_item
from services.buyback_requests import submit_request_from_cart


def _create_user(db, email: str = "print@example.com") -> models.User:
    user = models.User(
        email=email,
        name="印刷太郎",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: models.User) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _seed_and_submit(db, user: models.User) -> models_buyback.BuybackRequest:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_print_001",
        product_name="印刷テストカード",
        category="raw",
        condition_code="A",
        unit_price=2000,
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


def test_get_application_form_requires_auth(api_client, db):
    user = _create_user(db)
    request = _seed_and_submit(db, user)

    res = api_client.get(f"/api/buyback/requests/{request.id}/application-form")
    assert res.status_code == 401


def test_get_application_form_payload_is_pii_minimized(api_client, db):
    user = _create_user(db)
    request = _seed_and_submit(db, user)

    res = api_client.get(
        f"/api/buyback/requests/{request.id}/application-form",
        headers=_auth_header(user),
    )
    assert res.status_code == 200
    body = res.json()

    assert body["shop_name"]
    assert body["public_buyback_code"].startswith("KRX-BUY-")
    assert body["inbound_mgmt_id"].startswith("KRX-PKG-")
    assert body["applicant_name"] == "印刷太郎"
    assert body["declared_item_count"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["product_name"] == "印刷テストカード"
    assert "scan_token" not in body
    assert body["identity_status_label"]
    assert len(body["notices"]) >= 4

    # Must not leak sensitive fields
    raw = res.text.lower()
    assert "password" not in raw
    assert "account_number" not in raw
    assert "storage_key" not in raw
    assert user.email.lower() not in raw
    assert "postal_code" not in body
    assert "phone_number" not in body
    assert "address" not in body

    barcode = (
        db.query(models_buyback.BuybackBarcode)
        .filter(
            models_buyback.BuybackBarcode.entity_type
            == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value
        )
        .one()
    )
    image = api_client.get(
        f"/api/buyback/requests/{request.id}/application-form/barcode.svg",
        headers=_auth_header(user),
    )
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/svg+xml")
    assert barcode.scan_token not in image.text


def test_issue_application_form_logs_print(api_client, db):
    user = _create_user(db, email="issue@example.com")
    request = _seed_and_submit(db, user)

    res1 = api_client.post(
        f"/api/buyback/requests/{request.id}/application-form/issue",
        headers=_auth_header(user),
        json={"print_type": "application_a4"},
    )
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["is_reprint"] is False
    assert body1["application_form_issued_at"] is not None

    res2 = api_client.post(
        f"/api/buyback/requests/{request.id}/application-form/issue",
        headers=_auth_header(user),
        json={"print_type": "application_a4"},
    )
    assert res2.status_code == 200
    assert res2.json()["is_reprint"] is True

    logs = (
        db.query(models_buyback.BuybackPackagePrintLog)
        .filter(models_buyback.BuybackPackagePrintLog.entity_id == request.id)
        .all()
    )
    assert len(logs) == 2
    assert logs[0].includes_pii is False


def test_application_form_other_user_forbidden(api_client, db):
    owner = _create_user(db, email="owner@example.com")
    other = _create_user(db, email="other@example.com")
    request = _seed_and_submit(db, owner)

    res = api_client.get(
        f"/api/buyback/requests/{request.id}/application-form",
        headers=_auth_header(other),
    )
    assert res.status_code == 404


def test_can_print_application_form_false_after_assessment(db):
    user = _create_user(db, email="assessed@example.com")
    request = _seed_and_submit(db, user)
    assert can_print_application_form(request) is True

    request.assessed_at = request.submitted_at
    request.assessed_total = 1000
    assert can_print_application_form(request) is False
