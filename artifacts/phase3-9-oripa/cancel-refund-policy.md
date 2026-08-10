# Phase 3-9 Step 8 — Cancel / Refund / Recovery policy

## Number resale (fairness)
Once an entry number has been assigned to a user (and therefore revealed),
**it must never return to `available`**. Cancel / refund retires the entry
(`assignment_status=retired`, `shipment_status=cancelled`).

## Scenarios
| Case | Behavior |
|------|----------|
| Payment failure / pre-assignment | `OripaPurchase.status=failed`; no entries assigned (idempotent key) |
| Post-assign, held, pre-ship cancel | Purchase `cancelled`; entries `retired` (no resale) |
| Shipment cancel (unshipped) | Entries return to `held` for same user; shipment `cancelled`; fees unchanged |
| Purchase cancel while pending_ship | Entries retired; removed from shipment; empty shipment auto-cancelled |
| Post-ship cancel | Blocked via API (409). Ops handles money outside this engine; numbers stay shipped |
| Duplicate cancel / refund webhook | Idempotent — second call returns cancelled purchase |

## Existing systems
- **Does not** invent partial-refund restore for points / coupons / Stripe.
- Oripa interim purchase path does not mutate Card.stock on assign/link; cancel does not invent stock restore.
- Normal Order refunds continue to use existing checkout / Stripe handlers unchanged.
