# B-SMART — Step-by-step production delivery plan

**Project:** B-SMART multi-store commerce and business-management platform  
**Production website:** https://thesis-j0n8.onrender.com  
**Primary commerce database:** Cloudflare D1 `bsmart-commerce`  
**API:** Cloudflare Worker `bsmart-commerce-api`  
**Hosting:** Existing Render service `thesis`  
**Repository:** https://github.com/RlM100always/Thesis  
**Baseline verified:** 8 November 2026

This plan is the active delivery checklist. A feature is not called complete merely because code exists: its UI, API, database persistence, tenant isolation, tests and production deployment must all be verified.

## 1. Current production baseline

### Confirmed infrastructure
- Render service `thesis` deploys the React website and legacy FastAPI application from `main`.
- Cloudflare Worker `bsmart-commerce-api` is deployed and its `DB` binding points to the existing D1 database `bsmart-commerce`.
- D1 schema version is **12**. Migrations 0009–0012 have been applied.
- Render's latest confirmed application deployment is commit `a81b998ac7f267d2217a37d33aedd083d23a13be`.
- GitHub Actions production storefront checks and D1 read-only smoke checks passed for that commit.
- The latest D1 smoke test confirms CORS, D1 health, authentication health, public-store visibility, diagnostics and unauthenticated owner-assistant rejection.

### Existing D1 data — preserve it
The live database contains 11 store rows (10 seeded sample stores and one retained CI/POS fixture), 260 products, 3 test orders, 3 order lines, 3 inventory movements, 1 cashbook receipt and 1 legacy CI merchant account. All 11 stores remain inactive and marked as sample/demo data. There are currently **zero verified active real merchant stores** and no verified real owner accounts. Public discovery correctly returns zero stores and zero products. Do not activate sample stores or represent test records as real business activity.

### Important database boundary
The D1 commerce platform and legacy FastAPI business application are still separate systems. D1 is authoritative for the D1 storefront/customer/merchant/order workflows. The legacy FastAPI POS, accounting, procurement, CRM, workforce and other operational modules still use a separate SQLAlchemy database; the last recorded Render runtime used ephemeral SQLite. The repository contains no verified `bsmart.db` backup. Do not point SQLAlchemy at a D1 database ID, do not switch to the unused Render Postgres resource without a verified data audit, and do not claim the legacy modules have been migrated. Full migration requires the actual source database or an explicitly approved clean-start decision.

## 2. Feature-by-feature status

| Workstream | Existing foundation | Remaining work / release gate |
|---|---|---|
| Store design | Responsive React storefront, store themes, product cards/details, search, category/tag filters, price/name sorting, incremental “load more” | Complete mobile/desktop UX and accessibility review; optimise images/performance; improve facets, empty/error states and test real owner-created stores |
| Owner panel | Separate D1 owner registration/login, dashboard, store draft, product/stock management, orders, returns, customer inbox, POS/cashbook and coupons | Resend sender is not configured; verify email/password reset end-to-end; add owner/staff role matrix and full settings; test all CRUD after re-login |
| Customer assistant | Store-scoped assistant uses catalogue and signed-in customer's own order context; fallback answers are available | Improve recommendation ranking, test prompt injection and accuracy, add human-support handoff and monitored rate limits |
| Owner assistant | D1 tenant-scoped assistant for selected sales, stock, order, COD and product questions; owner dashboard has assistant UI | Expand supported intents, reconcile metrics against D1 queries, add evaluated AI narration only after budget approval |
| Business AI | Live D1 metrics, top-product and low-stock query foundations; reorder levels exist | Add date-range sales trends, customer cohorts/insights, inventory forecast, exports and calculation tests |
| E-commerce | Store catalogue, guest/account cart paths, checkout, COD/manual fulfilment, order lifecycle, server-side customer cart, coupons with checkout revalidation and usage limits | End-to-end cart/checkout tests on approved merchant store; delivery fee/rules and notifications; idempotency and concurrency tests; payment gateway only after provider/webhook approval |
| Inventory | D1 stock quantity, stock movements, owner stock adjustments, reorder thresholds and low-stock indicators | Verify every stock mutation and rollback; add alert delivery, reconciliation, receiving/purchasing and race-condition tests |
| Customer | Customer registration/login, profile, addresses, account order history, wishlist, product reviews, returns and store messaging | Customer email verification/password recovery, privacy export/deletion, support escalation and complete account lifecycle tests |
| Security | PBKDF2-HMAC-SHA-256 password hashes (100,000 iterations), hashed bearer sessions, owner route scoping, rate controls, email verification/reset code, platform-admin secret | Resend currently not configured (live health check: false); staff roles not implemented; improve abuse controls, session management, security headers, secret rotation and restore drill |
| Admin | Platform-admin overview, store/owner/customer/order/return/audit views, owner activation/suspension and store approval controls | Add least-privilege admin roles, owner identity review, safe exports, monitoring and auditable bulk actions |
| Deployment | Render auto-deploy from main; Cloudflare Worker deployment via GitHub Actions; production D1 smoke workflow | Keep CI green, verify each deployment ID and run post-deploy checks; create staging D1 for write tests |
| Documentation | Deployment runbook, D1 migration map, store access register and onboarding/recovery notes | Keep status aligned with live settings; add per-store login rows only for verified stores; document operator, owner and recovery procedures |

