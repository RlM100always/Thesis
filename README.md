# B-SMART — Bangladesh Business OS

**Website:** https://thesis-j0n8.onrender.com
**Online stores:** https://thesis-j0n8.onrender.com/#/stores
**NEW Cloudflare D1 owner dashboard:** https://thesis-j0n8.onrender.com/#/d1-owner

## Current status (26 October 2026)

The React website is deployed on Render. Its **new Cloudflare D1 demo commerce backend** lives on Cloudflare Workers and persists the store, product, order, anonymous demo customer, inventory-movement and cashbook data. The Worker URL is https://bsmart-commerce-api.bcs-written-rakib.workers.dev .

Current D1 development data: 10 original **fictional demo shops** with 259 sample products, plus one temporary automated CI demonstration store and one temporary POS test product. These are **not** the previously removed 32 research shops, and not restored real businesses. No customer order should be fulfilled and no payment should be collected from a demo shop.

The new D1 owner console has **a separate account system**. Owners can create a demo shop, publish products, change stock, see orders, simulate POS sale, record sample receipt/expenses and inspect a basic cashbook. Owner signup gives a **one-time 256-bit access key**. Save it securely; lost keys cannot be recovered. Email verification, password recovery, merchant identity validation and actual payments are not implemented. The old FastAPI business login will **not** sign in to the new D1 owner console.

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
