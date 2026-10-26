# Operational online stores — data recovery boundary

The production web service is `thesis-j0n8.onrender.com`. It auto-deploys changes to GitHub `main`. The Render workspace contains a Postgres instance named `thesis-db` (Postgres 17, Singapore); existence alone does NOT mean `DATABASE_URL` is configured for the service. Render external IP allowlist is empty, so external diagnostic queries cannot be used.

## Store visibility

`GET /api/public/store/` returns only the active `stores` records. `GET /api/public/store/diagnostics` returns only active store count, listed product count and no sensitive rows. A store may have products in `products` but zero `store_products` listings, causing a blank product catalogue. The owner can activate and list them from their store panel.

On deployment startup, check Render Logs for `STORE_DIAGNOSTIC db_backend=...`. For a persistent Render PostgreSQL setup it must say `postgresql` (not `sqlite`), then show counts. Never paste connection strings, secrets or customer records into GitHub.

## Why stores can be empty

1. `DATABASE_URL` is unset; FastAPI silently defaults to ephemeral `sqlite:///./bsmart.db` in development settings.
2. Existing tenant owners have not created/activated storefronts.
3. Store exists, but public product listing is empty.
4. Existing real store records may have existed only in an older SQLite container. Those cannot be restored from the source ZIP alone.

## What was removed

`/sample-stores` and the two 32-shop simulated preview tables were removed. No operational Store/Organization/Customer/SalesDocument rows have been deleted; no seed has been executed.

## Safe data restoration

- Restore real business data from a known-good database backup if available.
- Use a **clearly labelled synthetic demo seed** only under a dedicated explicit flag, with an idempotent mode and isolated demo organization IDs, never by deleting/renaming real tenants.
- The old `seed_10_businesses.py` is a development-only high-volume generator, guarded to refuse Render/PostgreSQL. Do not remove those safeguards.
- After configuring persistence and any demo catalog, check `/api/public/store/`, `/api/public/store/diagnostics`, an individual `/api/public/store/slug/<slug>`, and a test COD checkout in a non-production sandbox.
