"""One-off repairs for legacy buyback assessment data inconsistencies."""

from __future__ import annotations

import logging

from sqlalchemy.orm import sessionmaker

from database import engine
from services.buyback_item_labels import infer_line_status_from_assessment
from services.buyback_item_labels import CUSTOMER_REVIEW_REQUEST_STATUSES, infer_line_status_from_assessment

logger = logging.getLogger(__name__)


def repair_legacy_assessment_item_statuses() -> int:
    """Sync pending item line_status from assessment data when request is in review."""
    import models_buyback

    Session = sessionmaker(bind=engine)
    repaired = 0
    with Session() as db:
        try:
            rows = (
                db.query(models_buyback.BuybackRequest)
                .filter(
                    models_buyback.BuybackRequest.status.in_(
                        list(CUSTOMER_REVIEW_REQUEST_STATUSES)
                    )
                )
                .all()
            )
            for request in rows:
                changed = False
                for item in request.items or []:
                    if (item.line_status or "pending") != "pending":
                        continue
                    inferred = infer_line_status_from_assessment(item)
                    if inferred:
                        item.line_status = inferred
                        changed = True
                        repaired += 1
                if changed:
                    request.updated_at = request.updated_at
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("buyback legacy item status repair failed")
    if repaired:
        logger.info("Repaired %s legacy buyback item line statuses", repaired)
    return repaired
