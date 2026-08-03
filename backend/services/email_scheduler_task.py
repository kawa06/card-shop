"""Background worker for scheduled email campaigns and failed-send retries."""

from __future__ import annotations

import asyncio
import logging

from services.db_persist import safe_commit
from services.email_broadcast import process_due_scheduled_campaigns, retry_failed_sends

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60


async def background_email_scheduler_task(db_factory) -> None:
    await asyncio.sleep(15)
    while True:
        try:
            db = db_factory()
            try:
                scheduled = process_due_scheduled_campaigns(db)
                retried = retry_failed_sends(db)
                if scheduled or retried:
                    safe_commit(db)
                    logger.info("Email scheduler: campaigns=%s retries=%s", scheduled, retried)
            finally:
                db.close()
        except Exception:
            logger.exception("Email scheduler task failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
