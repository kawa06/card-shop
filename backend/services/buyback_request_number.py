"""Human-readable buyback request numbers (KBB-YYYYMMDD-NNNN)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import models_buyback


def assign_buyback_request_number(db: Session, request: models_buyback.BuybackRequest) -> str:
    """Assign a unique request number at submission. Idempotent if already set."""
    if request.request_number:
        return request.request_number

    today = datetime.utcnow().strftime("%Y%m%d")
    seq_row = (
        db.query(models_buyback.BuybackRequestNumberSequence)
        .filter(models_buyback.BuybackRequestNumberSequence.seq_date == today)
        .with_for_update()
        .first()
    )
    if not seq_row:
        seq_row = models_buyback.BuybackRequestNumberSequence(seq_date=today, last_seq=0)
        db.add(seq_row)
        db.flush()

    seq_row.last_seq += 1
    request.request_number = f"KBB-{today}-{seq_row.last_seq:04d}"
    return request.request_number
