# Cloudflare D1 — B-SMART commerce database and merchant console

**Project reference:** Database **`bsmart-commerce`**, Worker **`bsmart-commerce-api`**, URL https://bsmart-commerce-api.bcs-written-rakib.workers.dev. The production Worker and Render frontend were verified live on 2026-11-07; the Render frontend is https://thesis-j0n8.onrender.com.

Render hosts the web application at https://thesis-j0n8.onrender.com. **Cloudflare D1 is the database for the D1 storefront, customer, merchant, product, inventory and order workflows. No Render PostgreSQL database is required for those records.** The frontend uses a dual adapter in `frontend/src/api.js`:

- Cloudflare D1 for `demo-bsmart-*` legacy demonstration stores and for newly created `merchant-*` owner-store IDs / `shop-*` slugs.
- Existing FastAPI for all prior business records, legacy auth and original operational modules. **These have NOT been migrated.** No login/identity synchronization exists between systems.

## D1 features implemented

- 10 labelled synthetic business demo stores plus 259 example products, and persistent D1 product/stock listing via Worker.
- Guest **demo-only** checkout plus explicitly admin-approved merchant-owned COD checkout. Order placement uses transactional D1 batch/stock checks; cancellation restores inventory once and records an inventory movement. Seeded demo stores cannot be promoted to operational checkout.
- Shared D1 customer accounts across demo stores: registration/login, profile/avatar, password change with session revocation, saved Bangladesh addresses, account-wide order history, server-side per-store carts, cross-store wishlist, verified-purchase reviews, support chat and return requests. Customer contact/address details are stored in D1; use synthetic/test data only.
- New merchant-owner registration uses PBKDF2-HMAC-SHA-256 password hashes (100,000 iterations), random per-account salts and 12-hour hashed bearer sessions. Existing one-time access-key accounts remain compatible. Owner email verification and password recovery have now been implemented in the upgrade branch, but are not live until migration 0009 is safely applied and the Worker is configured with a Resend API key and verified sender address. Migration 0010 adds per-product reorder thresholds and privacy-preserving assistant rate-limit storage.
- Owner store creation creates a real, private draft (`is_demo=0`, `is_active=0`). Owners can manage products and stock, but cannot publish their own store; Platform Admin approval is required. Product descriptions/brands/tags/compare-at prices, stock adjustment logs, owner-scoped order status workflow, customer message inbox and return management are stored in D1.
- Staged customer-visible order tracking: placed → confirmed → processing → ready → dispatched → delivered. Legacy `fulfilled` and `shipped` statuses remain readable; each merchant transition stores a status note.
- COD payment state is persisted separately from fulfilment state. Merchant can mark COD as received only after `delivered`/legacy `fulfilled`; timestamp, merchant email and note are saved. Customer and platform-admin views distinguish demo orders, pending COD, collected COD and cancelled-without-payment. No online gateway or automatic refund is active.
- Platform admin may explicitly promote only merchant-owned stores to operational COD checkout after confirmation. Approved operational stores accept COD/manual fulfilment only; seeded demo stores remain demo-only, and online payment, courier and refund integrations are not enabled.
- Demo-store POS remains simulated. Approved merchant stores can record real cash POS sales, payment collection and inventory movement in one D1 batch. The cashbook records receipts/expenses but is not a double-entry accounting ledger.
- React Owner Center at `/#/d1-owner` with mobile navigation, plus a secret-protected Platform Admin page at `/#/d1-platform-admin` for store moderation, order oversight and audit history.

## Live D1 data audit (7 November 2026)

The existing database was queried read-only. Its 22 application tables report `commerce_meta.schema_version=8`.

- 10 fictional seeded demo stores and 259 sample products.
- One retained POS CI fixture (`shop-752c1d2b-b92`) with one test product.
- Three demo/test orders, three order lines, three inventory movements and one test cashbook receipt.
- One legacy CI merchant account; zero customer accounts and zero real merchant-owned operational stores.
- All 11 store rows are still marked `is_demo=1`.
- Orphan-reference, order-total, payment-state and negative-stock checks returned zero exceptions.

The CI fixture is retained in D1 for audit/reconciliation. The current alignment change hides it from public store discovery and customer account routes; it does not delete or rewrite its records. Seeded demo stores remain visible and demo-only.

The Cloudflare account also contains a separate D1 database named `bcs-written` for study-content records. It is not the B-SMART commerce database and must not be used as a replacement or merged into `bsmart-commerce`.

## D1 schema

Live D1 currently reports `commerce_meta.schema_version=8`. The upgrade branch adds `migrations/0009_owner_email_security.sql` and `migrations/0010_assistant_and_reorder_levels.sql`; neither migration is applied to production yet. The live database must be backed up and its schema rechecked before the additive 0009/0010 statements are applied. Payment status fields and both payment/inventory triggers are present in the current live schema.

**Do not blindly run `wrangler d1 migrations apply --remote` on this existing database.** Migrations were applied manually via Cloudflare API, not registered in Wrangler's `d1_migrations` table. One-time `ALTER TABLE` statements would fail if replayed. Before applying any future migration: take and verify a D1 backup/export, query the live schema and `commerce_meta`, apply only reviewed additive SQL that is missing, then re-query columns and triggers.


## Platform admin secret setup

Configure the Worker secret after the platform-admin code is deployed:

```sh
cd cloudflare
npx wrangler secret put PLATFORM_ADMIN_KEY
```

