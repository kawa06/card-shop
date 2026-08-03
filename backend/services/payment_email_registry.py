"""Payment/order email event registry — add new payment methods without changing send code."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class OrderEmailEventDef:
    """Maps a business event to a template key, with optional payment-method overrides."""

    event_key: str
    default_template_key: str
    description: str
    payment_method_templates: dict[str, str] = field(default_factory=dict)
    status_flag: str = ""


# ── Core order/payment events (10 templates requested) ──────────────────────

ORDER_EMAIL_EVENTS: dict[str, OrderEmailEventDef] = {
    "order_completed": OrderEmailEventDef(
        event_key="order_completed",
        default_template_key="order_completed",
        description="注文完了",
        status_flag="order_completed_ok",
    ),
    "order_received": OrderEmailEventDef(
        event_key="order_received",
        default_template_key="order_received",
        description="注文受付",
        status_flag="order_received_ok",
    ),
    "payment_pending": OrderEmailEventDef(
        event_key="payment_pending",
        default_template_key="order_payment_pending",
        description="決済待ち",
        payment_method_templates={
            "stripe_bank_transfer": "order_bank_transfer",
            "bank_transfer": "order_bank_transfer",
            "konbini": "order_konbini_pending",
            "cvs": "order_konbini_pending",
        },
        status_flag="payment_pending_ok",
    ),
    "payment_success": OrderEmailEventDef(
        event_key="payment_success",
        default_template_key="order_payment_confirmed",
        description="決済成功",
        status_flag="purchase_ok",
    ),
    "payment_failed": OrderEmailEventDef(
        event_key="payment_failed",
        default_template_key="order_payment_failed",
        description="決済失敗",
        status_flag="payment_failed_ok",
    ),
    "payment_expired": OrderEmailEventDef(
        event_key="payment_expired",
        default_template_key="order_payment_expired",
        description="決済期限切れ",
        payment_method_templates={
            "stripe_bank_transfer": "order_payment_expired",
            "bank_transfer": "order_payment_expired",
        },
        status_flag="bank_transfer_expired_ok",
    ),
    "order_cancelled": OrderEmailEventDef(
        event_key="order_cancelled",
        default_template_key="order_cancelled",
        description="注文キャンセル",
        status_flag="bank_transfer_cancelled_ok",
    ),
    "refund_completed": OrderEmailEventDef(
        event_key="refund_completed",
        default_template_key="order_refund",
        description="返金完了",
        status_flag="refund_ok",
    ),
}


def resolve_order_template_key(
    event_key: str,
    payment_method: Optional[str] = None,
) -> str:
    """Resolve template key for an order email event, with payment-method override."""
    event = ORDER_EMAIL_EVENTS.get(event_key)
    if not event:
        return event_key
    method = (payment_method or "").strip().lower()
    if method and method in event.payment_method_templates:
        return event.payment_method_templates[method]
    return event.default_template_key


def get_order_email_event(event_key: str) -> Optional[OrderEmailEventDef]:
    return ORDER_EMAIL_EVENTS.get(event_key)


def register_payment_method_template(
    event_key: str,
    payment_method: str,
    template_key: str,
) -> None:
    """Runtime registration for new payment methods (e.g. PayPay, Apple Pay)."""
    event = ORDER_EMAIL_EVENTS.get(event_key)
    if not event:
        raise KeyError(f"Unknown order email event: {event_key}")
    # frozen dataclass — use object.__setattr__ on payment_method_templates copy
    # For simplicity, document that new methods are added to ORDER_EMAIL_EVENTS dict at deploy time.
    raise NotImplementedError(
        "Add payment method templates to ORDER_EMAIL_EVENTS in payment_email_registry.py"
    )
