-- Owner account activation and explicit owner role for platform administration.
-- Existing accounts remain active and retain owner access by default.
ALTER TABLE merchant_accounts ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
  CHECK(is_active IN (0,1));
ALTER TABLE merchant_accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'owner'
  CHECK(role IN ('owner'));
CREATE INDEX IF NOT EXISTS idx_merchant_accounts_active_role
  ON merchant_accounts(is_active,role);
UPDATE commerce_meta SET value='12' WHERE key='schema_version';
