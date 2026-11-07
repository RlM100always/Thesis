# B-SMART — Bangladesh Business OS

**Website:** https://thesis-j0n8.onrender.com
**Online stores:** https://thesis-j0n8.onrender.com/#/stores
**NEW Cloudflare D1 owner dashboard:** https://thesis-j0n8.onrender.com/#/d1-owner

## Current status (7 November 2026)

The React website is deployed on Render. Its **new Cloudflare D1 demo commerce backend** lives on Cloudflare Workers and persists the store, product, order, anonymous demo customer, inventory-movement and cashbook data. The Worker URL is https://bsmart-commerce-api.bcs-written-rakib.workers.dev .

Current `bsmart-commerce` D1 data: 10 **fictional demo shops** with 259 sample products, plus one retained POS CI fixture with one test product. The D1 database also contains three demo/test orders, three order lines, three inventory movements, one test cashbook receipt and one legacy CI merchant account. All 11 existing stores are marked `is_demo=1`; there are no real merchant-owned operational stores and no registered D1 customer accounts. These records are preserved; the CI fixture is excluded from the public store directory. These are **not** the previously removed 32 research shops, and not restored real businesses. No demo order should be fulfilled and no payment should be collected from a demo shop.

The D1 owner console has **a separate account system**. New owner accounts use PBKDF2-HMAC-SHA-256 password hashes (100,000 iterations); legacy one-time access-key accounts remain compatible. Owners can create a private operational-store draft, manage products and stock, see orders and use demo POS/cashbook tools. Platform Admin approval is required before a merchant-owned store can become public and accept COD orders. Email verification, password recovery and merchant identity validation are not implemented. The old FastAPI business login will **not** sign in to the D1 owner console. The separate Cloudflare D1 database named `bcs-written` contains study-content records and is not the B-SMART commerce database; do not mix it with `bsmart-commerce`.

**Important: Original full business system has not been migrated.** The original extensive FastAPI + SQLAlchemy modules — actual POS/cash, accounting, CRM/customer profiles, staff, coupons, chat, invoicing, supplier/inventory procurement, financing and historical merchant records — still use the old operational database, last verified running on ephemeral SQLite on Render. This old data is **not** synced with the new D1 demo slice, and cannot be declared persistent through Cloudflare. Changing only `DATABASE_URL` to a D1 identifier is not a working migration.

The user's original local ZIP lacked the primary `bsmart.db` and contained only `bsmart.db-wal` / `bsmart.db-shm`. The connected R2 research bucket held setup metadata, not a complete merchant-data backup. Real historic orders/customers cannot be restored without a valid database/backup.

## Implementation and verification

- [Cloudflare D1 source, Worker, migrations and technical status](cloudflare/README.md)
- [Legacy data recovery precautions](docs/STOREFRONT_DATABASE_RECOVERY.md)
- [Cloudflare D1 Worker live smoke checks](https://github.com/RlM100always/Thesis/actions/runs/40326438876) — owner-created shop preview and transactional demo POS reconciliation passed
- [D1 access-key owner signup and stock CRUD tests](https://github.com/RlM100always/Thesis/actions/runs/40325162409)
- [Demo order cancellation and stock rollback](https://github.com/RlM100always/Thesis/actions/runs/40318406288)

For the backend local developer environment:

```bash
pip install -r requirements.render.txt
python run_api.py
cd frontend
npm ci && npm run dev
```

The experimental demo system and the legacy operational app must remain clearly labelled and isolated until the full application is migrated, secured and validated.


## Production upgrade tracking

- [Step-by-step production implementation plan](docs/PRODUCTION_IMPLEMENTATION_PLAN.md)
- [Store owner access register (no passwords or secrets)](docs/STORE_ACCESS_REGISTER.md)
- [Deployment, verification and rollback runbook](docs/DEPLOYMENT_RUNBOOK.md)

The implementation plan distinguishes existing functionality from work still required. Do not treat sample catalogue stores as real merchants, and never publish owner passwords, platform-admin keys, API tokens or payment secrets in this public repository.
