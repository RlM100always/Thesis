# Cloudflare D1 — B-SMART demo commerce and merchant console

**Verified:** 26 October 2026. Database **`bsmart-commerce`** (Cloudflare D1, APAC), Worker **`bsmart-commerce-api`**, URL https://bsmart-commerce-api.bcs-written-rakib.workers.dev .

Frontend site https://thesis-j0n8.onrender.com uses a dual adapter in `frontend/src/api.js`:

- Cloudflare D1 for `demo-bsmart-*` legacy demonstration stores and for newly created `merchant-*` owner-store IDs / `shop-*` slugs.
- Existing FastAPI for all prior business records, legacy auth and original operational modules. **These have NOT been migrated.** No login/identity synchronization exists between systems.

## D1 features implemented

- 10 labelled synthetic business demo stores plus 259 example products, and persistent D1 product/stock listing via Worker.
- Guest **demo-only** checkout with transactional D1 batch and stock/price-check triggers, order lines, order status token, cancellation and stock return to inventory.
- Anonymous demo customer reference (real entered phone/address not retained).
- New owner onboarding and login via **one-time cryptographically random 256-bit owner access key**, stored as SHA-256 digest in D1; 12-hour hashed bearer sessions. PBKDF2 was unavailable in this particular Worker runtime, so password authentication is intentionally **not** used. Email is *unverified*. Owner access key must be saved; lost-key recovery not implemented. Avoid using this as a production identity system.
- Owner store creation (draft until explicitly made public), product publishing/editing, stock adjustment logs and owner-scoped order status workflow.
- Demo counter POS, recorded atomically with inventory and order rows in D1, and a small example **cashbook**. Not double-entry accounting or actual cash collection.
- React Owner Center page at `/#/d1-owner` with a compact Android-style bottom navigation on mobile.

## D1 schema

`migrations/0001_commerce.sql` through `migrations/0005_demo_cashbook.sql`, source Worker `commerce-worker.js` importing `merchant-routes.js`, config `wrangler.toml`. The existing remote database schema has been advanced to `commerce_meta.schema_version=5` by Cloudflare REST calls.

**Do not blindly run `wrangler d1 migrations apply --remote` on this existing database.** Migrations were applied manually via Cloudflare API, not registered in Wrangler's `d1_migrations` table. One-time `ALTER TABLE` statements would fail if replayed. These migrations are source-controlled for application to a *fresh* new D1 instance once, in order. Before any future changes, align the Wrangler migration ledger or use independently reviewed idempotent migrations, take a backup, and verify `commerce_meta`.

## Verification

- [Owner-created store, demo POS and cashbook reconciliation](https://github.com/RlM100always/Thesis/actions/runs/40326438876)
- [Owner signup/login, product editing, inventory audit and logout/cleanup](https://github.com/RlM100always/Thesis/actions/runs/40325162409)
- [Guest order placement, cancellation and stock reversal](https://github.com/RlM100always/Thesis/actions/runs/40318406288)

GitHub frontend build and API live smoke workflows have passed. The Worker's code has been deployed directly through the Cloudflare API; GitHub commits alone do **not** automatically redeploy Worker script changes unless Cloudflare CI secrets / automatic deploy are configured. The last source-only change improving safe deletion after cashbook entries may not be in the last deployed Worker binary.

## Critical NOT YET migrated

Previous B-SMART business login, true merchant tenant memberships, original POS and full cashflow, stock purchasing, live inventory, receivables, accounting journals, invoicing, supplier/customer CRM, chats, promotional coupons, reviews, fulfillment, app reporting, permission controls and historical customers/orders. All remain in FastAPI's old operational SQLite system. They are **not** Cloudflare D1 primary and not kept in sync with this D1 demo store.

No real payment gateways, credential verification, merchant identity validation, email recovery, abuse protection (Turnstile/rate limits), full privacy compliance, DB restore plan or production backup automation have been completed. Do not collect live money or sensitive shopper data here.

**Temporary CI fixture:** The POS live test created `ci-pos-5b716399edab183e@example.invalid` with an isolated `shop-752c1d2b-b92` demo store and one simulated order. After the test, deletion through the connector was blocked by safety checks, so the fixture remains in D1. It is not a real merchant. Remove it only after checking its exact account/store IDs and dependencies in the Cloudflare dashboard; never run broad deletes against actual merchants.

## Architecture migration path

1. Preserve original database/backup or explicitly accept that unavailable historic data cannot be recreated.
2. Port legacy operational tables and transaction-safe order/stock flows into a D1-native repository/Worker/DO model **with regression and concurrency tests**, and owner-scoped membership authentication.
3. Add privacy-preserving verified merchant login, customer identity, chat, coupons, true accounting double-entry journals, payments and reporting.
4. Implement reliable backups to R2 and tested D1 point-in-time restore before any cutover.
5. Only after verification, switch legacy FastAPI owner modules to the new D1 backend and retire ephemeral SQLite without losing real records.


## Staged real COD foundation (not launched yet)

A guarded **Cash on Delivery** checkout implementation is under review in the `feature/d1-real-cod-foundation-20261026` branch. It includes delivery contact validation, affirmative consent, an hourly per-IP hashed rate limit, D1 transactional stock deduction, merchant-visible addresses, and explicit shipped/fulfilled status transitions. Neither card nor bKash/Nagad/SSLCommerz payments are processed by this Worker.

**Fail-closed by default:** for any real order to be possible, all of these must be true:

1. Apply reviewed migration `cloudflare/migrations/0006_real_cod_gate.sql` **once**, after a verified remote D1 backup and migration-ledger reconciliation.
2. Independently verify the merchant, approve `commerce_stores.real_cod_approved=1` for that exact owner and real store, and set its `is_demo=0`. The owner website cannot self-approve or self-promote a synthetic demo store.
3. Deploy the reviewed Worker bundle, pass frontend and backend tests, and explicitly set `ENABLE_REAL_COD=true` in that Worker's runtime. It defaults to off and stores unapproved.
4. Establish published privacy/retention/deletion guidance, recovery from backups, incident response, merchant support, dispatch procedures, and abuse controls before public orders are enabled.

This does **not** migrate FastAPI users, historical POS or accounting data. There is no delivery carrier integration, verified payment collection, refund gateway, self-service merchant KYC, or production-ready identity recovery. No synthetic records should ever be presented as merchant history. Real delivery and any financial settlement remain the merchant's responsibility outside this release, until separately integrated and verified.

To test this branch locally without collecting real shopper data:

```bash
cd cloudflare
npm test
node --check commerce-worker.js
node --check merchant-routes.js
```

See `docs/D1_REAL_COD_ROLLOUT.md` for required data-protection and cutover checks.
