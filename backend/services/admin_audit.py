"""Append-only admin audit logging."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

import models_admin
from services.sensitive_redaction import redact_audit_value, redact_text


def _serialize(data: Any) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, str):
        return redact_text(data)
    try:
        return json.dumps(
            redact_audit_value(data),
            ensure_ascii=False,
            default=str,
        )
    except (TypeError, ValueError):
        return redact_text(str(data))


def extract_client_meta(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return redact_text(ip), redact_text(user_agent)


def write_audit_log(
    db: Session,
    *,
    action: str,
    result: str = "success",
    admin_user: Optional[models_admin.AdminUser] = None,
    actor_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str | int] = None,
    before_data: Any = None,
    after_data: Any = None,
    reason: Optional[str] = None,
    request: Optional[Request] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> models_admin.AdminAuditLog:
    if ip_address is None or user_agent is None:
        req_ip, req_ua = extract_client_meta(request)
        ip_address = ip_address or req_ip
        user_agent = user_agent or req_ua

    entry = models_admin.AdminAuditLog(
        admin_user_id=admin_user.id if admin_user else None,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        before_data=_serialize(before_data),
        after_data=_serialize(after_data),
        reason=reason,
        result=result,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry
