"""Outbound package barcode issuance and packing labels."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

import models
import models_buyback
from services.buyback_barcodes import create_barcode, get_active_barcode_for_entity
from services.buyback_emails import STATUS_LABELS
from services.buyback_inbound import provision_request_logistics
from services.buyback_public_ids import assign_inbound_mgmt_id, build_package_box_code
from services.sensitive_redaction import redact_text

logger = logging.getLogger(__name__)

PACKAGE_STATUS_LABELS = {
    "packing": "梱包中",
    "packed": "梱包完了",
    "awaiting_verify": "発送前確認待ち",
    "shipped": "発送済み",
    "delivered": "配達完了",
    "cancelled": "キャンセル",
}

PACKAGE_KIND_LABELS = {
    "return": "返送",
    "outbound": "発送",
}

# Statuses where packing barcodes may be issued
PACKABLE_REQUEST_STATUSES = {
    models_buyback.BuybackRequestStatus.assessed.value,
    models_buyback.BuybackRequestStatus.awaiting_customer.value,
    models_buyback.BuybackRequestStatus.accepted.value,
    models_buyback.BuybackRequestStatus.rejected.value,
}


def _serialize_package(
    db: Session,
    package: models_buyback.BuybackShipmentPackage,
) -> dict:
    barcode = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
        entity_id=package.id,
        barcode_type=models_buyback.BuybackBarcodeType.package_outbound.value,
    )
    packed_by = None
    if package.packed_by_user_id:
        u = db.query(models.User).filter(models.User.id == package.packed_by_user_id).first()
        packed_by = u.name if u else None

    items = (
        db.query(models_buyback.BuybackPackageItem)
        .filter(models_buyback.BuybackPackageItem.package_id == package.id)
        .all()
    )
    item_rows = []
    for link in items:
        req_item = (
            db.query(models_buyback.BuybackRequestItem)
            .filter(models_buyback.BuybackRequestItem.id == link.request_item_id)
            .first()
        )
        item_rows.append(
            {
                "request_item_id": link.request_item_id,
                "quantity": link.quantity,
                "product_name": req_item.product_name_snapshot if req_item else None,
                "condition_code": req_item.condition_code if req_item else None,
            }
        )

    return {
        "id": package.id,
        "request_id": package.request_id,
        "package_code": package.package_code,
        "package_kind": package.package_kind,
        "package_kind_label": PACKAGE_KIND_LABELS.get(package.package_kind, package.package_kind),
        "box_index": package.box_index,
        "total_boxes": package.total_boxes,
        "return_reference": package.return_reference,
        "shipping_method": package.shipping_method,
        "preferred_ship_date": package.preferred_ship_date.isoformat()
        if package.preferred_ship_date
        else None,
        "preferred_time_slot": package.preferred_time_slot,
        "tracking_number": package.tracking_number,
        "status": package.status,
        "status_label": PACKAGE_STATUS_LABELS.get(package.status, package.status),
        "packed_by_name": packed_by,
        "packed_at": package.packed_at,
        "shipped_at": package.shipped_at,
        "admin_note": package.admin_note,
        "barcode_human_readable": barcode.human_readable if barcode else package.package_code,
        "items": item_rows,
        "created_at": package.created_at,
    }


def list_packages_for_request(db: Session, request_id: int) -> list[dict]:
    rows = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.request_id == request_id)
        .order_by(
            models_buyback.BuybackShipmentPackage.package_kind.asc(),
            models_buyback.BuybackShipmentPackage.box_index.asc(),
        )
        .all()
    )
    return [_serialize_package(db, row) for row in rows]


def issue_packages_for_request(
    db: Session,
    *,
    admin_user: models.User,
    request_id: int,
    total_boxes: int = 1,
    package_kind: str = "return",
    shipping_method: Optional[str] = None,
    preferred_ship_date: Optional[date] = None,
    preferred_time_slot: Optional[str] = None,
    return_reference: Optional[str] = None,
    admin_note: Optional[str] = None,
    request_item_ids: Optional[list[int]] = None,
    replace_existing: bool = False,
) -> list[dict]:
    if total_boxes < 1 or total_boxes > 50:
        raise HTTPException(status_code=400, detail="箱数は1〜50で指定してください")
    if package_kind not in PACKAGE_KIND_LABELS:
        raise HTTPException(status_code=400, detail="無効な梱包種別です")

    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == request_id)
        .options(joinedload(models_buyback.BuybackRequest.items))
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申請が見つかりません")

    if request.status == models_buyback.BuybackRequestStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="キャンセル済み申込には梱包バーコードを発行できません")
    if request.status not in PACKABLE_REQUEST_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"現在のステータス（{STATUS_LABELS.get(request.status, request.status)}）では梱包バーコードを発行できません",
        )

    customer = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="申込者ユーザーが見つかりません")

    # Ensure inbound IDs exist for base package code
    declared = sum(i.quantity for i in (request.items or []))
    provision_request_logistics(
        db, request=request, user=customer, declared_item_count=declared
    )
    base_id = assign_inbound_mgmt_id(db, request)

    existing = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(
            models_buyback.BuybackShipmentPackage.request_id == request.id,
            models_buyback.BuybackShipmentPackage.package_kind == package_kind,
        )
        .all()
    )
    if existing and not replace_existing:
        # Return existing if same total_boxes; otherwise require replace
        if len(existing) == total_boxes and all(
            p.status
            != models_buyback.BuybackShipmentPackageStatus.shipped.value
            for p in existing
        ):
            return [_serialize_package(db, p) for p in existing]
        raise HTTPException(
            status_code=400,
            detail="既に梱包バーコードが発行されています。再発行する場合は replace_existing=true を指定してください",
        )

    if existing and replace_existing:
        for p in existing:
            if p.status == models_buyback.BuybackShipmentPackageStatus.shipped.value:
                raise HTTPException(
                    status_code=400,
                    detail="発送済みの梱包があるため再発行できません",
                )
            # Revoke barcodes
            barcodes = (
                db.query(models_buyback.BuybackBarcode)
                .filter(
                    models_buyback.BuybackBarcode.entity_type
                    == models_buyback.BuybackBarcodeEntityType.shipment_package.value,
                    models_buyback.BuybackBarcode.entity_id == p.id,
                    models_buyback.BuybackBarcode.is_active.is_(True),
                )
                .all()
            )
            for b in barcodes:
                b.is_active = False
                b.revoked_at = datetime.utcnow()
            db.query(models_buyback.BuybackPackageItem).filter(
                models_buyback.BuybackPackageItem.package_id == p.id
            ).delete(synchronize_session=False)
            db.delete(p)
        db.flush()

    # Validate item IDs belong to this request
    attach_ids: list[int] = []
    if request_item_ids:
        valid_ids = {item.id for item in (request.items or [])}
        for iid in request_item_ids:
            if iid not in valid_ids:
                raise HTTPException(status_code=400, detail=f"明細ID {iid} はこの申込にありません")
            attach_ids.append(iid)
    else:
        # Default: attach return-target / rejected items for return packages
        if package_kind == "return":
            for item in request.items or []:
                if item.is_return_target or item.line_status == models_buyback.BuybackItemLineStatus.rejected.value:
                    attach_ids.append(item.id)

    created: list[models_buyback.BuybackShipmentPackage] = []
    now = datetime.utcnow()
    for box_index in range(1, total_boxes + 1):
        package_code = build_package_box_code(base_mgmt_id=base_id, box_index=box_index)
        # Avoid collision with inbound-only codes if somehow same
        collision = (
            db.query(models_buyback.BuybackShipmentPackage.id)
            .filter(models_buyback.BuybackShipmentPackage.package_code == package_code)
            .first()
        )
        if collision:
            raise HTTPException(
                status_code=400,
                detail=f"梱包ID {package_code} は既に使用されています",
            )

        package = models_buyback.BuybackShipmentPackage(
            request_id=request.id,
            package_code=package_code,
            package_kind=package_kind,
            box_index=box_index,
            total_boxes=total_boxes,
            return_reference=(return_reference or "").strip() or None,
            destination_user_id=request.user_id,
            shipping_method=(shipping_method or request.shipping_method or "").strip() or None,
            preferred_ship_date=preferred_ship_date,
            preferred_time_slot=(preferred_time_slot or "").strip() or None,
            status=models_buyback.BuybackShipmentPackageStatus.packing.value,
            admin_note=(admin_note or "").strip() or None,
        )
        db.add(package)
        db.flush()

        create_barcode(
            db,
            entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
            entity_id=package.id,
            barcode_type=models_buyback.BuybackBarcodeType.package_outbound.value,
            human_readable=package_code,
        )

        # Attach all return items to every box for visibility, or only box 1?
        # Spec: package_items link for mix warnings. Put all on box 1, others empty unless specified.
        if box_index == 1:
            for iid in attach_ids:
                req_item = next((i for i in (request.items or []) if i.id == iid), None)
                qty = req_item.quantity if req_item else 1
                db.add(
                    models_buyback.BuybackPackageItem(
                        package_id=package.id,
                        request_item_id=iid,
                        quantity=qty,
                    )
                )

        created.append(package)

    try:
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=admin_user.id,
                action="packages_issued",
                entity_type="buyback_request",
                entity_id=str(request.id),
                details_json=json.dumps(
                    {
                        "package_kind": package_kind,
                        "total_boxes": total_boxes,
                        "package_codes": [p.package_code for p in created],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.add(
            models_buyback.BuybackStatusHistory(
                request_id=request.id,
                from_status=request.status,
                to_status=request.status,
                changed_by_user_id=admin_user.id,
                note=f"梱包バーコード発行（{PACKAGE_KIND_LABELS.get(package_kind, package_kind)} {total_boxes}箱）",
                change_reason="packages_issued",
            )
        )
    except Exception:
        raise

    # Touch updated_at
    request.updated_at = now
    db.commit()

    return [_serialize_package(db, p) for p in created]


def complete_package(
    db: Session,
    *,
    admin_user: models.User,
    package_id: int,
    tracking_number: Optional[str] = None,
    admin_note: Optional[str] = None,
) -> dict:
    package = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.id == package_id)
        .first()
    )
    if not package:
        raise HTTPException(status_code=404, detail="梱包が見つかりません")
    if package.status == models_buyback.BuybackShipmentPackageStatus.shipped.value:
        raise HTTPException(status_code=400, detail="発送済みの梱包は完了処理できません")
    if package.status == models_buyback.BuybackShipmentPackageStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="キャンセル済みの梱包です")

    now = datetime.utcnow()
    values = {
        "status": models_buyback.BuybackShipmentPackageStatus.packed.value,
        "packed_by_user_id": admin_user.id,
        "packed_at": now,
        "updated_at": now,
    }
    if tracking_number is not None:
        tn = tracking_number.strip() or None
        if tn and redact_text(tn) != tn:
            raise HTTPException(status_code=400, detail="追跡番号が不正です")
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
        values["tracking_number"] = tn
    if admin_note is not None:
        values["admin_note"] = redact_text(admin_note.strip()) or None

    try:
        claimed = db.execute(
            update(models_buyback.BuybackShipmentPackage)
            .where(
                models_buyback.BuybackShipmentPackage.id == package.id,
                models_buyback.BuybackShipmentPackage.status.in_(
                    {
                        models_buyback.BuybackShipmentPackageStatus.packing.value,
                        models_buyback.BuybackShipmentPackageStatus.packed.value,
                        models_buyback.BuybackShipmentPackageStatus.awaiting_verify.value,
                    }
                ),
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="発送処理済みの梱包は完了処理できません",
            )
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=admin_user.id,
                action="package_completed",
                entity_type="buyback_shipment_package",
                entity_id=str(package.id),
                details_json=json.dumps(
                    {"package_code": package.package_code},
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="梱包の更新が競合しました",
        ) from exc
    db.refresh(package)
    return _serialize_package(db, package)


def get_package_label_payload(
    db: Session,
    *,
    admin_user: models.User,
    package_id: int,
    include_pii: bool,
    mark_print: bool = False,
    is_reprint: bool = False,
    device_info: Optional[str] = None,
) -> dict:
    package = (
        db.query(models_buyback.BuybackShipmentPackage)
        .filter(models_buyback.BuybackShipmentPackage.id == package_id)
        .first()
    )
    if not package:
        raise HTTPException(status_code=404, detail="梱包が見つかりません")

    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == package.request_id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="買取申請が見つかりません")

    dest = db.query(models.User).filter(models.User.id == package.destination_user_id).first()
    serialized = _serialize_package(db, package)

    payload = {
        **serialized,
        "shop_name": "KRX TCG",
        "public_buyback_code": request.public_buyback_code,
        "request_number": request.request_number,
        "inbound_mgmt_id": request.inbound_mgmt_id,
        "applicant_name": dest.name if include_pii and dest else "—",
        "destination_name": dest.name if include_pii and dest else "—",
        "request_status": request.status,
        "request_status_label": STATUS_LABELS.get(request.status, request.status),
        "item_count": sum(i["quantity"] for i in serialized.get("items") or [])
        or sum(
            item.quantity
            for item in (
                db.query(models_buyback.BuybackRequestItem)
                .filter(models_buyback.BuybackRequestItem.request_id == request.id)
                .all()
            )
        ),
        "handling_note": "取扱注意",
        "is_reprint": is_reprint,
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

    if mark_print:
        try:
            db.add(
                models_buyback.BuybackPackagePrintLog(
                    actor_user_id=admin_user.id,
                    print_type="package_label",
                    entity_type="buyback_shipment_package",
                    entity_id=package.id,
                    includes_pii=include_pii,
                    is_reprint=is_reprint,
                    device_info=(redact_text(device_info) or "")[:255] or None,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.warning(
                "Package print log failed",
                extra={"package_id": package.id},
            )

    return payload
