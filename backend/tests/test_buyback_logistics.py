"""Buyback logistics ID and barcode provisioning tests (Phase 1)."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_barcodes import get_active_barcode_for_entity, lookup_barcode_by_token
from services.buyback_cart import add_cart_item
from services.buyback_inbound import provision_request_logistics
from services.buyback_public_ids import assign_public_buyback_code, assign_public_member_id
from services.buyback_requests import submit_request_from_cart


def _create_user(db, email: str = "logistics@example.com") -> models.User:
    user = models.User(
        email=email,
        name="Logistics Buyer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_cart(db, user: models.User) -> None:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_logistics_001",
        product_name="物流テストカード",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=3,
    )


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_submit_provisions_public_ids_and_barcode(mock_notify, db):
    user = _create_user(db)
    _seed_cart(db, user)

    request = submit_request_from_cart(
        db,
        user=user,
        rejected_item_handling="return_rejected_only",
        agreed_prepaid_shipping=True,
        agreed_cod_consequence=True,
        agreed_condition_rejection=True,
    )
    db.refresh(user)

    assert request.request_number.startswith("KBB-")
    assert request.public_buyback_code.startswith("KRX-BUY-")
    assert request.inbound_mgmt_id.startswith("KRX-PKG-")
    assert user.public_member_id.startswith("KRX-MBR-")

    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .first()
    )
    assert inbound is not None
    assert inbound.inbound_mgmt_id == request.inbound_mgmt_id
    assert inbound.declared_item_count == 3
    assert inbound.status == models_buyback.BuybackInboundShipmentStatus.awaiting_shipment.value

    barcode = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
    )
    assert barcode is not None
    assert barcode.human_readable == request.inbound_mgmt_id
    assert lookup_barcode_by_token(db, barcode.scan_token) is not None
    mock_notify.assert_called_once()


def test_provision_request_logistics_is_idempotent(db):
    user = _create_user(db, email="idem@example.com")
    request = models_buyback.BuybackRequest(
        user_id=user.id,
        status=models_buyback.BuybackRequestStatus.submitted.value,
    )
    db.add(request)
    db.flush()

    inbound1, barcode1 = provision_request_logistics(
        db, request=request, user=user, declared_item_count=5
    )
    inbound2, barcode2 = provision_request_logistics(
        db, request=request, user=user, declared_item_count=5
    )
    db.commit()

    assert inbound1.id == inbound2.id
    assert barcode1.id == barcode2.id
    assert request.public_buyback_code.startswith("KRX-BUY-")
    assert request.inbound_mgmt_id.startswith("KRX-PKG-")


def test_public_codes_are_sequential_per_day(db):
    user = _create_user(db, email="seq@example.com")
    req1 = models_buyback.BuybackRequest(
        user_id=user.id,
        status=models_buyback.BuybackRequestStatus.submitted.value,
    )
    req2 = models_buyback.BuybackRequest(
        user_id=user.id,
        status=models_buyback.BuybackRequestStatus.submitted.value,
    )
    db.add(req1)
    db.add(req2)
    db.flush()

    code1 = assign_public_buyback_code(db, req1)
    code2 = assign_public_buyback_code(db, req2)
    db.commit()

    assert code1.startswith("KRX-BUY-")
    assert code2.startswith("KRX-BUY-")
    assert code1 != code2


def test_assign_public_member_id_is_stable(db):
    user = _create_user(db, email="member@example.com")
    first = assign_public_member_id(db, user)
    second = assign_public_member_id(db, user)
    assert first == second
    assert first.startswith("KRX-MBR-")
