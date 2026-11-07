-- Add owner email verification and single-use password recovery tokens.
-- Apply only after backing up the existing D1 database and checking live schema.
ALTER TABLE merchant_accounts ADD COLUMN email_verified_at TEXT;
ALTER TABLE merchant_accounts ADD COLUMN email_verification_token_hash TEXT;
ALTER TABLE merchant_accounts ADD COLUMN email_verification_expires_at TEXT;
ALTER TABLE merchant_accounts ADD COLUMN password_reset_token_hash TEXT;
ALTER TABLE merchant_accounts ADD COLUMN password_reset_expires_at TEXT;

CREATE INDEX IF NOT EXISTS idx_merchant_email_verification_token
  ON merchant_accounts(email_verification_token_hash);
CREATE INDEX IF NOT EXISTS idx_merchant_password_reset_token
  ON merchant_accounts(password_reset_token_hash);

UPDATE commerce_meta SET value='9' WHERE key='schema_version';
