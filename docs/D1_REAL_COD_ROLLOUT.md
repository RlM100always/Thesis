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


## Advanced operations, D1 v7 (staging, not deployed)

The same feature branch now includes a second additive migration,
`cloudflare/migrations/0007_merchant_insights_inventory_audit.sql`. Run it
**only after v6**, a verified backup, Cloudflare migration ledger review and CI.
Do not run these source-controlled migrations blindly against an existing DB.
The live connected D1 was last read at schema version 5.

- **Read-only merchant analytics**: `GET /api/merchant/insights?days=7|30|90`.
  Returns days, order breakdown, daily booked amounts, top products and up to
  50 published low-stock SKUs. All SQL filters by the logged-in merchant's
  store; totals are *orders booked*, never verified payment, cash or profit.
- **Reorder threshold**: `commerce_products.reorder_point` defaults to 5 and
  can be edited per SKU. Owner dashboard shows threshold-based alerts.
- **Atomic inventory correction**:
  `POST /api/merchant/inventory/corrections` requires auth and accepts
  `{product_id,delta,reason,note}`, signed integer quantity with range
  ±10000, reason restock/damage/stocktake/return/other, and a note of up to
  120 characters. An insert trigger enforces store ownership, prevents negative
  or excessive stock and writes a before/after audit row in the same SQLite
  transaction. On real stores, direct stock edits through product PATCH are
  deliberately rejected, so corrections must be audited. This is not an
  invoice, supplier purchase, physical stock verification, or payment.
- **Immutable status events**: existing order statuses are imported as *one
  baseline event*, not fabricated timelines; new order creation and every
  status change append timestamped events via triggers. Owner order detail
  endpoint is tenant-authenticated; public status tokens show only
  status/timestamps, never another merchant's private notes or login data.
- **Merchant UI**: insights, daily bars, top products, low-stock panel,
  auditable stock corrections, order filtering/search and customer-facing
  status history. Mobile navigation and keyboard focus are improved.

CI must pass **Node unit tests, API gate tests, React build, Python existing
integration tests, and in-memory D1 migrations 0001–0007 tests**, including
stock underflow, cross-store correction, cancel/reversal and event immutability.
A success in isolated in-memory SQLite is NOT a substitute for Cloudflare D1
staging and real-device end-to-end testing.

## Before any production promotion

- Verify buyer/privacy disclosures and a retention/deletion process for names,
  phone numbers, addresses and order tracking links.
- Restore and reconcile a genuine operational database backup; do not claim
  old FastAPI customer/orders have moved to D1.
- Verify merchant identity; use independent administrative approval only. No
  merchant-side self-approval and no live checkout flag enabled by default.
- Add reliable notification delivery, actual carrier tracking integrations,
  payment gateway credentials and verified callbacks, accounting, refund
  workflows and secure key recovery as separate audited releases.


## Safe retry handling (D1 v8)

A third **unapplied** migration, `0008_checkout_idempotency.sql`,
introduces a merchant-scoped unique checkout request key. Real COD checkout
requires a UUID v4 supplied by the browser and returns the original order on
repeated requests with the same ID and matching customer name/phone, rather
than reserving inventory again. Concurrent duplicate inserts are stopped by a
unique index; the error handler retrieves the first order if its contact
matches. Demo requests remain unchanged. No gateway payment is charged.
A lost browser state or deliberate different request ID is still a new order,
so refund/support and manual duplicate review must remain available.

**Current staging schema sequence is now 0001 through 0008**. Source-only
merge, PR approval or passing local tests do not apply these migrations to
remote Cloudflare D1. Obtain an operator-reviewed backup and apply them only
after reconciliation of the existing migration ledger.
