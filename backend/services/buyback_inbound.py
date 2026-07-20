"""Inbound shipment provisioning at buyback submission."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_barcodes import create_barcode, get_active_barcode_for_entity
from services.buyback_public_ids import (
    assign_inbound_mgmt_id,
    assign_public_buyback_code,
    assign_public_member_id,
)


def ensure_inbound_shipment(
    db: Session,
    *,
    request: models_buyback.BuybackRequest,
    declared_item_count: int,
) -> models_buyback.BuybackInboundShipment:
    existing = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
        .first()
    )
    if existing:
        return existing

    inbound_mgmt_id = assign_inbound_mgmt_id(db, request)
    shipment = models_buyback.BuybackInboundShipment(
        request_id=request.id,
        inbound_mgmt_id=inbound_mgmt_id,
        status=models_buyback.BuybackInboundShipmentStatus.awaiting_shipment.value,
        declared_item_count=declared_item_count,
    )
    db.add(shipment)
    db.flush()
    return shipment


def ensure_application_barcode(
    db: Session,
    *,
    inbound_shipment: models_buyback.BuybackInboundShipment,
    human_readable: str,
) -> models_buyback.BuybackBarcode:
    existing = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound_shipment.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
    )
    if existing:
        return existing

    return create_barcode(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound_shipment.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
        human_readable=human_readable,
    )


def provision_request_logistics(
    db: Session,
    *,
    request: models_buyback.BuybackRequest,
    user: models.User,
    declared_item_count: int,
) -> tuple[models_buyback.BuybackInboundShipment, models_buyback.BuybackBarcode]:
    """Assign public IDs, inbound shipment, and application barcode. Idempotent."""
    assign_public_buyback_code(db, request)
    assign_public_member_id(db, user)

    inbound = ensure_inbound_shipment(
        db,
        request=request,
        declared_item_count=declared_item_count,
    )
    barcode = ensure_application_barcode(
        db,
        inbound_shipment=inbound,
        human_readable=request.inbound_mgmt_id or inbound.inbound_mgmt_id,
    )
    return inbound, barcode
