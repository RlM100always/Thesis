# Full Multi-Storefront Recovery from User's Local Thesis ZIP

**Restoration branch:** `restoration/full-local-stores-2026-10-25`.

## Restored original local source (not reimagined)

- Public `/#/stores` Store Directory lists **active tenant stores** from `stores` DB, not the 32 simulated thesis stores.
- Dedicated branded storefront per business at `/#/store/<slug-or-organization-id>`, with product catalogue, cart, checkout and tracked orders.
- Original local `Store.jsx` (127 KB), `StoreAdmin.jsx` (116 KB), `StoreCustomerPortal.jsx` (30 KB), `StoreDirectory.jsx`, `OrderStatus.jsx`, `storeImages.js` restored **byte-for-byte** from local recovery overlay. Git blob SHA validated.
- Restored backend `store_routes.py`, `order_routes.py`, `store_customer_routes.py`, `coupon_routes.py`, `review_routes.py`, `payment_routes.py`, `domain_models.py` and `database.py` from the same source; wired each in `api/main.py`.
- Restored missing methods in `frontend/src/api.js`, while **preserving** existing SaaS admin, B-SMART research reset and current enterprise operation methods; unsafe GET masquerading as POST corrected.
- Recovered opt-in, explicitly synthetic `seed_10_businesses.py`; this has not been run on any production DB, and requires `BSMART_ALLOW_SYNTHETIC_SEED=YES`, a unique password and a local, empty test DB.
- A new *additive* Alembic migration `b5f251025a01` merges existing two migration heads and introduces missing columns/tables when deliberately applied.

## Scope and non-claims

Local isolated SQLite smoke test from recovery ZIP confirmed **store listing -> slug -> catalogue -> customer registration -> COD order -> tracking -> owner organization SalesDocument**. The ZIP's restoration report contains details. Full production PostgreSQL migration, frontend Vite bundle, sandbox payment callbacks, network/webhook security and mobile device-specific QA remain outstanding.

The uploaded local archive contained SQLite `-wal` and `-shm` but no complete matching `bsmart.db`. GitHub can restore source code; it cannot restore unbacked live customer/order history. Do not run the seed script on existing operational business data.

**Academic split:** Research Portal's 32 synthetic shops are research data; this public storefront directory only reads real operational `Store` rows. Do not combine them without explicit test/simulation tagging.

## Next stage for production

Run `npm ci && npm run build` in `frontend/`; run backend unit/route tests; test staging database migration with a backup; test owner/customer checkout and permissions; and verify Render build. Production payment gateway must use live-approved secret credentials and verified callbacks, never a demo password.
