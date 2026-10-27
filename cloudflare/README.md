# Cloudflare D1 — B-SMART demo commerce and merchant console

**Project reference:** Database **`bsmart-commerce`**, Worker **`bsmart-commerce-api`**, URL https://bsmart-commerce-api.bcs-written-rakib.workers.dev. Source and deployed Worker code may differ until deployment is verified.

Frontend site https://thesis-j0n8.onrender.com uses a dual adapter in `frontend/src/api.js`:

- Cloudflare D1 for `demo-bsmart-*` legacy demonstration stores and for newly created `merchant-*` owner-store IDs / `shop-*` slugs.
- Existing FastAPI for all prior business records, legacy auth and original operational modules. **These have NOT been migrated.** No login/identity synchronization exists between systems.

## D1 features implemented

- 10 labelled synthetic business demo stores plus 259 example products, and persistent D1 product/stock listing via Worker.
- Guest **demo-only** checkout with transactional D1 batch and stock/price-check triggers, order lines, order status token, cancellation and stock return to inventory.
- Shared D1 customer accounts across demo stores: registration/login, profile/avatar, password change with session revocation, saved Bangladesh addresses, account-wide order history, server-side per-store carts, cross-store wishlist, verified-purchase reviews, support chat and return requests. Customer contact/address details are stored in D1; use synthetic/test data only.
- New owner onboarding and login via **one-time cryptographically random 256-bit owner access key**, stored as SHA-256 digest in D1; 12-hour hashed bearer sessions. PBKDF2 was unavailable in this particular Worker runtime, so password authentication is intentionally **not** used. Email is *unverified*. Owner access key must be saved; lost-key recovery not implemented. Avoid using this as a production identity system.
- Owner store creation (draft until explicitly made public), product publishing/editing, product descriptions/brands/tags/compare-at prices, stock adjustment logs, owner-scoped order status workflow, customer message inbox and return management.
- Staged customer-visible order tracking: placed → confirmed → processing → ready → dispatched → delivered. Legacy `fulfilled` and `shipped` statuses remain readable; each merchant transition stores a status note.
- Platform admin may explicitly promote only merchant-owned stores to operational COD checkout after confirmation. Approved operational stores accept COD/manual fulfilment only; seeded demo stores remain demo-only, and online payment, courier and refund integrations are not enabled.
- Demo counter POS, recorded atomically with inventory and order rows in D1, and a small example **cashbook**. Not double-entry accounting or actual cash collection.
- React Owner Center at `/#/d1-owner` with mobile navigation, plus a secret-protected Platform Admin page at `/#/d1-platform-admin` for store moderation, order oversight and audit history.

## D1 schema

Source migrations extend through `migrations/0007_customer_commerce_workflows.sql`. The Worker imports `customer-routes.js`, `merchant-routes.js`, and `platform-admin-routes.js`. The last documented remote schema level is 5; do not assume migrations 0006–0007 have been applied remotely until queried and verified.

**Do not blindly run `wrangler d1 migrations apply --remote` on this existing database.** Migrations were applied manually via Cloudflare API, not registered in Wrangler's `d1_migrations` table. One-time `ALTER TABLE` statements would fail if replayed. The source migration sequence is tested locally in CI, but that does not prove remote D1 is migrated. Before deploying 0006–0007: take and verify a D1 backup/export, query the live schema and `commerce_meta`, apply only the reviewed additive SQL that is missing, then re-query new tables/columns/triggers.


## Platform admin secret setup

Configure the Worker secret after the platform-admin code is deployed:

```sh
cd cloudflare
npx wrangler secret put PLATFORM_ADMIN_KEY
```

Use a long, unique random value of at least 32 characters. Enter it at `/#/d1-platform-admin`. The UI keeps the key in memory only. Never commit the value to `wrangler.toml`, GitHub, browser storage, or source code. The route returns HTTP 503 until the secret is configured.

## Verification

- [Owner-created store, demo POS and cashbook reconciliation](https://github.com/RlM100always/Thesis/actions/runs/40326438876)
- [Owner signup/login, product editing, inventory audit and logout/cleanup](https://github.com/RlM100always/Thesis/actions/runs/40325162409)
- [Guest order placement, cancellation and stock reversal](https://github.com/RlM100always/Thesis/actions/runs/40318406288)

GitHub frontend build and API live smoke workflows have passed. The Worker's code has been deployed directly through the Cloudflare API; GitHub commits alone do **not** automatically redeploy Worker script changes unless Cloudflare CI secrets / automatic deploy are configured. The last source-only change improving safe deletion after cashbook entries may not be in the last deployed Worker binary.

## Critical NOT YET migrated

The previous B-SMART operational business database is still separate: business login/memberships, original POS/cashflow, purchasing, live stock, receivables, accounting journals, invoicing, operational CRM/coupons/reviews/fulfilment, reporting, permissions, and historical business customers/orders remain in FastAPI. D1 customer identities are not synchronized with the legacy customer identity.

No real payment gateways, credential verification, merchant identity validation, email recovery, abuse protection (Turnstile/rate limits), full privacy compliance, DB restore plan or production backup automation have been completed. Do not collect live money or sensitive shopper data here.

**Temporary CI fixture:** The POS live test created `ci-pos-5b716399edab183e@example.invalid` with an isolated `shop-752c1d2b-b92` demo store and one simulated order. After the test, deletion through the connector was blocked by safety checks, so the fixture remains in D1. It is not a real merchant. Remove it only after checking its exact account/store IDs and dependencies in the Cloudflare dashboard; never run broad deletes against actual merchants.

## Architecture migration path

1. Preserve original database/backup or explicitly accept that unavailable historic data cannot be recreated.
2. Port legacy operational tables and transaction-safe order/stock flows into a D1-native repository/Worker/DO model **with regression and concurrency tests**, and owner-scoped membership authentication.
3. Add privacy-preserving verified merchant login, customer identity, chat, coupons, true accounting double-entry journals, payments and reporting.
4. Implement reliable backups to R2 and tested D1 point-in-time restore before any cutover.
5. Only after verification, switch legacy FastAPI owner modules to the new D1 backend and retire ephemeral SQLite without losing real records.
