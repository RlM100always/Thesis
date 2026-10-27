# Cloudflare D1 — B-SMART demo commerce and merchant console

**Project reference:** Database **`bsmart-commerce`**, Worker **`bsmart-commerce-api`**, URL https://bsmart-commerce-api.bcs-written-rakib.workers.dev. The current Worker version was verified deployed on 2026-10-27; the Render frontend is https://thesis-j0n8.onrender.com.

Frontend site https://thesis-j0n8.onrender.com uses a dual adapter in `frontend/src/api.js`:

- Cloudflare D1 for `demo-bsmart-*` legacy demonstration stores and for newly created `merchant-*` owner-store IDs / `shop-*` slugs.
- Existing FastAPI for all prior business records, legacy auth and original operational modules. **These have NOT been migrated.** No login/identity synchronization exists between systems.

## D1 features implemented

- 10 labelled synthetic business demo stores plus 259 example products, and persistent D1 product/stock listing via Worker.
- Guest **demo-only** checkout plus explicitly admin-approved merchant-owned COD checkout. Order placement uses transactional D1 batch/stock checks; cancellation restores inventory once and records an inventory movement. Seeded demo stores cannot be promoted to operational checkout.
- Shared D1 customer accounts across demo stores: registration/login, profile/avatar, password change with session revocation, saved Bangladesh addresses, account-wide order history, server-side per-store carts, cross-store wishlist, verified-purchase reviews, support chat and return requests. Customer contact/address details are stored in D1; use synthetic/test data only.
- New owner onboarding and login via **one-time cryptographically random 256-bit owner access key**, stored as SHA-256 digest in D1; 12-hour hashed bearer sessions. PBKDF2 was unavailable in this particular Worker runtime, so password authentication is intentionally **not** used. Email is *unverified*. Owner access key must be saved; lost-key recovery not implemented. Avoid using this as a production identity system.
- Owner store creation (draft until explicitly made public), product publishing/editing, product descriptions/brands/tags/compare-at prices, stock adjustment logs, owner-scoped order status workflow, customer message inbox and return management.
- Staged customer-visible order tracking: placed → confirmed → processing → ready → dispatched → delivered. Legacy `fulfilled` and `shipped` statuses remain readable; each merchant transition stores a status note.
- COD payment state is persisted separately from fulfilment state. Merchant can mark COD as received only after `delivered`/legacy `fulfilled`; timestamp, merchant email and note are saved. Customer and platform-admin views distinguish demo orders, pending COD, collected COD and cancelled-without-payment. No online gateway or automatic refund is active.
- Platform admin may explicitly promote only merchant-owned stores to operational COD checkout after confirmation. Approved operational stores accept COD/manual fulfilment only; seeded demo stores remain demo-only, and online payment, courier and refund integrations are not enabled.
- Demo counter POS, recorded atomically with inventory and order rows in D1, and a small example **cashbook**. Not double-entry accounting or actual cash collection.
- React Owner Center at `/#/d1-owner` with mobile navigation, plus a secret-protected Platform Admin page at `/#/d1-platform-admin` for store moderation, order oversight and audit history.

## D1 schema

Source migrations extend through `migrations/0008_cod_payment_tracking.sql`. The live D1 database was queried after migration and reports `commerce_meta.schema_version=8`; payment status fields and both payment/inventory triggers are present.

**Do not blindly run `wrangler d1 migrations apply --remote` on this existing database.** Migrations were applied manually via Cloudflare API, not registered in Wrangler's `d1_migrations` table. One-time `ALTER TABLE` statements would fail if replayed. Before applying any future migration: take and verify a D1 backup/export, query the live schema and `commerce_meta`, apply only reviewed additive SQL that is missing, then re-query columns and triggers.


## Platform admin secret setup

Configure the Worker secret after the platform-admin code is deployed:

```sh
cd cloudflare
npx wrangler secret put PLATFORM_ADMIN_KEY
```

Use a long, unique random value of at least 32 characters. Enter it at `/#/d1-platform-admin`. The UI keeps the key in memory only. Never commit the value to `wrangler.toml`, GitHub, browser storage, or source code. **As checked on 2026-10-27, `PLATFORM_ADMIN_KEY` is not yet configured in the Worker; the admin route returns HTTP 503 until you add it.** Add it manually in Cloudflare Dashboard → Workers & Pages → `bsmart-commerce-api` → Settings → Variables and Secrets → Add secret, name `PLATFORM_ADMIN_KEY`, then deploy/save.

## Verification

- [Owner-created store, demo POS and cashbook reconciliation](https://github.com/RlM100always/Thesis/actions/runs/40326438876)
- [Owner signup/login, product editing, inventory audit and logout/cleanup](https://github.com/RlM100always/Thesis/actions/runs/40325162409)
- [Guest order placement, cancellation and stock reversal](https://github.com/RlM100always/Thesis/actions/runs/40318406288)

Latest GitHub CI passed on commit `6cc6986c0de53496a749ea9c09a554670239542d` (frontend build, D1 schema smoke, backend compile and backend integration). The corresponding Render deploy is live. The Worker was uploaded directly through the Cloudflare API at 2026-10-27 08:39 UTC; GitHub commits alone do **not** automatically redeploy Worker script changes unless Cloudflare CI secrets / automatic deploy are configured.

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
