# Stripe / DB mismatch recovery

If Stripe shows `paid` but the order is still `awaiting_payment`:

1. Confirm the Checkout Session / PaymentIntent in Stripe Dashboard (do not trust frontend redirect alone).
2. Prefer letting the webhook retry (`checkout.session.completed` / `async_payment_succeeded`).
3. If webhook delivery failed permanently, use existing admin recovery / `fulfill_order_inventory` paths (idempotent). Oripa slots stay `reserved` until confirm; do not manually set them `available` if payment may have succeeded.
4. After recovery, run `python scripts/check_oripa_consistency.py`.

Never destroy production to “test restore”. Validate restore on a temporary Railway Postgres clone when needed.