## 3. Delivery sequence

### Step 0 — Baseline and data protection — VERIFIED
- [x] Confirm Render workspace/service and Cloudflare Primary account/database.
- [x] Inspect current repository, deployment workflows and D1 schema.
- [x] Export D1 before migrations and apply only missing additive migrations 0009–0012.
- [x] Verify existing D1 record counts and preserve all existing records.
- [x] Deploy Worker and Render application updates.
- [x] Pass frontend build, backend compile/integration and production D1 read-only smoke tests.
- [x] Confirm public directory does not expose inactive sample/CI stores.

### Step 1 — Storefront quality and catalogue journey — IN PROGRESS
- [ ] Test store home, product detail, search, categories/tags, sort and incremental loading on mobile and desktop.
- [ ] Test no-results, API-down, empty catalogue, unavailable store and out-of-stock states.
- [ ] Verify price, stock, image, variant and wishlist display against D1/API responses.
- [ ] Add automated UI/API regression tests for filtering, sorting, cart and product detail.
- [ ] Confirm each real merchant-created store receives its own public slug and URL.

**Acceptance:** all storefront interactions work with actual API data and do not expose inactive sample stores.

### Step 2 — Owner identity and separate dashboard
- [x] D1 owner account/password authentication and private store drafts.
- [x] Email verification and password-reset endpoints/UI code deployed.
- [x] Password hashes and hashed session tokens.
- [x] Owner dashboard for catalogue, stock, orders, returns, messages, POS/cashbook and coupons.
- [ ] Configure Resend secret `RESEND_API_KEY` and verified `AUTH_EMAIL_FROM` sender.
- [ ] Test registration → email verification → login → forgot password → reset → old-session revocation.
- [ ] Add staff accounts/roles and permission matrix (current D1 schema only permits the `owner` role).
- [ ] Test cross-store access denial for every owner endpoint.

**Acceptance:** only verified account holders can access their own store; no owner can read another store's records.

### Step 3 — Customer shopping assistant and owner assistant
- [x] Storefront customer assistant endpoint and UI.
- [x] Owner assistant endpoint and UI with tenant-scoped D1 queries.
- [x] Workers AI binding deployed; inference remains disabled by default.
- [ ] Add recommendation ranking from category/brand/price/availability and explain why a product is suggested.
- [ ] Add order lookup only for the authenticated customer's own orders.
- [ ] Add human support handoff and clear escalation state.
- [ ] Evaluate hallucination, prompt injection, privacy and cross-tenant leakage.
- [ ] Enable AI model calls only after selecting a model, reviewing current pricing and setting a budget.

**Acceptance:** prices, stock, orders and business metrics must come from authoritative database queries; model failure must not break shopping or owner operations.

