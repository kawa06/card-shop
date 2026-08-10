# Phase 3-9 Step 7 — Shipping fee policy (consolidation)

## Existing system
- Shipping fees are calculated and charged on each `Order` at checkout (`shipping_fee` / `packaging_fee`).
- There is no prior "consolidate shipments and refund/recharge" specification.

## Phase 3-9 minimal safe rule
When consolidating paid normal orders and/or held oripa entries into one `Shipment`:

1. **Do not refund** previously paid `Order.shipping_fee` / `packaging_fee`.
2. **Do not charge additional** shipping for the consolidated package via API.
3. Consolidation updates **fulfillment status / tracking only**.
4. Oripa interim purchase path currently assigns numbers without collecting shipping at buy-time; shipping is handled at shipment time operationally.

This avoids inventing partial refund / additional Stripe charge logic inside Phase 3-9.
