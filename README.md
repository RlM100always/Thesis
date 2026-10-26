# B-SMART — Bangladesh SME Business OS

**Active operational marketplace:** [Online Store Directory](https://thesis-j0n8.onrender.com/#/stores). It draws live data only from the operational `Store`/`StoreProduct` tables.

## Storefronts and data

The original full multi-storefront frontend/backend (store directory, public store pages, customer accounts, cart, checkout, owner management, coupons/reviews and payment adapters) was restored in commit `78a88efd3501fc6aa43b1c9e981535a9ef5c353c`.

**Removed:** the separate 32 synthetic research-shop explorer, its two PSV exports, and its public navigation entry. The dummy research dataset is not an operational storefront seed. No operational customer/order records were deleted.

**Data availability:** GitHub stores source code, not the Render database rows. The public store API filters `stores.is_active = true` and lists only active store profiles. A populated product catalog also needs associated `store_products.is_listed = true` rows. The 10-business development seed `seed_10_businesses.py` intentionally refuses to run on Render/PostgreSQL and must never be used to overwrite a live business.

A public, aggregate-only availability check is provided at `/api/public/store/diagnostics`; startup logs include `STORE_DIAGNOSTIC` to help identify an empty database, missing product listings, or a transient SQLite file. No credentials or personal details are logged.

See `docs/STOREFRONT_DATABASE_RECOVERY.md` for a safe recovery process and opt-in demo catalogue workflow.

## Development

```bash
pip install -r requirements.render.txt
python run_api.py
cd frontend && npm ci && npm run dev
```

The website must use a **persisted database** (`DATABASE_URL`, Render PostgreSQL) to retain organization, store, customer and order records across deploys. This does not happen merely because a Postgres instance exists.

**Research:** previous ML weights were retired. No new real SME data or trained model is represented by an empty research portal.
