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

### Verified Cloudflare / live-database status — 26 October 2026

The user's intended primary Cloudflare storage is present: the **Primary Cloudflare account** contains R2 bucket `bsmart-thesis-research`. At verification, that bucket had **one object** (`thesis/research/setup.json`, 269 bytes), and the account had **no B-SMART D1 database**. R2 is integrated in `api/r2_store.py` for research-file/model objects; it is **not** the operational shop/customer/order database.

Render startup logs verified that `thesis-j0n8.onrender.com` actually uses **SQLite**: 1 organization, 4 products, 0 stores, 0 public listings. An independent Render PostgreSQL instance also exists but is not connected to the running app; its mere existence does not make it primary. **Do not blindly switch production to PostgreSQL or run a demo seed without confirming where original business records live.** The opt-in demo bootstrap flag was disabled.

If Cloudflare must become the operational **primary database**, provision/validate **Cloudflare D1** and implement a compatible transaction-safe data-access layer and migrations first. D1 cannot be selected simply by assigning an R2 bucket to SQLAlchemy's `DATABASE_URL`. Alternatively retain PostgreSQL for operational SQL and R2 for research files/backups after an explicit architecture decision. Neither path reconstructs customer/order records without their original database or backups.

**Research:** previous ML weights were retired. No new real SME data or trained model is represented by an empty research portal.
