"""Background task to expire due point lots."""

from __future__ import annotations

import asyncio
import logging

from services.point_ledger import expire_due_points

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 300  # 5 minutes


async def background_point_expiration_task(db_factory) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            db = db_factory()
            try:
                count = expire_due_points(db)
                if count:
                    db.commit()
                    logger.info("Expired %s point unit(s) across users", count)
            finally:
                db.close()
        except Exception:
            logger.error("Point expiration task failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
