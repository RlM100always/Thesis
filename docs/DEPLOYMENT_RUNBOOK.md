# Production Deployment Runbook

## Current deployment topology

- Frontend and legacy FastAPI application: Render service, public URL https://thesis-j0n8.onrender.com
- D1 commerce API: Cloudflare Worker `bsmart-commerce-api`
- Commerce database: existing Cloudflare D1 database `bsmart-commerce`
- Frontend code: `frontend/`
- Worker code/configuration: `cloudflare/commerce-worker.js`, `cloudflare/*.js`, `cloudflare/wrangler.toml`
- GitHub Actions: `.github/workflows/storefront-check.yml`, `.github/workflows/cloudflare-worker-deploy.yml`, `.github/workflows/cloudflare-d1-live-smoke.yml`

## Before deployment

1. Confirm the target Render workspace and Cloudflare account.
2. Confirm the target Render service is the existing B-SMART service. Do not create a replacement service or database as a shortcut.
3. Inspect current service environment variable names without printing secret values.
4. Verify the GitHub repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are configured.
5. Verify the Worker secret `PLATFORM_ADMIN_KEY` exists. Do not read or print its value.
6. For owner verification and password recovery, configure Worker secret `RESEND_API_KEY`, verified sender variable `AUTH_EMAIL_FROM`, and `PUBLIC_APP_URL=https://thesis-j0n8.onrender.com`.
7. For AI inference, confirm the Workers AI model budget and only then set Worker variable `AI_ENABLED=true`. The default is disabled; deterministic data-grounded responses remain available without model calls.
8. Take a D1 backup/export and verify it can be read before applying any migration.
9. Confirm the selected branch and commit have passing CI.

## Build and test

Frontend:
```bash
cd frontend
npm ci
npm run lint
npm test
npm run build
```

Backend:
```bash
python -m pip install -r requirements.render.txt
python -m compileall -q api
python -m pytest -q
```

Worker:
```bash
node --check --input-type=module < cloudflare/commerce-worker.js
node --check --input-type=module < cloudflare/customer-routes.js
node --check --input-type=module < cloudflare/merchant-routes.js
node --check --input-type=module < cloudflare/platform-admin-routes.js
```

## Deployment order

1. Merge only a reviewed, CI-passing change to the deployment branch.
2. Render auto-deploys from `main` when its service is configured for that branch.
3. Cloudflare Worker deploy runs from GitHub Actions only when its required repository secrets are configured; otherwise the workflow explicitly skips deployment.
4. Wait for each platform to report a successful deployment.
5. Run read-only checks against Render `/health`, Render `/health/ready`, Worker `/health`, merchant auth health and the public store directory.
6. Test writes only against an isolated staging database or isolated test store. Do not create CI merchants, orders, POS sales or cashbook rows in the production D1 database.
7. Verify the public storefront, owner sign-in, customer account, order lifecycle and admin console.
8. Record commit SHA, deployment IDs, test evidence and rollback point.

## Database safety

- Keep the existing D1 database ID and `DB` binding.
- Never run historical migrations blindly against the live database. The earlier migrations were manually applied and may not be registered in Wrangler's migration ledger.
- For owner email security, inspect the live `merchant_accounts` columns and `commerce_meta.schema_version`; only apply migration 0009 if those columns are absent. For assistants/reorder alerts, verify `commerce_products.reorder_level` and `commerce_ai_rate_limits` before applying migration 0010. The currently recorded live version is 8, and both migrations are branch-only until approved.
- Apply only reviewed additive SQL that is confirmed missing from the live schema.
- Never switch SQLAlchemy to a D1 database ID. D1 is accessed through the Worker binding.
- Do not delete or reset existing stores, customers, orders, inventory, cashbook or audit records to make a test pass.

## Rollback

1. Stop further deployments.
2. Revert the application code to the last known-good commit.
3. If a schema migration was applied, use the verified backup/restore procedure and a reviewed rollback plan. Do not assume a code rollback reverses D1 schema/data changes.
4. Re-run readiness and read-only integrity checks.
5. Document the incident and the affected data boundary.

## Owner email provider setup

The owner registration and password-recovery branch uses Resend for outbound email. Before enabling it:

1. Verify the sender domain in Resend.
2. Add `RESEND_API_KEY` as a Cloudflare Worker secret. Never store it in `wrangler.toml` or GitHub source.
3. Set `AUTH_EMAIL_FROM` to the exact verified sender identity.
4. Set `PUBLIC_APP_URL` to the production Render URL.
5. Apply the additive migration `cloudflare/migrations/0009_owner_email_security.sql` only after backing up D1 and confirming the columns are not already present.
6. Test owner registration, verification link expiry, resend, password reset, token reuse rejection and session revocation in staging.

The branch fails closed when the mail provider is not configured: it does not create a new owner account without sending a verification email. Do not publish temporary passwords or reset links in README files.
