"""Unified buyback logistics audit / scan / print log listing."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
import models_buyback


def write_buyback_audit(
    db: Session,
    *,
    actor_user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    details: Optional[dict] = None,
) -> None:
    db.add(
        models_buyback.BuybackAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=json.dumps(details, ensure_ascii=False) if details else None,
        )
    )


def write_package_print_log(
    db: Session,
    *,
    actor_user_id: int,
    print_type: str,
    entity_type: str,
    entity_id: int,
    includes_pii: bool = False,
    is_reprint: bool = False,
    device_info: Optional[str] = None,
) -> None:
    db.add(
        models_buyback.BuybackPackagePrintLog(
            actor_user_id=actor_user_id,
            print_type=print_type,
            entity_type=entity_type,
            entity_id=entity_id,
            includes_pii=includes_pii,
            is_reprint=is_reprint,
            device_info=(device_info or "")[:255] or None,
        )
    )


def _actor_name(db: Session, user_id: Optional[int], cache: dict[int, str]) -> Optional[str]:
    if not user_id:
        return None
    if user_id in cache:
        return cache[user_id]
    user = db.query(models.User).filter(models.User.id == user_id).first()
    name = user.name if user else None
    cache[user_id] = name or f"#{user_id}"
    return cache[user_id]


def _parse_details(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"raw": raw[:200]}


def list_logistics_logs(
    db: Session,
    *,
    log_type: Optional[str] = None,
    request_id: Optional[int] = None,
    package_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Merge scan / print / buyback audit rows into one timeline (newest first)."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    wanted = (log_type or "all").strip().lower()
    rows: list[dict[str, Any]] = []
    actors: dict[int, str] = {}

    if wanted in ("all", "scan"):
        q = db.query(models_buyback.BuybackPackageScanLog)
        if request_id:
            q = q.filter(models_buyback.BuybackPackageScanLog.request_id == request_id)
        if package_id:
            q = q.filter(models_buyback.BuybackPackageScanLog.package_id == package_id)
        for log in q.order_by(models_buyback.BuybackPackageScanLog.created_at.desc()).limit(300).all():
            rows.append(
                {
                    "id": f"scan-{log.id}",
                    "log_type": "scan",
                    "action": log.action,
                    "result": log.result,
                    "actor_user_id": log.actor_user_id,
                    "actor_name": _actor_name(db, log.actor_user_id, actors),
                    "request_id": log.request_id,
                    "package_id": log.package_id,
                    "entity_type": "barcode_scan",
                    "entity_id": str(log.barcode_id) if log.barcode_id else None,
                    "includes_pii": None,
                    "is_reprint": None,
                    "scan_token_prefix": (log.scan_token or "")[:8] or None,
                    "details": _parse_details(log.details_json),
                    "device_info": log.device_info,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at,
                }
            )

    if wanted in ("all", "print"):
        package_ids_for_request: set[int] = set()
        if request_id:
            package_ids_for_request = {
                row[0]
                for row in db.query(models_buyback.BuybackShipmentPackage.id)
                .filter(models_buyback.BuybackShipmentPackage.request_id == request_id)
                .all()
            }
        q = db.query(models_buyback.BuybackPackagePrintLog)
        for log in q.order_by(models_buyback.BuybackPackagePrintLog.created_at.desc()).limit(300).all():
            if package_id and not (
                log.entity_type == "buyback_shipment_package" and log.entity_id == package_id
            ):
                continue
            if request_id:
                ok = (
                    (log.entity_type == "buyback_request" and log.entity_id == request_id)
                    or (
                        log.entity_type == "buyback_shipment_package"
                        and log.entity_id in package_ids_for_request
                    )
                )
                if not ok:
                    continue
            rows.append(
                {
                    "id": f"print-{log.id}",
                    "log_type": "print",
                    "action": log.print_type,
                    "result": "ok",
                    "actor_user_id": log.actor_user_id,
                    "actor_name": _actor_name(db, log.actor_user_id, actors),
                    "request_id": log.entity_id if log.entity_type == "buyback_request" else request_id,
                    "package_id": log.entity_id
                    if log.entity_type == "buyback_shipment_package"
                    else None,
                    "entity_type": log.entity_type,
                    "entity_id": str(log.entity_id),
                    "includes_pii": log.includes_pii,
                    "is_reprint": log.is_reprint,
                    "scan_token_prefix": None,
                    "details": None,
                    "device_info": log.device_info,
                    "ip_address": None,
                    "created_at": log.created_at,
                }
            )

    if wanted in ("all", "audit"):
        q = db.query(models_buyback.BuybackAuditLog)
        audit_actions_prefix = (
            "pii_",
            "package_",
            "inbound_",
            "ship_",
            "receive",
            "application_",
            "label_",
        )
        for log in q.order_by(models_buyback.BuybackAuditLog.created_at.desc()).limit(400).all():
            action = log.action or ""
            if not any(action.startswith(p) for p in audit_actions_prefix) and action not in {
                "request_submitted",
                "status_changed",
            }:
                # keep logistics-related; still include common buyback admin actions
                if "buyback" not in (log.entity_type or ""):
                    continue
            req_id = None
            pkg_id = None
            if log.entity_type == "buyback_request" and log.entity_id and log.entity_id.isdigit():
                req_id = int(log.entity_id)
            if log.entity_type in {"buyback_shipment_package", "package"} and log.entity_id and log.entity_id.isdigit():
                pkg_id = int(log.entity_id)
            if request_id and req_id != request_id and pkg_id is None:
                details = _parse_details(log.details_json) or {}
                if details.get("request_id") != request_id:
                    continue
            if package_id and pkg_id != package_id:
                details = _parse_details(log.details_json) or {}
                if details.get("package_id") != package_id:
                    continue
            rows.append(
                {
                    "id": f"audit-{log.id}",
                    "log_type": "audit",
                    "action": log.action,
                    "result": "ok",
                    "actor_user_id": log.actor_user_id,
                    "actor_name": _actor_name(db, log.actor_user_id, actors),
                    "request_id": req_id,
                    "package_id": pkg_id,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                    "includes_pii": "pii" in action,
                    "is_reprint": None,
                    "scan_token_prefix": None,
                    "details": _parse_details(log.details_json),
                    "device_info": None,
                    "ip_address": None,
                    "created_at": log.created_at,
                }
            )

    def sort_key(row: dict[str, Any]) -> datetime:
        ts = row.get("created_at")
        return ts if isinstance(ts, datetime) else datetime.min

    rows.sort(key=sort_key, reverse=True)
    total = len(rows)
    page = rows[offset : offset + limit]
    return page, total
