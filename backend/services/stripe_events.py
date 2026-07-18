"""Idempotent Stripe webhook event tracking."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models


def claim_stripe_event(
    db: Session,
    event_id: str,
    event_type: str | None = None,
    order_id: int | None = None,
) -> bool:
    """
    Record a Stripe event if not yet processed.
    Returns True if this call claimed the event (should process).
    Returns False if already processed (skip duplicate webhook delivery).
    """
    if not event_id:
        return True

    existing = (
        db.query(models.StripeProcessedEvent)
        .filter(models.StripeProcessedEvent.event_id == event_id)
        .first()
    )
    if existing:
        return False

    db.add(
        models.StripeProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            order_id=order_id,
        )
    )
    db.flush()
    return True


def save_stripe_payment_refs(
    order: models.Order,
    *,
    payment_intent_id: str | None = None,
    event_id: str | None = None,
) -> None:
    if payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id
    if event_id:
        order.stripe_event_id = event_id