### Step 4 — Business intelligence
- [ ] Sales totals and trends by day/week/month with clear order-value vs collected-cash distinction.
- [ ] Top products, category mix and repeat-customer insights.
- [ ] Low-stock alerts based on each product's reorder level.
- [ ] Customer insights with consent and privacy safeguards.
- [ ] Exportable reports and reconciliation tests against source rows.

### Step 5 — E-commerce and inventory hardening
- [x] Store-specific coupons, checkout revalidation and atomic usage-limit triggers.
- [x] Stock and order workflow foundations.
- [ ] Test cart persistence across sign-in and devices.
- [ ] Test coupon expiry, limits, minimum order, concurrent redemption and cancelled orders.
- [ ] Test duplicate checkout requests, stock races, cancellation and returns.
- [ ] Add shipping rules/fees and transactional notifications.
- [ ] Add real payment gateway only after merchant credentials, verified webhooks, refunds and reconciliation are supplied and tested.

### Step 6 — Customer account and support
- [x] Customer accounts, profile, addresses, order history, wishlist, reviews, returns and store messaging.
- [ ] Complete customer recovery and verified contact flow.
- [ ] Test data export/deletion and retention rules.
- [ ] Verify customer support threads cannot cross store/customer boundaries.

### Step 7 — Central admin
- [x] Admin views for stores, owners, orders, customers, returns and audit history.
- [x] Store activation/approval and owner suspension/session revocation.
- [ ] Add admin role separation and re-authentication for sensitive actions.
- [ ] Add owner identity/document review workflow and approval evidence.
- [ ] Test every admin action and immutable audit trail.

### Step 8 — Legacy operational migration to Cloudflare Primary
- [ ] Obtain and verify the actual legacy source database backup (the repository has no `bsmart.db` file).
- [ ] Inventory all SQLAlchemy models, tables, row counts, foreign keys, tenant ownership and balances.
- [ ] Design D1-native tables and Worker APIs; do not treat D1 as a direct SQLAlchemy connection string.
- [ ] Migrate one bounded module at a time: identity/tenant → products/inventory → POS/sales → purchasing → finance → CRM/workforce → platform controls.
- [ ] Reconcile counts, stock, receivables, cash, journals and audit history.
- [ ] Run tenant-isolation, concurrency, rollback and restore tests before switching each frontend route.
- [ ] Retire ephemeral SQLite only after verified cutover and backup.

**Acceptance:** no data loss, no double-writing and one authoritative writer per business event.

### Step 9 — Production release
- [ ] Maintain green CI and confirmed Render/Cloudflare deployments.
- [ ] Run staging write tests and production read-only smoke tests.
- [ ] Verify D1 backup can be restored in an isolated recovery environment.
- [ ] Configure email delivery, monitoring, alerts, rate limits and operational support.
- [ ] Only then onboard verified real businesses and enable live trading/payment features.

## 4. Required production configuration

- Cloudflare Worker secret: `PLATFORM_ADMIN_KEY` (already present; never read into logs or source).
- Email: secret `RESEND_API_KEY`; variable `AUTH_EMAIL_FROM` set to a verified sender; `PUBLIC_APP_URL=https://thesis-j0n8.onrender.com`.
- AI: Worker AI binding exists; `AI_ENABLED` is intentionally not enabled. Set it only after model/budget review.
- GitHub Actions: Cloudflare deployment credentials remain in repository secrets; do not print their values.
- D1: preserve existing database ID `887fa347-9c22-46b1-a7cf-91a7dbdfc311`.

## 5. Definition of done

A feature is complete only when:
1. UI works on mobile and desktop.
2. API validates input and returns useful errors.
3. Data persists in the correct Cloudflare D1 tenant/store.
4. Success, failure, concurrency and permission tests pass.
5. Existing data is preserved and backup/recovery is documented.
6. CI passes.
7. Render and Worker deployment are confirmed.
8. Production smoke checks pass.
9. Documentation reflects the actual deployed state.

No sample store, test order, simulated payment or unverified account may be described as a real business record.
