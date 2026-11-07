# Production implementation plan

**Project:** B-SMART multi-store commerce and business management platform  
**Repository:** https://github.com/RlM100always/Thesis  
**Baseline audited:** 8 November 2026  
**Working branch:** `production/business-platform-upgrade`

This plan is the release checklist for the requested business-level upgrade. It separates existing working functionality from missing functionality. A feature is not marked complete until its backend, tenant isolation, UI, tests and production deployment have all been verified.

## 1. Verified baseline

The repository currently contains two separate business data systems:

1. **Cloudflare D1 commerce Worker** (`bsmart-commerce`): public store catalogue, D1 customer accounts, owner registration/login, merchant-owned draft stores, product/stock management, COD order workflow, customer wishlist/reviews/returns/messages, merchant inbox, POS/cashbook and a secret-protected platform-admin console.
2. **Legacy FastAPI application**: the wider business-management modules, including the existing owner-facing Business Assistant and POS, accounting, purchasing, CRM, workforce and reporting features. The frontend still uses the FastAPI path for these legacy modules.

They are not one integrated database today. The repository's own live-audit notes state that the latest legacy Render runtime used ephemeral SQLite, while D1 holds a separate commerce dataset. The D1 database currently contains 10 seeded sample stores and 259 sample products, plus a retained CI fixture; it has no verified real merchant-owned operational store. Existing D1 records must be preserved.

## 2. Requested feature delivery

| Workstream | Existing foundation | Remaining work before production sign-off |
|---|---|---|
| Premium storefront | Responsive storefront, store themes, catalogue, search and category/area filters | UX review on mobile/desktop, pagination/performance, image optimisation, product detail and empty/error states, accessibility |
| Owner panel | Separate D1 owner registration/login and dashboard; product, stock, order, POS, cashbook, returns and customer-message views | Verified email, password recovery, owner/staff roles, session controls, complete settings, audit coverage and end-to-end CRUD |
| Customer AI assistant | Product catalogue, order status, customer accounts and support messaging APIs | Grounded shopping assistant, product recommendations, safe order lookup, escalation to human support, rate limiting and privacy controls |
| Owner AI assistant | FastAPI Business Assistant answers selected real-data questions; optional Anthropic narration | Extend verified intents and analytics; add equivalent D1-owner assistant; ensure all answers are tenant-scoped and numbers are grounded in database results |
| Business intelligence | Existing FastAPI reports/insights; basic D1 owner metrics | Sales trends, top products, stock warnings, customer insights, date filters, export and tested calculations |
| E-commerce | D1 catalogue, checkout, stock checks, COD/manual fulfilment, customer accounts, wishlist, reviews, returns and order tracking | Server-persisted cart consistency, coupons/promotions, shipping rules, order notifications, idempotency and real payment integration only after provider approval |
| Inventory | D1 stock quantity, stock adjustments and order-related stock movement | Reorder thresholds, low-stock alerts, inventory reconciliation, purchase/receiving workflows and concurrency tests |
| Customer experience | Registration/login, profile, addresses, order history, wishlist, reviews, returns and store messaging | Password recovery, email verification, clearer support escalation, privacy/export/deletion workflow |
| Security | Password hashes, hashed bearer sessions, login throttling, tenant-scoped owner routes, platform-admin secret | Email verification, password reset, role matrix for D1, stronger abuse protection, security headers, secret rotation, audit review and backup/restore drill |
| Platform admin | Store approval/activation, order oversight, customer/return views and audit log | Least-privilege admin roles, owner verification queue, safer bulk operations, export and operational monitoring |
| Deployment | Render frontend/API and Cloudflare Worker exist; GitHub Actions workflows exist | Confirm correct Render workspace and Cloudflare account, verify required secrets, run CI, deploy Worker and Render, then run production smoke tests |
| Documentation | Root README and Cloudflare technical notes | Per-store access register, operator runbook, owner onboarding, recovery instructions and release evidence |

## 3. Delivery sequence and release gates

### Phase 0 — Baseline and safe working branch
- [x] Inspect repository architecture, routes, current database boundaries and deployment workflows.
- [x] Create the isolated working branch `production/business-platform-upgrade`.
- [x] Record verified gaps and access-documentation rules.
- [ ] Run the full current CI suite on the working branch and retain its results.

**Gate:** no production database writes or destructive migrations during the audit.

### Phase 1 — Identity, roles and owner access
- [x] Add branch-level owner email verification and single-use password-reset endpoints, hashed tokens, expiry checks and session revocation.
- [x] Add owner-panel verification, resend-verification, forgot-password and reset-password screens.
- [x] Add migration 0009 and automated schema/auth-flow tests (pending CI result).
- [ ] Configure Resend and apply migration 0009 safely to the existing D1 database.
- [ ] Decide the authoritative identity system for each store.
- [ ] Verify the email-provider delivery path end to end in staging and production.
- [ ] Add owner/staff roles and permissions with store-level tenant isolation.
- [ ] Add D1 owner/staff roles, session controls and security-event audit.
- [ ] Test cross-store access denial, lockout, reset-token expiry and account lifecycle.

