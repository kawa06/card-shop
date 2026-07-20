"""Public-facing buyback identifiers (KRX-BUY / KRX-PKG)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_buyback

SEQ_KIND_BUY = "KRX-BUY"
SEQ_KIND_PKG = "KRX-PKG"
MEMBER_PREFIX = "KRX-MBR"


def _next_daily_code(db: Session, *, seq_kind: str) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    seq_row = (
        db.query(models_buyback.BuybackNumberSequence)
        .filter(
            models_buyback.BuybackNumberSequence.seq_kind == seq_kind,
            models_buyback.BuybackNumberSequence.seq_date == today,
        )
        .with_for_update()
        .first()
    )
    if not seq_row:
        seq_row = models_buyback.BuybackNumberSequence(seq_kind=seq_kind, seq_date=today, last_seq=0)
        db.add(seq_row)
        db.flush()

    seq_row.last_seq += 1
    return f"{seq_kind}-{today}-{seq_row.last_seq:06d}"


def assign_public_buyback_code(db: Session, request: models_buyback.BuybackRequest) -> str:
    if request.public_buyback_code:
        return request.public_buyback_code
    code = _next_daily_code(db, seq_kind=SEQ_KIND_BUY)
    request.public_buyback_code = code
    return code


def assign_inbound_mgmt_id(db: Session, request: models_buyback.BuybackRequest) -> str:
    if request.inbound_mgmt_id:
        return request.inbound_mgmt_id
    code = _next_daily_code(db, seq_kind=SEQ_KIND_PKG)
    request.inbound_mgmt_id = code
    return code


def assign_public_member_id(db: Session, user: models.User) -> str:
    if user.public_member_id:
        return user.public_member_id

    import secrets

    for _ in range(10):
        suffix = secrets.token_hex(4).upper()
        candidate = f"{MEMBER_PREFIX}-{suffix}"
        exists = (
            db.query(models.User.id)
            .filter(models.User.public_member_id == candidate)
            .first()
        )
        if not exists:
            user.public_member_id = candidate
            return candidate

    raise RuntimeError("Failed to assign unique public_member_id")


def build_package_box_code(*, base_mgmt_id: str, box_index: int) -> str:
    """Outbound box code: KRX-PKG-YYYYMMDD-NNNNNN-01"""
    return f"{base_mgmt_id}-{box_index:02d}"
