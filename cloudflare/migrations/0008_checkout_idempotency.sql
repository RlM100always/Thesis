-- D1 v8: idempotent real COD checkout; prevents duplicate stock reservation
-- when the same browser retries an order after an uncertain network response.
-- Apply ONCE after v7 and a verified backup. Existing orders stay unchanged.
ALTER TABLE commerce_orders ADD COLUMN checkout_request_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_co_checkout_request
ON commerce_orders(store_id,checkout_request_id)
WHERE checkout_request_id IS NOT NULL;
UPDATE commerce_meta SET value='8' WHERE key='schema_version';
