-- Customer password recovery: single-use, hashed tokens and short-window abuse controls.
ALTER TABLE commerce_customer_accounts ADD COLUMN password_reset_token_hash TEXT;
ALTER TABLE commerce_customer_accounts ADD COLUMN password_reset_expires_at TEXT;
CREATE INDEX IF NOT EXISTS idx_customer_password_reset_token
  ON commerce_customer_accounts(password_reset_token_hash);
CREATE TABLE IF NOT EXISTS commerce_customer_auth_limits (
  identifier_hash TEXT PRIMARY KEY,
  window_id INTEGER NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_auth_limits_updated
  ON commerce_customer_auth_limits(updated_at);
UPDATE commerce_meta SET value='13' WHERE key='schema_version';
