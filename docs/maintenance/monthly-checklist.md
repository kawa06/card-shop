# Monthly maintenance checklist (Phase 3-10+)

Run at least once per month. Prefer automation (`scripts/` + CI) over ad-hoc clicks.

## Automated / scriptable

| Check | How |
|-------|-----|
| Full backend pytest | `cd backend && python -m pytest tests -q --ignore=tests/e2e` |
| Frontend build | `cd frontend && npm run build` |
| Typecheck | `cd frontend && npx tsc --noEmit` |
| Lint | `cd frontend && npm run lint` |
| Playwright critical | `cd frontend && npx playwright test e2e/phase3-9-oripa.spec.ts e2e/phase3-10-oripa-payment.spec.ts` |
| Oripa reservation consistency | `cd backend && python scripts/check_oripa_consistency.py` |
| Inventory alerts sanity | `cd backend && python -m pytest tests/test_inventory_alerts.py -q` |
| Stripe event idempotency | `cd backend && python -m pytest tests/test_stripe_events.py tests/test_oripa_step10_payment.py -q` |

## Production health

| Check | How |
|-------|-----|
| Railway health | `GET /api/health` → `status=ok`, `database.persistent=true`, version current |
| Vercel production | Open production URL; smoke `/oripa`, `/checkout`, `/mypage` |
| Stripe webhook | Dashboard → webhook endpoint delivery success rate; review failed events |
| Stale reservations | Run consistency script; expire task should clear unpaid `reserved` past TTL |
| Orphan payments | Orders `awaiting_payment` older than 48h without Stripe session; investigate |
| Payment/order mismatch | Paid order with `OripaPurchase.status=pending` → run recovery confirm |
| Refund consistency | Refunded oripa entries must be `retired`, never `available` |
| Audit / error logs | Review Railway logs for `oripa_` audit actions and unhandled exceptions |
| Failed background jobs | Order expiry / point expiry / email scheduler errors in logs |
| DB migration status | Confirm `run_schema_upgrades` columns exist on production PG |
| PostgreSQL backup | See `docs/database-backup.md` — verify latest backup exists |
| Restore procedure | Dry-run document review only (do **not** destroy production) |
| Stripe↔DB mismatch | See `docs/maintenance/stripe-db-mismatch-recovery.md` |
| Dependency updates | `pip list --outdated`, `npm outdated` — schedule security patches |
| Security updates | OS / Railway / Vercel advisories |
| TODO/FIXME | `rg "TODO|FIXME" backend frontend` — triage |

## Oripa-specific (Phase 3-10)

- [ ] Concurrent last-slot still one winner (`test_concurrent_last_slot_one_winner`)
- [ ] Webhook duplicate does not double-assign
- [ ] Unpaid cancel/expiry returns slots to `available`
- [ ] Paid refund keeps `retired` (no resale)
- [ ] Public `/api/oripas` has no linked product / prize fields

## Sign-off

Date: __________  
Operator: __________  
Notes: __________
