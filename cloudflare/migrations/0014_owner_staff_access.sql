-- B-SMART Cloudflare Primary: verified owner onboarding and store-scoped staff access.
-- Additive only. Preserve every existing commerce account, store, order and product.
ALTER TABLE merchant_accounts ADD COLUMN display_name TEXT;
ALTER TABLE merchant_accounts ADD COLUMN email_verification_method TEXT;

CREATE INDEX IF NOT EXISTS idx_merchant_accounts_role_active
  ON merchant_accounts(role,is_active);

CREATE TABLE IF NOT EXISTS merchant_owner_invites (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE,
  owner_name TEXT NOT NULL,
  store_name TEXT NOT NULL,
  category TEXT NOT NULL,
  area TEXT NOT NULL,
  tagline TEXT,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  identity_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(identity_confirmed IN (0,1)),
  accepted_at TEXT,
  revoked_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_invites_pending_email
  ON merchant_owner_invites(email)
  WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS merchant_staff_store_access (
  account_id TEXT PRIMARY KEY REFERENCES merchant_accounts(id) ON DELETE CASCADE,
  owner_id TEXT NOT NULL REFERENCES merchant_accounts(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('manager','sales','inventory','support','analyst')),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT,
  UNIQUE(store_id,account_id)
);
CREATE INDEX IF NOT EXISTS idx_merchant_staff_store_role
  ON merchant_staff_store_access(store_id,role,is_active);
CREATE INDEX IF NOT EXISTS idx_merchant_staff_owner
  ON merchant_staff_store_access(owner_id,is_active);

CREATE TABLE IF NOT EXISTS merchant_staff_invites (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES merchant_accounts(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  email TEXT NOT NULL COLLATE NOCASE,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('manager','sales','inventory','support','analyst')),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  accepted_at TEXT,
  revoked_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_invites_pending_email
  ON merchant_staff_invites(email)
  WHERE accepted_at IS NULL AND revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_staff_invites_store
  ON merchant_staff_invites(store_id,created_at);

UPDATE commerce_meta SET value='14' WHERE key='schema_version';
