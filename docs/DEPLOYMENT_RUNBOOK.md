# B-SMART Production Deployment Runbook

## Confirmed production topology — 8 November 2026

- Render workspace: existing user-confirmed workspace.
- Render service: `thesis`, Singapore, URL https://thesis-j0n8.onrender.com, deploy branch `main`.
- Cloudflare account: user-confirmed Cloudflare Primary account.
- Cloudflare Worker: `bsmart-commerce-api`, URL https://bsmart-commerce-api.bcs-written-rakib.workers.dev.
- Cloudflare D1 database: `bsmart-commerce`, ID `887fa347-9c22-46b1-a7cf-91a7dbdfc311`.
- D1 schema version: **13** (migrations 0009–0013 applied).
- Frontend/legacy FastAPI source: `frontend/` and `api/`.
- Worker source/config: `cloudflare/commerce-worker.js`, `cloudflare/*.js`, `cloudflare/wrangler.toml`.

## Latest verified deployment

- Render deployment for application commit `a81b998ac7f267d2217a37d33aedd083d23a13be`: live.
- GitHub storefront recovery/build workflow: [run 42444053016](https://github.com/RlM100always/Thesis/actions/runs/42444053016) — success.
- Cloudflare D1 read-only smoke: [run 42444052960](https://github.com/RlM100always/Thesis/actions/runs/42444052960) — success.
- The smoke checks validate D1 health, owner auth health, CORS, public-store visibility, diagnostics, inactive sample-store 404 and unauthenticated owner-assistant rejection.
- A fresh D1 export completed immediately before migration 0013 (schema-12 snapshot); bookmark: `00000057-00000000-0000511d-8fc19d9c4140d189405c4fbac8e5fc48`. The SQL export is stored in Cloudflare's temporary export storage; a full restore drill is still required.

## Before deployment

1. Confirm the target Render service is the existing B-SMART service; never create a replacement service/database as a shortcut.
2. Inspect Render environment variable names only; do not print secret values.
3. Confirm GitHub repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` exist.
4. Confirm Cloudflare Worker secret `PLATFORM_ADMIN_KEY` exists; never read or print its value.
5. For owner and customer email verification/reset, configure Worker secret `RESEND_API_KEY`, verified sender variable `AUTH_EMAIL_FROM`, and `PUBLIC_APP_URL=https://thesis-j0n8.onrender.com`. Email delivery is currently not configured; password recovery endpoints fail closed until setup is complete.
6. Workers AI binding exists, but inference is disabled by default. Review model, pricing and budget before enabling `AI_ENABLED=true`.
7. Back up D1 and verify export/restore procedure before every schema/data migration.
8. Confirm selected branch and commit have passing CI.

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
node --check --input-type=module < cloudflare/assistant-routes.js
node --check --input-type=module < cloudflare/platform-admin-routes.js
```

## Deployment order

1. Commit changes to a working branch and open a PR.
2. Require frontend, backend and D1 schema smoke tests to pass.
3. Merge reviewed code into `main`.
4. Render auto-deploys from `main`.
5. Cloudflare Worker deploy runs through GitHub Actions when the Cloudflare repository secrets are configured.
6. Confirm both platforms report a successful deployment.
7. Run production read-only checks.
8. Run writes only against an isolated staging D1 database or dedicated test store. Never create CI merchants/orders/POS/cashbook records in production.
9. Record commit SHA, deployment IDs, smoke-test run and rollback point.

## Database safety and migration rules

- Keep the existing D1 database ID and Worker `DB` binding.
- Live D1 schema version is **13**; migrations 0009–0013 have been applied.
- A fresh export was completed immediately before migration 0013; it has not yet been restored into a separate recovery database. Do not claim a tested restore.
- Historical migrations were applied manually and may not be registered in Wrangler's `d1_migrations` ledger. Never blindly run `wrangler d1 migrations apply --remote`.
- Before future migration: export/backup, inspect live schema, compare with migration, apply only missing reviewed additive SQL, verify columns/indexes/triggers and record counts.
- Never point SQLAlchemy `DATABASE_URL` at a D1 database ID. D1 access is through a Worker binding and D1-native queries/batches.
- Do not delete, reset, rename or reseed existing stores, customers, orders, stock, cashbook or audit records to make tests pass.
- The legacy FastAPI database is separate and was last recorded as ephemeral SQLite on Render. No verified `bsmart.db` backup exists in the current repository. Full operational migration is blocked until the source database/backup is located or the owner explicitly approves a clean-start policy.

## Rollback

1. Stop further deployments.
2. Revert application code to the last known-good commit.
3. Schema rollback is not the same as code rollback. Use a verified D1 backup/restore in an isolated recovery process; never run guessed reverse SQL.
4. Re-run health/read-only integrity checks.
5. Document incident, affected module, source-of-truth and recovery outcome.

## Owner email provider setup

1. Verify sender domain in Resend.
2. Add `RESEND_API_KEY` as a Cloudflare Worker secret.
3. Set `AUTH_EMAIL_FROM` to the exact verified sender identity.
4. Set `PUBLIC_APP_URL` to the production Render URL.
5. Confirm migrations 0009–0013 columns/tables exist (already included in schema version 13).
6. Test registration, verification, expired/reused token rejection, resend, password reset and old-session revocation in staging.
7. Re-run the owner auth health check; it must report both email settings as configured before opening registration.

## Store onboarding

- Owner registration is not ready for public onboarding until email provider setup and end-to-end verification tests pass.
- A verified owner creates a private store draft.
- Platform Admin reviews the business and approves activation.
- Only real, approved merchant stores can be listed publicly and use COD/manual fulfilment.
- Record store name, public URL, owner login URL, owner email, role and approval status in `STORE_ACCESS_REGISTER.md`. Never record passwords or tokens.
