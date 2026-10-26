# B-SMART research reset and operational marketplace separation

The previously generated integrated synthetic research-shop catalogue and its
separate explorer were **removed from GitHub main on 26 October 2026** at the
user's request. It is not the same as an operational business storefront.

- Live ecommerce shops come only from the business `Store` and `StoreProduct`
  records in the configured application database, at `/#/stores`.
- The research models/experiments were previously retired; this project makes
  no claim of freshly validated ML predictions.
- The archived source history remains under
  `archive/pre-new-bsmart-dataset-2026-10-25`.
- The operational storefront functionality (customer registration/login,
  store owner settings, product catalogues, checkout, customer/order history,
  chat, coupons, reviews, payment-adapter code) is retained.

**Operational DB recovery and demonstration catalogue:** see
[STOREFRONT_DATABASE_RECOVERY.md](STOREFRONT_DATABASE_RECOVERY.md).
Production must use durable PostgreSQL; neither GitHub code nor a synthetic
research CSV can restore missing live customer/order records from an
unavailable SQLite file.
