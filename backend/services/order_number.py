"""Human-readable order number generation (KRX-YYYYMMDD-NNNN)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import models


def assign_order_number(db: Session, order: models.Order) -> str:
    """Assign a unique order number at payment completion. Idempotent if already set."""
    if order.order_number:
        return order.order_number

    today = datetime.utcnow().strftime("%Y%m%d")
    seq_row = (
        db.query(models.OrderNumberSequence)
        .filter(models.OrderNumberSequence.seq_date == today)
        .with_for_update()
        .first()
    )
    if not seq_row:
        seq_row = models.OrderNumberSequence(seq_date=today, last_seq=0)
        db.add(seq_row)
        db.flush()

    seq_row.last_seq += 1
    order.order_number = f"KRX-{today}-{seq_row.last_seq:04d}"
    return order.order_number
