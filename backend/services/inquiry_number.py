"""Human-readable inquiry number generation (INQ-YYYYMMDD-NNNN)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

import models


def assign_inquiry_number(db: Session) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    seq_row = (
        db.query(models.InquiryNumberSequence)
        .filter(models.InquiryNumberSequence.seq_date == today)
        .with_for_update()
        .first()
    )
    if not seq_row:
        seq_row = models.InquiryNumberSequence(seq_date=today, last_seq=0)
        db.add(seq_row)
        db.flush()

    seq_row.last_seq += 1
    return f"INQ-{today}-{seq_row.last_seq:04d}"
