# B-SMART Cloudflare-first commerce slice

**Deployed and verified 26 October 2026**

| Resource | Cloudflare |
|---|---|
| D1 database | `bsmart-commerce` (APAC), id `887fa347-9c22-46b1-a7cf-91a7dbdfc311` |
| Worker | `bsmart-commerce-api` |
| Worker URL | `https://bsmart-commerce-api.bcs-written-rakib.workers.dev` |
| Main React site | `https://thesis-j0n8.onrender.com/#/stores` |
| Code | `cloudflare/commerce-worker.js`, `frontend/src/api.js` |
| Migrations | `cloudflare/migrations/0001_commerce.sql` + `0002_customer_inventory.sql` |
| Verification | GitHub Actions `B-SMART Cloudflare D1 Live Smoke` |

## Live functional scope

- **10 fictional, conspicuously labelled demo stores** spanning pharmacy, grocery, fashion, restaurant, electronics, hardware, beauty, stationery, mobile and furniture, currently with 259 published sample products. These are *not* the previously removed 32 synthetic research shops and not recovered real tenant records.
- Persistent D1 public store directory, product catalogue, example prices, available demo inventory.
- Guest demonstration order checkout (**no actual payment or delivery**): inventory is checked in D1, prices are read from D1, order header and lines are written atomically via D1.batch; SQLite triggers enforce stock/price, decrement stock and log stock movements.
- Anonymized demo customer reference is created for each order. Real names, phones and shipping addresses entered into the demonstration are **discarded**, not saved.
- Order token-based status lookup and cancellation. On cancellation, an SQL trigger returns units to stock and logs reversal movement.
- Frontend routes the demo org IDs (`demo-bsmart-*`) to Cloudflare while preserving existing FastAPI operational-store routes. Thus no old merchant storefronts, customer accounts, orders or payments are overwritten in the Render SQLite app.
- Secure versioning: Worker uses a scoped D1 binding. GitHub Actions verifies remote Worker /health, 10-store directory, product catalogue, demo checkout, order lookup, cancellation and returned stock. The checkout tests run **once per marked commit** to avoid spamming persistent data.

## Endpoints

```
GET /health
GET /api/public/store/
GET /api/public/store/diagnostics
GET /api/public/store/slug/demo-bsmart-grocery
GET /api/public/store/demo-bsmart-grocery
GET /api/public/orders/demo-bsmart-grocery/products
POST /api/public/orders/demo-bsmart-grocery
GET /api/public/orders/demo-bsmart-grocery/status/{token}
POST /api/public/orders/demo-bsmart-grocery/cancel/{token}
```

Only synthetic examples can be ordered. Workers CORS allows the hosted website and local development origins. For a full production launch add robust rate limits / bot controls, fraud/consent workflows, audit logs, actual merchant account authorization, payment verification, consumer privacy and retention controls.

## Critical migration gap — not silently hidden

**This is a live persistent demo ecommerce vertical slice, NOT the entire original FastAPI system migrated to D1.**

The current operational user authentication, tenant POS, store owner management, coupons/reviews/customer-chat, transaction history and real business finance records still run through their existing SQLAlchemy database (currently ephemeral SQLite in Render logs). Those are **not** synced to D1. Demo stores are not connected to a genuine store owner login and do not accept payments/ship goods. To make D1 the production primary store for *real* businesses requires a separately tested data-access architecture with owner-scoped authentication, D1 SQL schema/migration of all required operational tables, order idempotency and concurrency guarantees, password/identity migration, owner admin CRUD and restoreable backups. Do not claim otherwise.

The original user-supplied source ZIP had only `bsmart.db-wal` and `bsmart.db-shm`, **not** the primary `bsmart.db`; the research R2 bucket contained setup metadata rather than live tenant transaction backup. It is not possible to resurrect unavailable real records by making these demo stores.

## Deployment

A source-backed Wrangler configuration is at `wrangler.toml`, with migrations under `migrations/`. **The remote D1 database was already created and SQL v1+v2 was manually applied and verified using the Cloudflare API** (v2 is registered in `commerce_meta`, version `2`). Do NOT rerun `0002_customer_inventory.sql` manually against this same database; the ALTER TABLE is not designed to be repeated. On a **fresh** empty D1 instance, run migrations once in order using Wrangler and check the resulting schema.

Build frontend on Render from GitHub main; its `api.js` has a Worker URL fallback but it is also configurable at build time using `VITE_D1_COMMERCE_URL`. Production auth and payments stay disabled for demo stores.

## Evidence

- [Read-only live Worker smoke tests](https://github.com/RlM100always/Thesis/actions/runs/40317971723)
- [Guest demo order / status persistence test](https://github.com/RlM100always/Thesis/actions/runs/40318100597)
- [Demo checkout, cancellation and restock test](https://github.com/RlM100always/Thesis/actions/runs/40318406288)
