"""One-off Stripe key validation (does not print secrets)."""
import os
import sys

import stripe

key = (os.getenv("STRIPE_SECRET_KEY") or "").strip().replace("\n", "").replace("\r", "").replace(" ", "")
print(f"len={len(key)}")
if not key:
    print("STRIPE_FAIL missing key")
    sys.exit(1)

stripe.api_key = key
try:
    stripe.Account.retrieve()
    print("STRIPE_OK")
except stripe.error.AuthenticationError as exc:
    print("STRIPE_FAIL auth", str(exc)[:120])
    sys.exit(1)
except stripe.error.StripeError as exc:
    if key.startswith("rk_") and (
        getattr(exc, "code", None) == "permission_denied"
        or "permission denied" in str(exc).lower()
    ):
        print("STRIPE_OK restricted")
        sys.exit(0)
    print("STRIPE_FAIL", str(exc)[:120])
    sys.exit(1)
except Exception as exc:
    print("STRIPE_FAIL", str(exc)[:120])
    sys.exit(1)