Use a long, unique random value of at least 32 characters. Enter it at `/#/d1-platform-admin`. The UI keeps the key in memory only. Never commit the value to `wrangler.toml`, GitHub, browser storage, or source code. **`PLATFORM_ADMIN_KEY` was configured as a Cloudflare Worker secret on 2026-11-07.** Its value is intentionally not stored in GitHub, Wrangler config or this document. The owner received the generated key in the connected ChatGPT conversation and should save it in a password manager. The D1 Platform Admin page keeps the key in memory only. To rotate it, replace the Worker secret and use the new value at `/#/d1-platform-admin`.

## Verification

- [Owner-created store, demo POS and cashbook reconciliation](https://github.com/RlM100always/Thesis/actions/runs/40326438876)
- [Owner signup/login, product editing, inventory audit and logout/cleanup](https://github.com/RlM100always/Thesis/actions/runs/40325162409)
- [Guest order placement, cancellation and stock reversal](https://github.com/RlM100always/Thesis/actions/runs/40318406288)

The Render service auto-deploys from `main`. A dedicated Cloudflare Worker deployment workflow now exists at `.github/workflows/cloudflare-worker-deploy.yml`; configure GitHub repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` to enable automatic Worker deploys when `cloudflare/**` changes. Until those secrets are configured, merge to GitHub does not deploy Worker code automatically; the Worker must be deployed through Cloudflare separately.

## Database boundary — important

- Render is the application host; it is not the commerce database.
- Cloudflare D1 (`bsmart-commerce`) is authoritative for the D1 storefront and merchant-commerce routes.
- The older FastAPI operational modules (78 operational model tables, 36 platform-control model tables and 54 registered routers) still use their separate SQLAlchemy database. The latest Render startup log reports ephemeral SQLite with 1 organization, 0 stores, 4 catalogue products and 0 listed store products. They have **not** been migrated to D1 and must not be described as D1-backed. The Render Postgres resource exists but is not connected to the running service; do not use it as an assumed source of truth.
- Do not create or pay for a Render PostgreSQL database for the D1 commerce store. A future D1 cutover of the legacy modules needs a separate reviewed migration and regression plan.

## Critical NOT YET migrated

The previous B-SMART operational business database is still separate: business login/memberships, original POS/cashflow, purchasing, live stock, receivables, accounting journals, invoicing, operational CRM/coupons/reviews/fulfilment, reporting, permissions, and historical business customers/orders remain in FastAPI. D1 customer identities are not synchronized with the legacy customer identity.

No real payment gateways, merchant identity validation, full abuse protection (Turnstile/rate limits), full privacy compliance, tested DB restore plan or production backup automation have been completed. Owner email verification and password reset are branch-only until migration 0009 and mail-provider configuration are deployed. The customer/owner assistant code and reorder thresholds are branch-only until migration 0010 is applied. Do not collect live money or sensitive shopper data here.

**Temporary CI fixture:** The POS live test created `ci-pos-5b716399edab183e@example.invalid` with an isolated `shop-752c1d2b-b92` demo store and one simulated order. After the test, deletion through the connector was blocked by safety checks, so the fixture remains in D1. It is not a real merchant. Remove it only after checking its exact account/store IDs and dependencies in the Cloudflare dashboard; never run broad deletes against actual merchants.

## Architecture migration path

1. Preserve original database/backup or explicitly accept that unavailable historic data cannot be recreated.
2. Port legacy operational tables and transaction-safe order/stock flows into a D1-native repository/Worker/DO model **with regression and concurrency tests**, and owner-scoped membership authentication.
3. Add privacy-preserving verified merchant login, customer identity, chat, coupons, true accounting double-entry journals, payments and reporting.
4. Implement reliable backups to R2 and tested D1 point-in-time restore before any cutover.
5. Only after verification, switch legacy FastAPI owner modules to the new D1 backend and retire ephemeral SQLite without losing real records.


## Owner email verification and password recovery (upgrade branch)

The branch `production/business-platform-upgrade` adds single-use, hashed owner verification and password-reset tokens. Verification links expire after 24 hours; password-reset links expire after 60 minutes. Password reset revokes all existing owner sessions. Email delivery uses the Resend API and must fail closed if configuration is absent.

Configure these Worker values before enabling new owner registration:
- Secret `RESEND_API_KEY` — Resend API key (Cloudflare Worker secret).
- Variable `AUTH_EMAIL_FROM` — sender identity on a domain verified with Resend.
- Variable `PUBLIC_APP_URL` — `https://thesis-j0n8.onrender.com` (optional; the code has this safe fallback).

The new registration endpoint returns a configuration error until the provider is configured; it does not create an unverified owner account when email delivery is unavailable. Do not put the Resend key or sender credentials in GitHub source files.


## Store assistants and reorder alerts (upgrade branch)

The upgrade branch adds:
- A public D1 storefront assistant at `POST /api/public/assistant/{store-slug}`. It uses the current store's published catalogue and, only when a customer bearer session is supplied, that customer's orders in the same store.
- An authenticated owner assistant at `POST /api/merchant/assistant`. It queries only the signed-in owner's store and reports order value separately from COD money actually collected.
- Per-product `reorder_level` (default 5) and low-stock analysis.
- Hashed per-minute rate-limit keys; raw customer IPs and chat transcripts are not stored by this feature.

The Worker has a Workers AI binding configured for `@cf/zai-org/glm-4.7-flash`, but inference is deliberately **disabled by default**. It requires the Worker variable `AI_ENABLED=true`. Until enabled, the assistants use deterministic, database-grounded fallback responses; checkout and store operations do not depend on AI. Customer assistant UI is currently mounted on D1 storefronts only; the legacy FastAPI storefront integration remains a separate migration task.

Cloudflare's current model page lists GLM-4.7-Flash as multilingual and shows unit pricing of $0.0605 per million input tokens and $0.40 per million output tokens. Recheck the current model pricing before enabling inference: https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/
