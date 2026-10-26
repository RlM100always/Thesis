# B-SMART production commerce cutover — 26 Oct 2026

## Implemented in the COD staging branch

- Guarded real-COD checkout on D1 only when the merchant was independently approved **and** the Worker environment feature flag was deliberately enabled.
- Customer consent and Bangladesh phone/address validation (no bank/card capture).
- D1 atomic order+lines+stock update via existing triggers; stock is restored on cancellation.
- Per-store/hour hash-of-IP checkout throttle (five requests/hour as a baseline; not a replacement for managed bot protection).
- Owner order list with shipping information, confirm/ship/fulfil/cancel controls, and optimistic status update checking.
- Frontend prevents real checkout if the backend reports it disabled, with explicit personal-data consent for enabled COD.
- New Node unit/Worker route tests on GitHub Actions.

## Production release gates — no public real orders before all are complete

| Gate | Status |
|---|---|
| GitHub change review, Node tests, React production build | PR verification required |
| Remote D1 snapshot / point-in-time recovery drill | NOT verified |
| Reconcile D1 migration ledger and apply v6 schema exactly once | NOT applied |
| Deploy Worker after migration | NOT deployed |
| Deploy frontend after CI | NOT deployed |
| Merchant identity/document approval for each proposed real merchant | NOT completed |
| Privacy notice, retention period, PII deletion/export, access/security review | NOT completed |
| Abuse protection, logging, alerting, operational support | PARTIAL (rate limit only) |
| Merchant delivery workflow, address verification and COD settlement proof | NOT externally verified |
| bKash / Nagad / SSLCommerz merchant onboarding, live callbacks | NOT configured |
| Legacy FastAPI orders/users/POS/CRM/accounting migration and reconciliation | NOT completed |

**Do not set** `ENABLE_REAL_COD=true`, change `is_demo`, or issue real customer checkout links until every relevant gate above has passed. Never touch demo research shop identities or invent missing real orders.

## Minimum proposed cutover process

1. Export/secure a consistent backup of the *operational* FastAPI database (if extant), and separately snapshot D1; validate recovery in isolation.
2. Capture schema and row-count inventory for the original POS, order, stock, customer and accounting tables and create tenant-id mapping. Historical data without a usable backup remains unavailable.
3. Port business/tenant/membership identity with verified login, password recovery, MFA and row-level tenant authorization; reconcile imported order and payment totals before any routing switch.
4. Add transactional D1-native POS/supplier/purchasing, ledger/journals, discounts/coupons, inventory movements, delivery, CRM, chat and reports, each with tenant data separation tests.
5. Add authenticated payment provider setup; use provider-hosted payment sessions and signed webhook callbacks. Never trust client screenshots or mark payment complete based only on an order status.
6. Publish and test privacy/data export/deletion policies, monitoring, anti-abuse, backups, recovery, real-device UX, concurrency tests and disaster drills.
7. Roll out per merchant behind kill switches, check totals against original DB, then remove dual backend routing only after parity tests pass.

For now the existing real FastAPI modules and the new D1 system must remain separated. This staged PR is a foundation, not a production release.
