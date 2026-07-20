"""Customer buyback application form data (PII-minimized for print)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.buyback_barcodes import get_active_barcode_for_entity
from services.buyback_compliance import (
    GUARDIAN_STATUS_LABELS,
    IDENTITY_STATUS_LABELS,
    get_compliance_status,
)
from services.buyback_inbound import provision_request_logistics
from services.buyback_requests import get_user_request

logger = logging.getLogger(__name__)

APPLICATION_FORM_NOTICES = [
    "この申込書を買取品と一緒に箱へ入れてください",
    "申込書がない場合、確認に時間がかかる可能性があります",
    "荷物は元払いで発送してください",
    "着払いで届いた荷物は受取拒否または着払いで返送する場合があります",
    "状態が著しく悪い商品や買取対象外の商品は、買取できない場合があります",
    "発送前に申込内容と同梱商品を確認してください",
]


def _log_print(
    db: Session,
    *,
    actor_user_id: int,
    request_id: int,
    print_type: str,
    is_reprint: bool,
    device_info: Optional[str] = None,
) -> None:
    try:
        db.add(
            models_buyback.BuybackPackagePrintLog(
                actor_user_id=actor_user_id,
                print_type=print_type,
                entity_type="buyback_request",
                entity_id=request_id,
                includes_pii=False,
                is_reprint=is_reprint,
                device_info=(device_info or "").strip() or None,
            )
        )
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=actor_user_id,
                action="application_form_printed",
                entity_type="buyback_request",
                entity_id=str(request_id),
                details_json=json.dumps(
                    {
                        "print_type": print_type,
                        "is_reprint": is_reprint,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    except Exception as exc:
        logger.warning("Failed to write application form print log: %s", exc)


def build_application_form(
    db: Session,
    *,
    user: models.User,
    request_id: int,
    mark_issued: bool = False,
    print_type: str = "application_a4",
    device_info: Optional[str] = None,
) -> dict:
    """Return print-safe application form payload for the owning customer."""
    request = get_user_request(db, user_id=user.id, request_id=request_id)
    if request.status == models_buyback.BuybackRequestStatus.draft.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="下書きの申込書は印刷できません",
        )

    declared_item_count = sum(item.quantity for item in (request.items or []))
    inbound, barcode = provision_request_logistics(
        db,
        request=request,
        user=user,
        declared_item_count=declared_item_count,
    )

    # Prefer active barcode after provision (idempotent)
    active = get_active_barcode_for_entity(
        db,
        entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
        entity_id=inbound.id,
        barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
    )
    if active:
        barcode = active

    compliance = get_compliance_status(db, user_id=user.id, requires_guardian=False)
    guardian = compliance.get("guardian_status")
    guardian_label = None
    if guardian:
        guardian_label = GUARDIAN_STATUS_LABELS.get(guardian, guardian)
    elif compliance.get("requires_guardian_consent"):
        guardian_label = "未申請"

    is_reprint = bool(request.application_form_issued_at)
    now = datetime.utcnow()
    if mark_issued and not request.application_form_issued_at:
        request.application_form_issued_at = now
        request.updated_at = now

    if mark_issued:
        _log_print(
            db,
            actor_user_id=user.id,
            request_id=request.id,
            print_type=print_type,
            is_reprint=is_reprint,
            device_info=device_info,
        )

    db.commit()
    db.refresh(request)
    db.refresh(user)

    items = [
        {
            "product_name": item.product_name_snapshot,
            "condition_code": item.condition_code,
            "quantity": item.quantity,
        }
        for item in (request.items or [])
    ]

    planned = request.customer_planned_ship_date
    return {
        "shop_name": settings.SITE_NAME or "KRX TCG",
        "request_id": request.id,
        "request_number": request.request_number,
        "public_buyback_code": request.public_buyback_code,
        "inbound_mgmt_id": request.inbound_mgmt_id or inbound.inbound_mgmt_id,
        "public_member_id": user.public_member_id,
        "applicant_name": user.name,
        "submitted_at": request.submitted_at or request.created_at,
        "customer_planned_ship_date": planned.isoformat() if planned else None,
        "declared_item_count": declared_item_count,
        "items": items,
        "identity_status": compliance.get("identity_status"),
        "identity_status_label": compliance.get("identity_status_label")
        or IDENTITY_STATUS_LABELS.get(compliance.get("identity_status"), "—"),
        "guardian_status": guardian,
        "guardian_status_label": guardian_label,
        "requires_guardian_consent": bool(compliance.get("requires_guardian_consent")),
        "scan_token": barcode.scan_token,
        "barcode_human_readable": barcode.human_readable or request.inbound_mgmt_id,
        "application_form_issued_at": request.application_form_issued_at,
        "is_reprint": is_reprint and mark_issued,
        "notices": list(APPLICATION_FORM_NOTICES),
    }
