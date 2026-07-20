"""Admin inbound scan and receive operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

import models
import models_buyback
from services.buyback_barcodes import lookup_barcode_by_token
from services.buyback_compliance import get_compliance_status
from services.buyback_emails import STATUS_LABELS, notify_buyback_inbound_received

logger = logging.getLogger(__name__)

INBOUND_STATUS_LABELS = {
    "awaiting_shipment": "発送待ち",
    "customer_shipped": "客から発送済み",
    "arrived": "荷物到着",
    "received": "受付済み",
}


def _log_scan(
    db: Session,
    *,
    actor_user_id: Optional[int],
    scan_token: str,
    barcode_id: Optional[int],
    action: str,
    result: str,
    request_id: Optional[int] = None,
    package_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    device_info: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    try:
        db.add(
            models_buyback.BuybackPackageScanLog(
                actor_user_id=actor_user_id,
                scan_token=scan_token[:64],
                barcode_id=barcode_id,
                action=action,
                result=result,
                request_id=request_id,
                package_id=package_id,
                ip_address=(ip_address or "")[:64] or None,
                device_info=(device_info or "")[:255] or None,
                details_json=json.dumps(details, ensure_ascii=False) if details else None,
            )
        )
    except Exception as exc:
        logger.warning("Failed to write scan log: %s", exc)


def _resolve_inbound_by_code(
    db: Session, code: str
) -> tuple[Optional[models_buyback.BuybackBarcode], Optional[models_buyback.BuybackInboundShipment]]:
    """Resolve scan token, human-readable barcode label, or public IDs."""
    token = (code or "").strip()
    if not token:
        return None, None

    barcode = lookup_barcode_by_token(db, token)
    if barcode and barcode.entity_type == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value:
        inbound = (
            db.query(models_buyback.BuybackInboundShipment)
            .filter(models_buyback.BuybackInboundShipment.id == barcode.entity_id)
            .first()
        )
        return barcode, inbound

    # Human-readable under barcode / public codes (admin convenience)
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.inbound_mgmt_id == token)
        .first()
    )
    if inbound:
        barcode = (
            db.query(models_buyback.BuybackBarcode)
            .filter(
                models_buyback.BuybackBarcode.entity_type
                == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
                models_buyback.BuybackBarcode.entity_id == inbound.id,
                models_buyback.BuybackBarcode.is_active.is_(True),
            )
            .order_by(models_buyback.BuybackBarcode.created_at.desc())
            .first()
        )
        return barcode, inbound

    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(
            (models_buyback.BuybackRequest.public_buyback_code == token)
            | (models_buyback.BuybackRequest.inbound_mgmt_id == token)
            | (models_buyback.BuybackRequest.request_number == token)
        )
        .first()
    )
    if request:
        inbound = (
            db.query(models_buyback.BuybackInboundShipment)
            .filter(models_buyback.BuybackInboundShipment.request_id == request.id)
            .first()
        )
        barcode = None
        if inbound:
            barcode = (
                db.query(models_buyback.BuybackBarcode)
                .filter(
                    models_buyback.BuybackBarcode.entity_type
                    == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
                    models_buyback.BuybackBarcode.entity_id == inbound.id,
                    models_buyback.BuybackBarcode.is_active.is_(True),
                )
                .order_by(models_buyback.BuybackBarcode.created_at.desc())
                .first()
            )
        return barcode, inbound

    # Match barcode human_readable
    barcode = (
        db.query(models_buyback.BuybackBarcode)
        .filter(
            models_buyback.BuybackBarcode.human_readable == token,
            models_buyback.BuybackBarcode.is_active.is_(True),
            models_buyback.BuybackBarcode.entity_type
            == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        )
        .first()
    )
    if barcode:
        inbound = (
            db.query(models_buyback.BuybackInboundShipment)
            .filter(models_buyback.BuybackInboundShipment.id == barcode.entity_id)
            .first()
        )
        return barcode, inbound

    return None, None


def build_inbound_scan_payload(
    db: Session,
    *,
    inbound: models_buyback.BuybackInboundShipment,
    barcode: Optional[models_buyback.BuybackBarcode],
    include_pii: bool,
) -> dict:
    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == inbound.request_id)
        .options(
            joinedload(models_buyback.BuybackRequest.items),
            joinedload(models_buyback.BuybackRequest.status_history),
        )
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申込が見つかりません")

    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    compliance = get_compliance_status(db, user_id=request.user_id, requires_guardian=False)

    receipts = (
        db.query(models_buyback.BuybackPackageReceipt)
        .filter(models_buyback.BuybackPackageReceipt.inbound_shipment_id == inbound.id)
        .order_by(models_buyback.BuybackPackageReceipt.received_at.desc())
        .limit(10)
        .all()
    )
    receipt_user_ids = {r.received_by_user_id for r in receipts}
    receipt_users = {}
    if receipt_user_ids:
        for row in db.query(models.User).filter(models.User.id.in_(receipt_user_ids)).all():
            receipt_users[row.id] = row

    history = sorted(
        request.status_history or [],
        key=lambda h: h.created_at or datetime.min,
        reverse=True,
    )[:20]

    items = [
        {
            "id": item.id,
            "product_name": item.product_name_snapshot,
            "condition_code": item.condition_code,
            "quantity": item.quantity,
        }
        for item in (request.items or [])
    ]

    payload = {
        "found": True,
        "request_id": request.id,
        "inbound_shipment_id": inbound.id,
        "barcode_id": barcode.id if barcode else None,
        "scan_token": barcode.scan_token if barcode else None,
        "request_number": request.request_number,
        "public_buyback_code": request.public_buyback_code,
        "inbound_mgmt_id": inbound.inbound_mgmt_id,
        "applicant_name": user.name if user else "—",
        "public_member_id": user.public_member_id if user else None,
        "submitted_at": request.submitted_at or request.created_at,
        "request_status": request.status,
        "request_status_label": STATUS_LABELS.get(request.status, request.status),
        "inbound_status": inbound.status,
        "inbound_status_label": INBOUND_STATUS_LABELS.get(inbound.status, inbound.status),
        "shipping_method": request.shipping_method,
        "declared_item_count": inbound.declared_item_count
        or sum(i.quantity for i in (request.items or [])),
        "actual_item_count": inbound.actual_item_count,
        "expected_box_count": inbound.expected_box_count,
        "items": items,
        "identity_status": compliance.get("identity_status"),
        "identity_status_label": compliance.get("identity_status_label"),
        "guardian_status": compliance.get("guardian_status"),
        "guardian_status_label": compliance.get("guardian_status_label"),
        "admin_note": request.admin_note,
        "logistics_note": request.logistics_note,
        "already_received": inbound.status
        == models_buyback.BuybackInboundShipmentStatus.received.value
        or request.status
        in {
            models_buyback.BuybackRequestStatus.received.value,
            models_buyback.BuybackRequestStatus.assessing.value,
            models_buyback.BuybackRequestStatus.assessed.value,
            models_buyback.BuybackRequestStatus.awaiting_customer.value,
            models_buyback.BuybackRequestStatus.accepted.value,
            models_buyback.BuybackRequestStatus.payout_pending.value,
            models_buyback.BuybackRequestStatus.paid.value,
        },
        "is_cancelled": request.status
        == models_buyback.BuybackRequestStatus.cancelled.value,
        "can_receive": request.status
        == models_buyback.BuybackRequestStatus.submitted.value
        and inbound.status
        != models_buyback.BuybackInboundShipmentStatus.received.value,
        "status_history": [
            {
                "id": h.id,
                "from_status": h.from_status,
                "from_status_label": STATUS_LABELS.get(h.from_status, h.from_status)
                if h.from_status
                else None,
                "to_status": h.to_status,
                "to_status_label": STATUS_LABELS.get(h.to_status, h.to_status),
                "note": h.note,
                "created_at": h.created_at,
            }
            for h in history
        ],
        "receipts": [
            {
                "id": r.id,
                "received_at": r.received_at,
                "received_by_name": receipt_users.get(r.received_by_user_id).name
                if receipt_users.get(r.received_by_user_id)
                else None,
                "box_count": r.box_count,
                "actual_item_count": r.actual_item_count,
                "condition_note": r.condition_note,
                "admin_note": r.admin_note,
                "device_info": r.device_info,
            }
            for r in receipts
        ],
        "notices": [
            "荷物は元払いであること",
            "申込書と商品点数を照合すること",
            "状態が著しく悪い商品は買取不可の場合があること",
        ],
    }

    if include_pii and user:
        payload["user_email"] = user.email
        payload["phone_number"] = user.phone_number
        payload["address"] = {
            "postal_code": user.postal_code,
            "region": user.region,
            "city": user.city,
            "address_line1": user.address_line1,
            "address_line2": user.address_line2,
        }
    else:
        payload["user_email"] = None
        payload["phone_number"] = None
        payload["address"] = None

    return payload


def scan_inbound_barcode(
    db: Session,
    *,
    admin_user: models.User,
    code: str,
    include_pii: bool,
    ip_address: Optional[str] = None,
    device_info: Optional[str] = None,
) -> dict:
    barcode, inbound = _resolve_inbound_by_code(db, code)
    token = (code or "").strip()

    if not inbound:
        _log_scan(
            db,
            actor_user_id=admin_user.id,
            scan_token=token or "empty",
            barcode_id=None,
            action="scan_lookup",
            result="not_found",
            ip_address=ip_address,
            device_info=device_info,
        )
        db.commit()
        return {
            "found": False,
            "message": "バーコードに該当する買取申込が見つかりません",
        }

    payload = build_inbound_scan_payload(
        db, inbound=inbound, barcode=barcode, include_pii=include_pii
    )
    result = "success"
    if payload.get("is_cancelled"):
        result = "cancelled"
    elif payload.get("already_received"):
        result = "already_received"

    _log_scan(
        db,
        actor_user_id=admin_user.id,
        scan_token=barcode.scan_token if barcode else token,
        barcode_id=barcode.id if barcode else None,
        action="scan_lookup",
        result=result,
        request_id=inbound.request_id,
        ip_address=ip_address,
        device_info=device_info,
        details={"include_pii": include_pii},
    )
    if include_pii:
        try:
            db.add(
                models_buyback.BuybackAuditLog(
                    actor_user_id=admin_user.id,
                    action="pii_viewed_on_scan",
                    entity_type="buyback_request",
                    entity_id=str(inbound.request_id),
                    details_json=json.dumps({"via": "inbound_scan"}, ensure_ascii=False),
                )
            )
        except Exception as exc:
            logger.warning("Failed to write PII view audit: %s", exc)

    db.commit()
    return payload


def receive_inbound_package(
    db: Session,
    *,
    admin_user: models.User,
    inbound_shipment_id: int,
    scanned_code: Optional[str] = None,
    box_count: Optional[int] = None,
    actual_item_count: Optional[int] = None,
    condition_note: Optional[str] = None,
    admin_note: Optional[str] = None,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    inbound = (
        db.query(models_buyback.BuybackInboundShipment)
        .filter(models_buyback.BuybackInboundShipment.id == inbound_shipment_id)
        .first()
    )
    if not inbound:
        raise HTTPException(status_code=404, detail="荷物データが見つかりません")

    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == inbound.request_id)
        .options(joinedload(models_buyback.BuybackRequest.items))
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申込が見つかりません")

    if request.status == models_buyback.BuybackRequestStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="キャンセル済みの申込は受付できません")

    if request.status not in {
        models_buyback.BuybackRequestStatus.submitted.value,
        models_buyback.BuybackRequestStatus.received.value,
    }:
        raise HTTPException(
            status_code=400,
            detail=f"現在のステータス（{STATUS_LABELS.get(request.status, request.status)}）では受付できません",
        )

    barcode = None
    if scanned_code:
        barcode, resolved = _resolve_inbound_by_code(db, scanned_code)
        if resolved and resolved.id != inbound.id:
            raise HTTPException(status_code=400, detail="読み取ったバーコードが荷物と一致しません")

    if not barcode:
        barcode = (
            db.query(models_buyback.BuybackBarcode)
            .filter(
                models_buyback.BuybackBarcode.entity_type
                == models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
                models_buyback.BuybackBarcode.entity_id == inbound.id,
                models_buyback.BuybackBarcode.is_active.is_(True),
            )
            .order_by(models_buyback.BuybackBarcode.created_at.desc())
            .first()
        )

    now = datetime.utcnow()
    was_already = inbound.status == models_buyback.BuybackInboundShipmentStatus.received.value

    inbound.status = models_buyback.BuybackInboundShipmentStatus.received.value
    if box_count is not None:
        inbound.expected_box_count = max(1, int(box_count))
    if actual_item_count is not None:
        inbound.actual_item_count = int(actual_item_count)
    if condition_note is not None:
        inbound.condition_note = condition_note.strip() or None
    inbound.updated_at = now

    prev_status = request.status
    if request.status == models_buyback.BuybackRequestStatus.submitted.value:
        request.status = models_buyback.BuybackRequestStatus.received.value
        request.received_at = now
        request.received_by_user_id = admin_user.id
        request.updated_at = now
        if admin_note is not None:
            request.logistics_note = admin_note.strip() or request.logistics_note
        db.add(
            models_buyback.BuybackStatusHistory(
                request_id=request.id,
                from_status=prev_status,
                to_status=models_buyback.BuybackRequestStatus.received.value,
                changed_by_user_id=admin_user.id,
                note=admin_note or "荷物受付",
                related_barcode_id=barcode.id if barcode else None,
                device_info=(device_info or "")[:255] or None,
                change_reason="inbound_receive",
            )
        )
    elif admin_note is not None:
        request.logistics_note = admin_note.strip() or request.logistics_note
        request.updated_at = now

    receipt = models_buyback.BuybackPackageReceipt(
        inbound_shipment_id=inbound.id,
        received_at=now,
        received_by_user_id=admin_user.id,
        scanned_barcode_id=barcode.id if barcode else None,
        device_info=(device_info or "")[:255] or None,
        box_count=box_count,
        actual_item_count=actual_item_count,
        condition_note=(condition_note or "").strip() or None,
        admin_note=(admin_note or "").strip() or None,
    )
    db.add(receipt)

    _log_scan(
        db,
        actor_user_id=admin_user.id,
        scan_token=barcode.scan_token if barcode else (scanned_code or inbound.inbound_mgmt_id),
        barcode_id=barcode.id if barcode else None,
        action="receive",
        result="already_received" if was_already else "success",
        request_id=request.id,
        ip_address=ip_address,
        device_info=device_info,
        details={
            "box_count": box_count,
            "actual_item_count": actual_item_count,
            "was_already_received": was_already,
        },
    )
    try:
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=admin_user.id,
                action="inbound_received",
                entity_type="buyback_request",
                entity_id=str(request.id),
                details_json=json.dumps(
                    {
                        "inbound_shipment_id": inbound.id,
                        "was_already_received": was_already,
                        "box_count": box_count,
                        "actual_item_count": actual_item_count,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    except Exception as exc:
        logger.warning("Failed to write receive audit: %s", exc)

    db.commit()

    if not was_already:
        try:
            dest_user = (
                db.query(models.User).filter(models.User.id == request.user_id).first()
            )
            if dest_user:
                notify_buyback_inbound_received(db, request, dest_user)
        except Exception as exc:
            logger.warning("Failed inbound received notification: %s", exc)

    return build_inbound_scan_payload(
        db,
        inbound=inbound,
        barcode=barcode,
        include_pii=True,
    )
