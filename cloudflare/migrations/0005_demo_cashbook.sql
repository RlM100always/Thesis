-- D1 demo POS/cashbook, not a regulated, certified double-entry ledger.
CREATE TABLE IF NOT EXISTS commerce_cashbook(
 id TEXT PRIMARY KEY,store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 kind TEXT NOT NULL CHECK(kind IN ('receipt','expense')),
 amount_bdt INTEGER NOT NULL CHECK(amount_bdt>0),
 description TEXT NOT NULL,
 related_order_id TEXT REFERENCES commerce_orders(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_demo_cashbook_store ON commerce_cashbook(store_id,created_at);
UPDATE commerce_meta SET value='5' WHERE key='schema_version';
