-- Migration 3. Apply only once to a NEW D1 instance after migrations 1 and 2.
CREATE TABLE IF NOT EXISTS merchant_accounts(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,password_salt TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS merchant_sessions(token_hash TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES merchant_accounts(id),expires_at TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_merchant_sessions_account ON merchant_sessions(account_id);
CREATE TABLE IF NOT EXISTS merchant_login_attempts(email TEXT PRIMARY KEY,failures INTEGER NOT NULL DEFAULT 0,lock_until TEXT);
ALTER TABLE commerce_stores ADD COLUMN owner_id TEXT REFERENCES merchant_accounts(id);
CREATE INDEX IF NOT EXISTS idx_commerce_store_owner ON commerce_stores(owner_id);
CREATE TABLE IF NOT EXISTS commerce_stock_adjustments(id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES commerce_stores(id),product_id TEXT NOT NULL REFERENCES commerce_products(id),old_quantity INTEGER NOT NULL,new_quantity INTEGER NOT NULL,delta INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_commerce_adjustments_store ON commerce_stock_adjustments(store_id,created_at);
UPDATE commerce_meta SET value='3' WHERE key='schema_version';
