from __future__ import annotations

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import stripe
from fastapi import HTTPException

from config import settings

logger = logging.getLogger(__name__)


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY.strip())


def _is_stripe_permission_denied(exc: stripe.error.StripeError) -> bool:
    code = getattr(exc, "code", None)
    if code == "permission_denied":
        return True
    return "permission denied" in str(exc).lower()


@lru_cache(maxsize=1)
def stripe_key_valid() -> bool:
    if not stripe_configured():
        return False
    _configure_stripe()
    try:
        stripe.Account.retrieve()
        return True
    except stripe.error.AuthenticationError:
        logger.error("Stripe secret key is invalid or revoked")
        return False
    except stripe.error.StripeError as exc:
        # Restricted keys (rk_live_...) often cannot read Account but still work for Checkout.
        if _is_stripe_permission_denied(exc) and settings.STRIPE_SECRET_KEY.strip().startswith("rk_"):
            logger.info("Stripe restricted key authenticated without Account read scope")
            return True
        logger.warning("Stripe key validation failed")
        return False


def _configure_stripe() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY.strip()


def require_stripe() -> None:
    if not stripe_configured():
        raise HTTPException(
            status_code=503,
            detail="Stripe決済の設定が完了していません。管理者にお問い合わせください。",
        )


def build_line_items(cart_items, shipping_fee: int, shipping_label: str) -> list[dict[str, Any]]:
    line_items: list[dict[str, Any]] = []
    for item in cart_items:
        card = item.card
        line_items.append(
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {
                        "name": card.name[:120],
                        "metadata": {"card_id": str(card.id)},
                    },
                    "unit_amount": int(round(card.price)),
                },
                "quantity": item.quantity,
            }
        )

    if shipping_fee > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": shipping_label[:120]},
                    "unit_amount": int(shipping_fee),
                },
                "quantity": 1,
            }
        )

    return line_items


def adjust_line_items_to_total(line_items: list[dict[str, Any]], target_total_jpy: int) -> list[dict[str, Any]]:
    """Reduce line item amounts so Stripe charge matches post-points order total."""
    target_total_jpy = max(0, int(target_total_jpy))
    adjusted = [json_copy_item(item) for item in line_items]

    def line_total(items: list[dict[str, Any]]) -> int:
        total = 0
        for item in items:
            total += int(item["price_data"]["unit_amount"]) * int(item["quantity"])
        return total

    current = line_total(adjusted)
    if current <= target_total_jpy:
        return adjusted

    discount = current - target_total_jpy
    for idx in range(len(adjusted) - 1, -1, -1):
        if discount <= 0:
            break
        item = adjusted[idx]
        unit = int(item["price_data"]["unit_amount"])
        qty = int(item["quantity"])
        line_sum = unit * qty
        if line_sum <= 0:
            continue
        reducible = min(discount, line_sum)
        new_line_sum = line_sum - reducible
        new_unit = new_line_sum // qty if qty else 0
        item["price_data"]["unit_amount"] = new_unit
        discount -= reducible

    if line_total(adjusted) != target_total_jpy and adjusted:
        diff = line_total(adjusted) - target_total_jpy
        last = adjusted[-1]
        qty = max(1, int(last["quantity"]))
        last["price_data"]["unit_amount"] = max(
            0, int(last["price_data"]["unit_amount"]) - (diff // qty)
        )
    return adjusted


def json_copy_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "price_data": {
            "currency": item["price_data"]["currency"],
            "product_data": dict(item["price_data"]["product_data"]),
            "unit_amount": int(item["price_data"]["unit_amount"]),
        },
        "quantity": int(item["quantity"]),
    }


def get_or_create_stripe_customer(email: str) -> str:
    _configure_stripe()
    existing = stripe.Customer.list(email=email, limit=1)
    if existing.data:
        return existing.data[0].id
    customer = stripe.Customer.create(email=email)
    return customer.id


def create_checkout_session(
    *,
    order_id: int,
    customer_email: str,
    line_items: list[dict[str, Any]],
    locale: str = "ja",
    checkout_type: str = "card",
) -> stripe.checkout.Session:
    require_stripe()
    _configure_stripe()

    checkout_type = (checkout_type or "card").lower()
    if checkout_type not in {"card", "bank_transfer"}:
        raise HTTPException(status_code=400, detail="不正な決済種別です")

    params: dict[str, Any] = {
        "mode": "payment",
        "line_items": line_items,
        "metadata": {"order_id": str(order_id), "checkout_type": checkout_type},
        "client_reference_id": str(order_id),
        "locale": locale if locale in {"ja", "en"} else "auto",
        "success_url": f"{settings.FRONTEND_URL.rstrip('/')}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.FRONTEND_URL.rstrip('/')}/checkout/cancel?order_id={order_id}",
    }

    if checkout_type == "bank_transfer":
        # Stripe Checkout `expires_at` must be within 24 hours of session creation.
        stripe_expiry_hours = min(settings.BANK_TRANSFER_PAYMENT_DEADLINE_HOURS, 23)
        deadline = datetime.utcnow() + timedelta(hours=stripe_expiry_hours)
        params["customer"] = get_or_create_stripe_customer(customer_email)
        params["payment_method_types"] = ["customer_balance"]
        params["payment_method_options"] = {
            "customer_balance": {
                "funding_type": "bank_transfer",
                "bank_transfer": {"type": "jp_bank_transfer"},
            }
        }
        params["expires_at"] = int(deadline.timestamp())
    else:
        params["customer_email"] = customer_email
        params["payment_method_types"] = ["card"]

    return stripe.checkout.Session.create(**params)


def retrieve_checkout_session(session_id: str) -> stripe.checkout.Session:
    require_stripe()
    _configure_stripe()
    return stripe.checkout.Session.retrieve(session_id)


def construct_webhook_event(payload: bytes, sig_header: str | None):
    if not settings.STRIPE_WEBHOOK_SECRET.strip():
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
    try:
        return stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc
