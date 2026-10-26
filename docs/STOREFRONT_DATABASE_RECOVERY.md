# Operational online stores — data recovery boundary

> **Verified 26 Oct 2026 — Cloudflare architecture correction:** The user
> established Cloudflare as the intended primary storage provider. The Primary
> Cloudflare account has R2 bucket `bsmart-thesis-research` with one setup
> metadata object, and no B-SMART D1 database. Operational SQL rows currently
> reside in an ephemeral Render SQLite instance, **not R2**. A Render Postgres
> instance exists but is not used by this website. Do not migrate or seed
> until source-of-truth / backups are confirmed. Demo-bootstrap environment flag
> has been reset to `NO` while this is unresolved.
>
> Cloudflare-first relational primary would mean provisioning D1 and adapting
> the FastAPI SQLAlchemy code with a secure Worker/data-access layer. R2 alone
> cannot satisfy transactional product, order, and customer SQL queries.


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


## New safe demo catalogue bootstrap

The app now has `api/demo_catalog_bootstrap.py`: on startup, and **only** when
`BSMART_BOOTSTRAP_DEMO_CATALOG=YES` *and* `DATABASE_URL` points to PostgreSQL,
and the database has **zero stores, including inactive stores**, it may create
10 isolated and clearly labelled demo organizations (pharmacy, grocery, clothing,
restaurant, electronics, hardware, beauty, stationery, mobile, furniture) with
literal sample products from `seed_10_businesses.py`, positive **simulated** inventory,
active storefront rows and store-product listings.

It DOES NOT restore original merchant/shop/customer/order records, create real
orders, initiate payment, send communications or overwrite live businesses.
If any Store row exists, the seed is skipped. A single transaction rolls back
on error. Demo shops are marked in both the Store Directory and individual
storefront; never provide real contact/address/payment details.


## New read-only-first store reconciliation helper (26 October 2026)

Run `python scripts/reconcile_existing_stores.py` on a **trusted database copy**
to inventory all existing organizations, storefronts, active products and
published listings. It does not write anything by default.

After separately verifying the durable database and business owner approval,
select a single organization via `--organization-id UUID --apply`, adding
`--activate` or `--publish-new-products` only when that owner authorizes
publication. Existing deliberately unpublished products remain unpublished.
Pharmacy product bulk-publication is refused pending manual licensing review.
The script refuses writes to production or Render-hosted SQLite.

**Do not use this helper as a replacement for restoring old business data.**
It can only link rows that already exist in the selected operational database.

### Cloudflare-first architecture safety

Cloudflare R2 bucket `bsmart-thesis-research` exists but is research object
storage, not a relational store/order database. Cloudflare D1 would require a
new schema and migration plus a Worker-native transactional adapter for order
placement: the D1 REST SQLAlchemy dialect cannot preserve the existing
FastAPI Session transaction/rollback semantics across multiple HTTP SQL calls.
Do not cut over checkout, payments, inventory or customer sessions without an
end-to-end migration and concurrent-order tests.

The user's `thesis.zip` included `bsmart.db-wal` and `bsmart.db-shm`,
but not the necessary `bsmart.db` SQLite database file. The Cloudflare
R2 research bucket contained only `thesis/research/setup.json` at the time
of verification, not a complete operating database snapshot. Recreate only
a clearly labelled demo after separate consent, not a fake recovery of real
customer/order history.
