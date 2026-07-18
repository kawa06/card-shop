"""Background task to expire overdue bank-transfer orders."""

from __future__ import annotations

import asyncio
import logging

from services.order_checkout import expire_overdue_bank_transfer_orders

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 300  # 5 minutes


async def background_order_expiry_task(db_factory) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            db = db_factory()
            try:
                count = expire_overdue_bank_transfer_orders(db)
                if count:
                    logger.info("Expired %s overdue bank-transfer order(s)", count)
            finally:
                db.close()
        except Exception as exc:
            logger.error("Order expiry task failed: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
