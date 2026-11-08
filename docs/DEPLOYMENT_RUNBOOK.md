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

## Latest verified deployment — 8 November 2026

- Render deployment for application commit `a81b998ac7f267d2217a37d33aedd083d23a13be` was recorded as live in the previous deployment audit; Render was not revalidated during this audit.
- Latest storefront recovery/build workflow: [run 42463053524](https://github.com/RlM100always/Thesis/actions/runs/42463053524) — all four jobs passed.
- Latest Cloudflare D1 read-only smoke: [run 42463053531](https://github.com/RlM100always/Thesis/actions/runs/42463053531) — passed.
- Latest Cloudflare Worker code deployment: direct content-only upload from GitHub `main` at `2026-11-08T08:44:30.644445Z`; Worker version `9ce95b0e-5d5e-496d-a1e9-0e6c848ba1b7`, deployment `3512e387-8a43-43b6-9596-e09d0f4957f0`, active at 100%.
- The content-only upload updated the seven Worker modules without replacing configuration. Post-deploy inspection confirmed the existing D1 binding, Workers AI binding and `PLATFORM_ADMIN_KEY` secret binding remained present.
- **Automated deployment is still misconfigured:** [workflow run 42463053554](https://github.com/RlM100always/Thesis/actions/runs/42463053554) concluded `success`, but its `Deploy Worker` step was skipped because `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` were empty. The direct upload above is a separate successful deployment; do not treat the skipped workflow as a deployment.
- A fresh full D1 schema-13 export completed on 8 November. Bookmark: `0000005a-00000000-0000511d-8401ba06e6b9525ec909bf7ed5a411e9`; file: `887fa347-9c22-46b1-a7cf-91a7dbdfc311-0000005a-00000000-0000511d-8401ba06e6b9525ec909bf7ed5a411e9.sql`. The export completed successfully, but a full restore drill is still required.
- The live D1 inventory query found 11 store rows (all inactive and not publicly listed), 260 products, 3 retained test orders, 0 customer accounts, 1 retained CI merchant account and 0 coupons. There are currently no active real merchant stores.

## Before deployment

1. Confirm the target Render service is the existing B-SMART service; never create a replacement service/database as a shortcut.
2. Inspect Render environment variable names only; do not print secret values.
3. **Currently blocked:** add GitHub Actions repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. The latest deployment workflow confirmed both values were empty and skipped its deploy step.
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
- A full schema-13 D1 export completed on 8 November 2026 (bookmark `0000005a-00000000-0000511d-8401ba06e6b9525ec909bf7ed5a411e9`; filename recorded above). It has not yet been restored into a separate recovery database. Do not claim a tested restore.
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