**Gate:** a user from Store A must never read or change Store B data.

### Phase 2 — Storefront and commerce
- [ ] Review the full customer journey on mobile and desktop.
- [ ] Complete cart, checkout, coupon, delivery-fee and order confirmation flows.
- [ ] Make all stock changes atomic and idempotent.
- [ ] Test cancellation, return, stock restoration and order-state transitions.
- [ ] Keep COD clearly distinct from online payment; enable a gateway only after credentials, webhook verification and reconciliation tests are supplied.

**Gate:** catalogue, cart, checkout, order and stock totals reconcile in automated tests.

### Phase 3 — Owner operations and inventory
- [ ] Complete product, category, pricing, variant, stock and store-settings CRUD.
- [ ] Add reorder thresholds and low-stock notifications.
- [ ] Complete order, return, customer inbox, POS and cashbook workflows.
- [ ] Add audit records for privileged actions.
- [ ] Test every create/read/update/delete operation and role boundary.

**Gate:** every owner action persists to the correct store and is visible after re-login.

### Phase 4 — Customer and owner AI assistants
- [ ] Customer assistant: answer only from the current store's published catalogue, delivery rules and authorised order data.
- [ ] Owner assistant: answer from the signed-in owner's store metrics and operational data.
- [ ] Add product recommendations based on catalogue attributes and availability.
- [ ] Add explicit human-support handoff.
- [ ] Add prompt-injection protections, request limits, privacy minimisation and deterministic fallback.
- [ ] Verify that AI cannot expose another store's records or invent prices, stock, delivery promises or financial totals.

**Gate:** every numeric/business claim is grounded in a database query; AI failure must not break checkout or owner operations.

### Phase 5 — Analytics and platform administration
- [ ] Add sales, inventory and customer insight dashboards.
- [ ] Validate calculations against source orders and stock movements.
- [ ] Add store-owner approval and operational review queues.
- [ ] Harden platform-admin access and audit exports.

**Gate:** dashboard totals reconcile with source records and privileged actions are auditable.

### Phase 6 — Production deployment and recovery
- [ ] Confirm Render workspace and Cloudflare account before account-level changes.
- [ ] Confirm GitHub Actions secrets exist without printing their values.
- [ ] Back up D1 and verify the backup before every schema/data migration.
- [ ] Apply only reviewed additive migrations; do not blindly replay historical migrations.
- [ ] Deploy Worker and Render from the approved branch/commit.
- [ ] Run read-only production smoke tests, then isolated staging write tests.
- [ ] Test restore/recovery before enabling real customer traffic or payments.

**Gate:** production health, database readiness, CORS, authentication, storefront, owner dashboard and smoke tests all pass.

## 4. Deployment configuration required

The existing Worker deployment workflow expects these GitHub repository secrets:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

The Worker also uses the Cloudflare secret:
- `PLATFORM_ADMIN_KEY` (must remain in Worker secret storage; never commit it)

The legacy FastAPI production configuration requires a persistent database and secure environment variables. Do not point SQLAlchemy at a D1 database ID or assume an existing Render PostgreSQL resource is the active database. Confirm the live Render service's actual environment and database before changing it.

Owner email verification/password reset code is in the upgrade branch and requires the Worker secret `RESEND_API_KEY` plus the `AUTH_EMAIL_FROM` sender variable and migration 0009. AI narration needs a configured supported AI provider/binding. Neither provider should be represented as live until its configuration and end-to-end tests pass.

## 5. Credential and store-register policy

- Public README files may contain store names, public URLs, login URLs, account roles and account status.
- Public README files must **never** contain passwords, API tokens, reset tokens, private keys, payment secrets or platform-admin keys.
- Each owner should set a unique password and use the password-reset flow. Until recovery is implemented, do not publish or distribute temporary credentials in Git.
- Store credentials belong in a password manager or approved secret manager. The access register records only the location/reference, never the secret itself.
- Do not create fictional owner accounts or claim sample catalogue stores are real businesses.

See [Store Access Register](STORE_ACCESS_REGISTER.md) and [Deployment Runbook](DEPLOYMENT_RUNBOOK.md).

## 6. Definition of done

A workstream is complete only when:
1. UI works at mobile and desktop sizes.
2. API validates inputs and returns useful errors.
3. Database writes persist and are tenant-scoped.
4. Automated tests cover success, failure and permission boundaries.
5. Existing data is preserved and migration is reversible/recoverable.
6. CI passes.
7. Production deployment is confirmed and smoke tests pass.
8. Documentation reflects the actual deployed state.

No item should be marked complete based only on a screenshot, successful build, or code being present.
