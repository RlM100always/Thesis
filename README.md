# B-SMART — Bangladesh Business OS

**Website:** https://thesis-j0n8.onrender.com
**Online stores:** https://thesis-j0n8.onrender.com/#/stores
**NEW Cloudflare D1 owner dashboard:** https://thesis-j0n8.onrender.com/#/d1-owner

## Current status (8 November 2026)

The React website is deployed on Render and the Cloudflare Worker `bsmart-commerce-api` has been deployed with the production multi-store upgrade. The Worker URL is https://bsmart-commerce-api.bcs-written-rakib.workers.dev . Cloudflare D1 `bsmart-commerce` remains the authoritative store/customer/order/inventory database for the D1 storefront.

Current `bsmart-commerce` D1 data: 10 **fictional sample shops** with 259 sample products, plus one retained POS CI fixture with one test product. There are three test orders, three order lines, three inventory movements, one test cashbook receipt and one legacy CI merchant account. All 11 stores are inactive and marked `is_demo=1`; therefore the public D1 store directory correctly returns zero stores and zero listed public products. There are no verified real merchant-owned operational stores and no D1 customer accounts. Existing records are preserved. These are **not** the previously removed 32 research shops or restored real businesses. Do not present sample data as real trading activity or collect payments from these sample shops.

The D1 owner console has **a separate account system**. New owner accounts use PBKDF2-HMAC-SHA-256 password hashes (100,000 iterations); legacy one-time access-key accounts remain compatible. Owners can create a private operational-store draft, manage products and stock, see orders and use demo POS/cashbook tools. Platform Admin approval is required before a merchant-owned store can become public and accept COD orders. Owner email verification and password recovery are implemented and deployed, but registration remains safely disabled until a verified Resend sender and `RESEND_API_KEY` are configured. Merchant identity validation is still required before operational publication. The old FastAPI business login will **not** sign in to the D1 owner console. The separate Cloudflare D1 database named `bcs-written` contains study-content records and is not the B-SMART commerce database; do not mix it with `bsmart-commerce`.

**Important: Original full business system has not been migrated.** The original extensive FastAPI + SQLAlchemy modules — actual POS/cash, accounting, CRM/customer profiles, staff, coupons, chat, invoicing, supplier/inventory procurement, financing and historical merchant records — still use the old operational database, last verified running on ephemeral SQLite on Render. This old data is **not** synced with the new D1 demo slice, and cannot be declared persistent through Cloudflare. Changing only `DATABASE_URL` to a D1 identifier is not a working migration.

The user's original local ZIP lacked the primary `bsmart.db` and contained only `bsmart.db-wal` / `bsmart.db-shm`. The connected R2 research bucket held setup metadata, not a complete merchant-data backup. Real historic orders/customers cannot be restored without a valid database/backup.

## Production upgrade deployment (8 November 2026)\n\n- [Merged production upgrade PR #20](https://github.com/RlM100always/Thesis/pull/20)\n- [Production CI: frontend, backend, D1 schema and Worker checks](https://github.com/RlM100always/Thesis/actions/runs/42443796673)\n- [Cloudflare Worker deployment](https://github.com/RlM100always/Thesis/actions/runs/42443796647)\n- Render deployment commit: `3cc005fd46f048fd5dcece1f072abbda36ce72c4` (live)\n- Cloudflare D1 schema version: **12** (migrations 0009–0012 applied after schema inspection and export)\n- Cloudflare Worker version: `836c5aa8-0c51-482a-bb01-29432d8d1f38` (100% deployment)\n\nThe Worker AI binding is present, but model inference is disabled by default. Assistants use deterministic database-grounded fallback answers until `AI_ENABLED=true` is deliberately configured. Owner email flows remain unavailable until the Resend provider is configured.\n\n## Implementation and verification

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

The D1 commerce platform and legacy FastAPI operational system remain separate. The legacy FastAPI operational database has not been migrated; it was last verified as ephemeral SQLite on Render. Do not claim historical POS, accounting, CRM or purchasing data is in D1.


## Production upgrade tracking

- [Step-by-step production implementation plan](docs/PRODUCTION_IMPLEMENTATION_PLAN.md)
- [Store owner access register (no passwords or secrets)](docs/STORE_ACCESS_REGISTER.md)
- [Deployment, verification and rollback runbook](docs/DEPLOYMENT_RUNBOOK.md)

The implementation plan distinguishes existing functionality from work still required. Do not treat sample catalogue stores as real merchants, and never publish owner passwords, platform-admin keys, API tokens or payment secrets in this public repository.
