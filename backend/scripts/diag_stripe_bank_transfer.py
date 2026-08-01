"""Probe Stripe bank-transfer checkout session creation (diagnostic)."""

from __future__ import annotations

import os
import sys

import stripe


def main() -> int:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        print("ERROR=no_stripe_key")
        return 1

    stripe.api_key = key
    print(f"KEY_TYPE={'restricted' if key.startswith('rk_') else 'secret'}")

    # 1) Customer API (required for bank transfer)
    try:
        existing = stripe.Customer.list(email="diag@example.com", limit=1)
        print(f"CUSTOMER_LIST=ok count={len(existing.data)}")
    except stripe.error.StripeError as exc:
        print(f"CUSTOMER_LIST=fail code={getattr(exc, 'code', None)} msg={getattr(exc, 'user_message', None) or str(exc)[:200]}")
        return 2

    try:
        customer = stripe.Customer.create(email="diag-bank-transfer@example.com")
        print(f"CUSTOMER_CREATE=ok id={customer.id}")
    except stripe.error.StripeError as exc:
        print(f"CUSTOMER_CREATE=fail code={getattr(exc, 'code', None)} msg={getattr(exc, 'user_message', None) or str(exc)[:200]}")
        return 3

    # 2) Card checkout baseline
    try:
        card = stripe.checkout.Session.create(
            mode="payment",
            customer_email="diag-bank-transfer@example.com",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "jpy",
                        "product_data": {"name": "diag-card"},
                        "unit_amount": 1500,
                    },
                    "quantity": 1,
                }
            ],
            success_url="https://frontend-one-topaz-20.vercel.app/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://frontend-one-topaz-20.vercel.app/checkout/cancel",
        )
        print(f"CARD_SESSION=ok id={card.id}")
    except stripe.error.StripeError as exc:
        print(f"CARD_SESSION=fail code={getattr(exc, 'code', None)} msg={getattr(exc, 'user_message', None) or str(exc)[:200]}")
        return 4

    # 3) Bank transfer checkout
    import time
    from datetime import datetime, timedelta

    expires = int((datetime.utcnow() + timedelta(hours=48)).timestamp())
    try:
        bank = stripe.checkout.Session.create(
            mode="payment",
            customer=customer.id,
            payment_method_types=["customer_balance"],
            payment_method_options={
                "customer_balance": {
                    "funding_type": "bank_transfer",
                    "bank_transfer": {"type": "jp_bank_transfer"},
                }
            },
            line_items=[
                {
                    "price_data": {
                        "currency": "jpy",
                        "product_data": {"name": "diag-bank"},
                        "unit_amount": 1500,
                    },
                    "quantity": 1,
                }
            ],
            success_url="https://frontend-one-topaz-20.vercel.app/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://frontend-one-topaz-20.vercel.app/checkout/cancel",
            expires_at=expires,
            metadata={"checkout_type": "bank_transfer", "order_id": "diag"},
        )
        print(f"BANK_SESSION=ok id={bank.id} url={'yes' if bank.url else 'no'}")
    except stripe.error.StripeError as exc:
        print(f"BANK_SESSION=fail code={getattr(exc, 'code', None)} msg={getattr(exc, 'user_message', None) or str(exc)[:300]}")
        # retry without expires_at
        try:
            bank2 = stripe.checkout.Session.create(
                mode="payment",
                customer=customer.id,
                payment_method_types=["customer_balance"],
                payment_method_options={
                    "customer_balance": {
                        "funding_type": "bank_transfer",
                        "bank_transfer": {"type": "jp_bank_transfer"},
                    }
                },
                line_items=[
                    {
                        "price_data": {
                            "currency": "jpy",
                            "product_data": {"name": "diag-bank-no-expiry"},
                            "unit_amount": 1500,
                        },
                        "quantity": 1,
                    }
                ],
                success_url="https://frontend-one-topaz-20.vercel.app/checkout/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="https://frontend-one-topaz-20.vercel.app/checkout/cancel",
                metadata={"checkout_type": "bank_transfer", "order_id": "diag"},
            )
            print(f"BANK_SESSION_NO_EXPIRY=ok id={bank2.id}")
        except stripe.error.StripeError as exc2:
            print(
                f"BANK_SESSION_NO_EXPIRY=fail code={getattr(exc2, 'code', None)} msg={getattr(exc2, 'user_message', None) or str(exc2)[:300]}"
            )
            return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
