-- D1 v9: merchant-managed product presentation fields, scoped to storefront.
-- Apply after 0008 on a verified, backed-up D1. Existing product images retained.
ALTER TABLE commerce_products ADD COLUMN description TEXT NOT NULL DEFAULT '';
UPDATE commerce_meta SET value='9' WHERE key='schema_version';
