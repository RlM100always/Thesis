-- v6: Real COD launch gate. Apply once, after a verified D1 backup.
-- Never promote a demo store or enable payments through a user-controlled API.
-- Schema is additive: all existing stores are unapproved by default.
ALTER TABLE commerce_stores ADD COLUMN real_cod_approved INTEGER NOT NULL DEFAULT 0 CHECK(real_cod_approved IN (0,1));
CREATE TABLE IF NOT EXISTS commerce_checkout_limits (
  store_id TEXT NOT NULL REFERENCES commerce_stores(id),
  ip_digest TEXT NOT NULL,
  hour_bucket INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(store_id,ip_digest,hour_bucket)
);
CREATE INDEX IF NOT EXISTS idx_cod_rate_hour ON commerce_checkout_limits(hour_bucket);
UPDATE commerce_meta SET value='6' WHERE key='schema_version';
