-- D1 customer accounts and durable multi-store shopping state.
-- Additive only: existing demo orders/products/stores are preserved.
CREATE TABLE IF NOT EXISTS commerce_customer_accounts (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  email TEXT COLLATE NOCASE UNIQUE,
  phone TEXT UNIQUE,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  avatar_data_url TEXT,
  division TEXT,
  district TEXT,
  thana TEXT,
  address_detail TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (length(trim(display_name)) >= 2),
  CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS commerce_customer_sessions (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_sessions_account ON commerce_customer_sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_customer_sessions_expiry ON commerce_customer_sessions(expires_at);

CREATE TABLE IF NOT EXISTS commerce_customer_login_attempts (
  identifier TEXT PRIMARY KEY,
  failures INTEGER NOT NULL DEFAULT 0,
  lock_until TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS commerce_customer_addresses (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  label TEXT NOT NULL DEFAULT 'বাড়ি',
  recipient_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  division TEXT NOT NULL,
  district TEXT NOT NULL,
  thana TEXT,
  address_detail TEXT NOT NULL,
  postal_code TEXT,
  is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_addresses_account_default
  ON commerce_customer_addresses(account_id, is_default, created_at);

CREATE TABLE IF NOT EXISTS commerce_customer_wishlist_items (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES commerce_products(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(account_id, store_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_wishlist_account
  ON commerce_customer_wishlist_items(account_id, created_at);

CREATE TABLE IF NOT EXISTS commerce_customer_cart_items (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES commerce_products(id) ON DELETE CASCADE,
  quantity INTEGER NOT NULL CHECK (quantity >= 1 AND quantity <= 99),
  variant_label TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(account_id, store_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_cart_account_store
  ON commerce_customer_cart_items(account_id, store_id);

CREATE TABLE IF NOT EXISTS commerce_product_reviews (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES commerce_products(id) ON DELETE CASCADE,
  order_id TEXT NOT NULL REFERENCES commerce_orders(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(account_id, store_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_product_reviews_store_product
  ON commerce_product_reviews(store_id, product_id, created_at);

-- NULL for all pre-existing guest orders; only new account-linked orders are shown
-- in customer order history. No historical orders are assigned by phone number.
ALTER TABLE commerce_orders
  ADD COLUMN account_id TEXT REFERENCES commerce_customer_accounts(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_commerce_orders_account_placed
  ON commerce_orders(account_id, placed_at DESC);
