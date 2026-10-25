# Local storefront recovery: progress and remaining differences (25 October 2026)

The local source archive `thesis.zip` and the accompanying generated recovery package contain additional store modules **not in the earlier GitHub checkout**. They must not be confused with the 32-shop research **synthetic** Store Explorer.

## Implemented on GitHub main

- `GET /api/public/store/`: active **operational** stores from the application's `Store` and `Organization` tables, with only public profile fields; hidden/inactive stores excluded.
- `GET /api/public/store/slug/{slug}`: resolves active stores to existing public product listing.
- `/#/stores`: responsive directory with search, category filters, cover/logo/cards and Android-like mobile bottom navigation. Store cards open the existing `/#/store/{organization_id}` sales channel with cart/order flow.
- Added visible nav item on the public website and unit tests for active filtering/slug lookup.
- These changes preserve ongoing research-reset code; they do not re-enable old ML model weights.

## Local source modules still awaiting upload/merge

The local archive has substantially newer versions of `Store.jsx` (~127 KB), `StoreAdmin.jsx` (~116 KB), `OrderStatus.jsx`, and `api/store_routes.py`; missing modules include `StoreCustomerPortal.jsx`, `api/store_customer_routes.py`, `api/coupon_routes.py`, `api/review_routes.py`, `api/payment_routes.py`, customer/payment model additions and the opt-in `seed_10_businesses.py`. They have **not** been represented as finished or deployed here.

The chat-generated **BSMART_FULL_LOCAL_STOREFRONT_RECOVERY_2026-10-25.zip** contains a safe selective merge script (`RESTORE_AND_PUSH.ps1`) to apply these exact source files to a freshly cloned GitHub working copy and push a named restoration branch after frontend build and isolated order smoke checks. This is the correct method to transfer local ZIP content to a remote repository when the GitHub connector cannot use the local ZIP as source bytes. Inspect the branch and perform final staging DB migration tests before merging to main.

## Existing business records

Git source control holds code, **not** the deployed business database. The uploaded `thesis.zip` contains SQLite WAL and SHM files, but **no matching complete `bsmart.db` file**. Therefore, an old owner/customer/order history cannot be automatically recovered from this Git archive. If your Render SQLite was ephemeral, check persistent Postgres/backups before assuming the records remain.

The ten businesses in the local seed script are simulated/demo businesses and should only be seeded on an isolated test tenant with explicit opt-in. They are not the 32 synthetic research shops and are not a substitute for restoring genuine persisted records.
