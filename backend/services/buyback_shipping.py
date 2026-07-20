"""Pre-shipment verification and ship confirmation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
import models_buyback
from services.buyback_barcodes import get_active_barcode_for_entity, lookup_barcode_by_token
from services.buyback_emails import STATUS_LABELS, notify_buyback_package_shipped
from services.buyback_packages import PACKAGE_KIND_LABELS, PACKAGE_STATUS_LABELS

logger = logging.getLogger(__name__)

SHIP_CHECK_ITEMS: list[dict[str, str]] = [
    {"code": "name_ok", "label": "宛名が正しい"},
    {"code": "address_ok", "label": "住所が正しい"},
    {"code": "building_ok", "label": "建物名・部屋番号を確認した"},
    {"code": "method_ok", "label": "発送方法が正しい"},
    {"code": "timeslot_ok", "label": "発送希望時間帯が正しい"},
    {"code": "owner_match", "label": "商品と申込者が一致している"},
    {"code": "docs_ok", "label": "必要な書類を同梱した"},
    {"code": "box_count_ok", "label": "箱番号と箱数が正しい"},
    {"code": "tracking_ok", "label": "送り状または追跡番号が正しい"},
]

BLOCKED_REQUEST_STATUSES = {
    models_buyback.BuybackRequestStatus.cancelled.value,
    models_buyback.BuybackRequestStatus.paid.value,
    models_buyback.BuybackRequestStatus.draft.value,
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
                scan_token=(scan_token or "")[:64] or "empty",
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
        logger.warning("Failed to write ship scan log: %s", exc)


def _address_complete(user: models.User | None) -> bool:
    if not user:
        return False
    return bool(
        (user.name or "").strip()
        and (user.postal_code or "").strip()
        and (user.region or "").strip()
        and (user.city or "").strip()
        and (user.address_line1 or "").strip()
    )


def _resolve_outbound_package(
    db: Session, code: str
) -> tuple[Optional[models_buyback.BuybackBarcode], Optional[models_buyback.BuybackShipmentPackage]]:
    token = (code or "").strip()
    if not token:
        return None, None

    barcode = lookup_barcode_by_token(db, token)
    if barcode and barcode.entity_type == models_buyback.BuybackBarcodeEntityType.shipment_package.value:
        package = (
            db.query(models_buyback.BuybackShipmentPackage)
            .filter(models_buyback.BuybackShipmentPackage.id == barcode.entity_id)
            .first()
        )
        return barcode, package

    package = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.package_code == token)
        .first()
    )
    if package:
        barcode = get_active_barcode_for_entity(
            db,
            entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
            entity_id=package.id,
            barcode_type=models_buyback.BuybackBarcodeType.package_outbound.value,
        )
        return barcode, package

    barcode = (
        db.query(models_buyback.BuybackBarcode)
        .filter(
            models_buyback.BuybackBarcode.human_readable == token,
            models_buyback.BuybackBarcode.is_active.is_(True),
            models_buyback.BuybackBarcode.entity_type
            == models_buyback.BuybackBarcodeEntityType.shipment_package.value,
        )
        .first()
    )
    if barcode:
        package = (
            db.query(models_buyback.BuybackShipmentPackage)
            .filter(models_buyback.BuybackShipmentPackage.id == barcode.entity_id)
            .first()
        )
        return barcode, package

    return None, None


def _build_warnings(
    *,
    request: models_buyback.BuybackRequest,
    package: models_buyback.BuybackShipmentPackage,
    dest: models.User | None,
    applicant: models.User | None,
) -> list[str]:
    warnings: list[str] = []
    if request.status == models_buyback.BuybackRequestStatus.cancelled.value:
        warnings.append("キャンセル済み申込です。発送できません。")
    if request.status == models_buyback.BuybackRequestStatus.paid.value:
        warnings.append("買取完了（振込済み）の申込です。誤発送に注意してください。")
    if package.status == models_buyback.BuybackShipmentPackageStatus.shipped.value:
        warnings.append("この梱包は既に発送済みです。二重発送できません。")
    if not _address_complete(dest):
        warnings.append("発送先住所が未入力または不完全です。")
    if dest and applicant and dest.id != applicant.id:
        warnings.append("梱包の発送先ユーザーと申込者が一致しません。")
    elif dest and applicant and (dest.name or "").strip() != (applicant.name or "").strip():
        warnings.append("申込者名義と発送先名義が一致しません。")
    if package.preferred_time_slot:
        warnings.append(f"発送希望時間帯あり: {package.preferred_time_slot}")
    if package.tracking_number:
        # Duplicate tracking check handled at confirm; still surface if empty tracking when packed
        pass
    else:
        warnings.append("追跡番号が未設定です。")

    sibling_count = package.total_boxes or 1
    if sibling_count > 1:
        warnings.append(f"複数箱発送です（{package.box_index}/{sibling_count}）。箱数を確認してください。")

    return warnings


def build_ship_preview(
    db: Session,
    *,
    package: models_buyback.BuybackShipmentPackage,
    barcode: Optional[models_buyback.BuybackBarcode],
    include_pii: bool,
) -> dict:
    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == package.request_id)
        .options(joinedload(models_buyback.BuybackRequest.items))
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申込が見つかりません")

    dest = db.query(models.User).filter(models.User.id == package.destination_user_id).first()
    applicant = db.query(models.User).filter(models.User.id == request.user_id).first()

    existing_conf = (
        db.query(models_buyback.BuybackShipmentConfirmation)
        .filter(models_buyback.BuybackShipmentConfirmation.package_id == package.id)
        .first()
    )

    items = (
        db.query(models_buyback.BuybackPackageItem)
        .filter(models_buyback.BuybackPackageItem.package_id == package.id)
        .all()
    )
    item_rows = []
    for link in items:
        req_item = next((i for i in (request.items or []) if i.id == link.request_item_id), None)
        item_rows.append(
            {
                "request_item_id": link.request_item_id,
                "quantity": link.quantity,
                "product_name": req_item.product_name_snapshot if req_item else None,
                "condition_code": req_item.condition_code if req_item else None,
            }
        )

    already_shipped = (
        package.status == models_buyback.BuybackShipmentPackageStatus.shipped.value
        or existing_conf is not None
    )
    is_cancelled = request.status == models_buyback.BuybackRequestStatus.cancelled.value
    address_ok = _address_complete(dest)
    can_confirm = (
        not already_shipped
        and not is_cancelled
        and address_ok
        and request.status not in BLOCKED_REQUEST_STATUSES
        and package.status
        in {
            models_buyback.BuybackShipmentPackageStatus.packing.value,
            models_buyback.BuybackShipmentPackageStatus.packed.value,
            models_buyback.BuybackShipmentPackageStatus.awaiting_verify.value,
        }
    )

    warnings = _build_warnings(
        request=request, package=package, dest=dest, applicant=applicant
    )

    payload = {
        "found": True,
        "package_id": package.id,
        "barcode_id": barcode.id if barcode else None,
        "scan_token": barcode.scan_token if barcode else None,
        "package_code": package.package_code,
        "package_kind": package.package_kind,
        "package_kind_label": PACKAGE_KIND_LABELS.get(package.package_kind, package.package_kind),
        "box_index": package.box_index,
        "total_boxes": package.total_boxes,
        "request_id": request.id,
        "request_number": request.request_number,
        "public_buyback_code": request.public_buyback_code,
        "return_reference": package.return_reference,
        "request_status": request.status,
        "request_status_label": STATUS_LABELS.get(request.status, request.status),
        "package_status": package.status,
        "package_status_label": PACKAGE_STATUS_LABELS.get(package.status, package.status),
        "shipping_method": package.shipping_method or request.shipping_method,
        "preferred_ship_date": package.preferred_ship_date.isoformat()
        if package.preferred_ship_date
        else None,
        "preferred_time_slot": package.preferred_time_slot,
        "tracking_number": package.tracking_number,
        "applicant_name": applicant.name if applicant else None,
        "destination_name": dest.name if dest else None,
        "items": item_rows,
        "checklist_items": SHIP_CHECK_ITEMS,
        "warnings": warnings,
        "already_shipped": already_shipped,
        "is_cancelled": is_cancelled,
        "address_complete": address_ok,
        "can_confirm": can_confirm,
        "notices": [
            "宛名・住所・時間帯を大きな表示で再確認してください",
            "チェックリストをすべて完了してから発送確定してください",
            "発送済みバーコードは再発送できません",
        ],
    }

    if include_pii and dest:
        payload["destination_phone"] = dest.phone_number
        payload["destination_address"] = {
            "postal_code": dest.postal_code,
            "region": dest.region,
            "city": dest.city,
            "address_line1": dest.address_line1,
            "address_line2": dest.address_line2,
        }
    else:
        payload["destination_phone"] = None
        payload["destination_address"] = None
        if not include_pii:
            # Still show name for shipping work when ship.read granted; address masked
            pass

    return payload


def scan_for_ship_verify(
    db: Session,
    *,
    admin_user: models.User,
    code: str,
    include_pii: bool,
    ip_address: Optional[str] = None,
    device_info: Optional[str] = None,
) -> dict:
    barcode, package = _resolve_outbound_package(db, code)
    token = (code or "").strip()

    if not package:
        _log_scan(
            db,
            actor_user_id=admin_user.id,
            scan_token=token or "empty",
            barcode_id=None,
            action="ship_verify_scan",
            result="not_found",
            ip_address=ip_address,
            device_info=device_info,
        )
        db.commit()
        return {
            "found": False,
            "message": "梱包バーコードに該当する荷物が見つかりません",
            "already_shipped": False,
            "can_confirm": False,
            "checklist_items": SHIP_CHECK_ITEMS,
            "warnings": [],
            "notices": [],
            "items": [],
        }

    # Move packed -> awaiting_verify on successful scan
    if package.status == models_buyback.BuybackShipmentPackageStatus.packed.value:
        package.status = models_buyback.BuybackShipmentPackageStatus.awaiting_verify.value
        package.updated_at = datetime.utcnow()

    payload = build_ship_preview(
        db, package=package, barcode=barcode, include_pii=include_pii
    )

    result = "success"
    if payload.get("already_shipped"):
        result = "already_shipped"
    elif payload.get("is_cancelled"):
        result = "cancelled"
    elif not payload.get("address_complete"):
        result = "incomplete_address"

    _log_scan(
        db,
        actor_user_id=admin_user.id,
        scan_token=barcode.scan_token if barcode else token,
        barcode_id=barcode.id if barcode else None,
        action="ship_verify_scan",
        result=result,
        request_id=package.request_id,
        package_id=package.id,
        ip_address=ip_address,
        device_info=device_info,
        details={"include_pii": include_pii},
    )
    if include_pii:
        try:
            db.add(
                models_buyback.BuybackAuditLog(
                    actor_user_id=admin_user.id,
                    action="pii_viewed_on_ship_verify",
                    entity_type="buyback_shipment_package",
                    entity_id=str(package.id),
                    details_json=json.dumps({"via": "ship_verify"}, ensure_ascii=False),
                )
            )
        except Exception as exc:
            logger.warning("Failed PII audit on ship verify: %s", exc)

    db.commit()
    return payload


def confirm_shipment(
    db: Session,
    *,
    admin_user: models.User,
    package_id: int,
    checklist: dict[str, bool],
    scanned_code: Optional[str] = None,
    tracking_number: Optional[str] = None,
    shipping_method: Optional[str] = None,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    package = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.id == package_id)
        .first()
    )
    if not package:
        raise HTTPException(status_code=404, detail="梱包が見つかりません")

    existing = (
        db.query(models_buyback.BuybackShipmentConfirmation)
        .filter(models_buyback.BuybackShipmentConfirmation.package_id == package.id)
        .first()
    )
    if existing or package.status == models_buyback.BuybackShipmentPackageStatus.shipped.value:
        raise HTTPException(status_code=400, detail="発送済みです。二重発送はできません")

    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == package.request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申込が見つかりません")
    if request.status == models_buyback.BuybackRequestStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="キャンセル済み申込は発送できません")
    if request.status in {
        models_buyback.BuybackRequestStatus.paid.value,
        models_buyback.BuybackRequestStatus.draft.value,
    }:
        raise HTTPException(
            status_code=400,
            detail=f"現在のステータス（{STATUS_LABELS.get(request.status, request.status)}）では発送確定できません",
        )

    dest = db.query(models.User).filter(models.User.id == package.destination_user_id).first()
    if not _address_complete(dest):
        raise HTTPException(status_code=400, detail="発送先住所が不完全なため発送確定できません")

    # All checklist items required
    missing = [
        item["label"]
        for item in SHIP_CHECK_ITEMS
        if not checklist.get(item["code"])
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"未完了の確認項目があります: {', '.join(missing)}",
        )

    barcode = None
    if scanned_code:
        barcode, resolved = _resolve_outbound_package(db, scanned_code)
        if resolved and resolved.id != package.id:
            raise HTTPException(status_code=400, detail="読み取ったバーコードが梱包と一致しません")
    if not barcode:
        barcode = get_active_barcode_for_entity(
            db,
            entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
            entity_id=package.id,
            barcode_type=models_buyback.BuybackBarcodeType.package_outbound.value,
        )

    tn = (tracking_number or package.tracking_number or "").strip() or None
    if tn:
        dup = (
            db.query(models_buyback.BuybackShipmentPackage.id)
            .filter(
                models_buyback.BuybackShipmentPackage.tracking_number == tn,
                models_buyback.BuybackShipmentPackage.id != package.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="この追跡番号は別の梱包で使用されています")
        package.tracking_number = tn

    method = (shipping_method or package.shipping_method or "").strip() or None
    if method:
        package.shipping_method = method

    now = datetime.utcnow()
    package.status = models_buyback.BuybackShipmentPackageStatus.shipped.value
    package.shipped_at = now
    package.updated_at = now

    confirmation = models_buyback.BuybackShipmentConfirmation(
        package_id=package.id,
        confirmed_at=now,
        confirmed_by_user_id=admin_user.id,
        scanned_barcode_id=barcode.id if barcode else None,
        tracking_number=package.tracking_number,
        shipping_method=package.shipping_method,
        checklist_json=json.dumps(checklist, ensure_ascii=False),
        device_info=(device_info or "")[:255] or None,
    )
    db.add(confirmation)
    db.flush()

    snapshot = models_buyback.BuybackShipmentAddressSnapshot(
        confirmation_id=confirmation.id,
        recipient_name=(dest.name if dest else "").strip() or "—",
        postal_code=dest.postal_code if dest else None,
        region=dest.region if dest else None,
        city=dest.city if dest else None,
        address_line1=dest.address_line1 if dest else None,
        address_line2=dest.address_line2 if dest else None,
        phone_number=dest.phone_number if dest else None,
        shipping_method=package.shipping_method,
        preferred_time_slot=package.preferred_time_slot,
        snapshot_json=json.dumps(
            {
                "recipient_name": dest.name if dest else None,
                "postal_code": dest.postal_code if dest else None,
                "region": dest.region if dest else None,
                "city": dest.city if dest else None,
                "address_line1": dest.address_line1 if dest else None,
                "address_line2": dest.address_line2 if dest else None,
                "phone_number": dest.phone_number if dest else None,
                "shipping_method": package.shipping_method,
                "preferred_ship_date": package.preferred_ship_date.isoformat()
                if package.preferred_ship_date
                else None,
                "preferred_time_slot": package.preferred_time_slot,
                "tracking_number": package.tracking_number,
                "package_code": package.package_code,
            },
            ensure_ascii=False,
        ),
    )
    db.add(snapshot)

    # Update request item return status if return package
    if package.package_kind == "return":
        links = (
            db.query(models_buyback.BuybackPackageItem)
            .filter(models_buyback.BuybackPackageItem.package_id == package.id)
            .all()
        )
        for link in links:
            item = (
                db.query(models_buyback.BuybackRequestItem)
                .filter(models_buyback.BuybackRequestItem.id == link.request_item_id)
                .first()
            )
            if item:
                item.return_status = models_buyback.BuybackItemReturnStatus.shipped.value
                if package.tracking_number:
                    item.return_tracking_number = package.tracking_number

        # If all packages for this request+kind shipped, optionally set request returned
        siblings = (
            db.query(models_buyback.BuybackShipmentPackage)
            .filter(
                models_buyback.BuybackShipmentPackage.request_id == request.id,
                models_buyback.BuybackShipmentPackage.package_kind == package.package_kind,
            )
            .all()
        )
        if siblings and all(
            s.status == models_buyback.BuybackShipmentPackageStatus.shipped.value for s in siblings
        ):
            if request.status in {
                models_buyback.BuybackRequestStatus.rejected.value,
                models_buyback.BuybackRequestStatus.awaiting_customer.value,
                models_buyback.BuybackRequestStatus.assessed.value,
            }:
                prev = request.status
                request.status = models_buyback.BuybackRequestStatus.returned.value
                request.updated_at = now
                db.add(
                    models_buyback.BuybackStatusHistory(
                        request_id=request.id,
                        from_status=prev,
                        to_status=request.status,
                        changed_by_user_id=admin_user.id,
                        note="発送確定（返送）",
                        related_barcode_id=barcode.id if barcode else None,
                        device_info=(device_info or "")[:255] or None,
                        change_reason="ship_confirm",
                    )
                )

    _log_scan(
        db,
        actor_user_id=admin_user.id,
        scan_token=barcode.scan_token if barcode else (scanned_code or package.package_code),
        barcode_id=barcode.id if barcode else None,
        action="ship_confirm",
        result="success",
        request_id=request.id,
        package_id=package.id,
        ip_address=ip_address,
        device_info=device_info,
        details={"checklist": checklist, "tracking_number": package.tracking_number},
    )
    try:
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=admin_user.id,
                action="shipment_confirmed",
                entity_type="buyback_shipment_package",
                entity_id=str(package.id),
                details_json=json.dumps(
                    {
                        "package_code": package.package_code,
                        "tracking_number": package.tracking_number,
                        "confirmation_id": confirmation.id,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    except Exception as exc:
        logger.warning("Failed ship confirm audit: %s", exc)

    db.commit()

    try:
        if dest:
            notify_buyback_package_shipped(db, request, dest, package)
    except Exception as exc:
        logger.warning("Failed package shipped notification: %s", exc)

    return build_ship_preview(
        db,
        package=package,
        barcode=barcode,
        include_pii=True,
    )
