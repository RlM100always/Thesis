-- Additive multi-store commerce workflows for customer support, returns and platform oversight.
-- These are demo operations. No payment provider or physical delivery is activated.
ALTER TABLE commerce_products ADD COLUMN description TEXT;
ALTER TABLE commerce_products ADD COLUMN brand TEXT;
ALTER TABLE commerce_products ADD COLUMN tags TEXT;
ALTER TABLE commerce_products ADD COLUMN compare_at_price_bdt INTEGER;
ALTER TABLE commerce_products ADD COLUMN unit_label TEXT DEFAULT 'pcs';
ALTER TABLE commerce_products ADD COLUMN updated_at TEXT;

ALTER TABLE commerce_orders ADD COLUMN cancellation_reason TEXT;
ALTER TABLE commerce_orders ADD COLUMN status_note TEXT;

CREATE TABLE IF NOT EXISTS commerce_order_returns(
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  order_id TEXT NOT NULL UNIQUE REFERENCES commerce_orders(id) ON DELETE CASCADE,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  customer_note TEXT,
  merchant_note TEXT,
  status TEXT NOT NULL DEFAULT 'requested'
    CHECK(status IN ('requested','approved','rejected','received','closed_demo')),
  requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_commerce_returns_store_status
  ON commerce_order_returns(store_id,status,requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_commerce_returns_account
  ON commerce_order_returns(account_id,requested_at DESC);

-- A returned demo order is restocked once, only after the merchant confirms receipt.
-- "received" is not a real refund and must never trigger a money movement.
CREATE TRIGGER IF NOT EXISTS commerce_restock_received_return
AFTER UPDATE OF status ON commerce_order_returns
WHEN NEW.status='received' AND OLD.status='approved'
BEGIN
  UPDATE commerce_products
    SET stock_qty=stock_qty+COALESCE(
      (SELECT SUM(l.quantity) FROM commerce_order_lines l
       WHERE l.order_id=NEW.order_id AND l.product_id=commerce_products.id),0),
        updated_at=CURRENT_TIMESTAMP
    WHERE store_id=NEW.store_id
      AND id IN (SELECT product_id FROM commerce_order_lines WHERE order_id=NEW.order_id);
  INSERT INTO commerce_inventory_movements(id,store_id,product_id,order_id,quantity_change,reason)
    SELECT lower(hex(randomblob(16))),NEW.store_id,l.product_id,NEW.order_id,l.quantity,'demo_return_received'
    FROM commerce_order_lines l WHERE l.order_id=NEW.order_id;
END;

CREATE TABLE IF NOT EXISTS commerce_customer_messages(
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  account_id TEXT NOT NULL REFERENCES commerce_customer_accounts(id) ON DELETE CASCADE,
  order_id TEXT REFERENCES commerce_orders(id) ON DELETE SET NULL,
  sender_role TEXT NOT NULL CHECK(sender_role IN ('customer','merchant')),
  message TEXT NOT NULL CHECK(length(trim(message)) BETWEEN 1 AND 2000),
  read_by_customer_at TEXT,
  read_by_merchant_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_messages_thread
  ON commerce_customer_messages(store_id,account_id,created_at);
CREATE INDEX IF NOT EXISTS idx_customer_messages_unread
  ON commerce_customer_messages(store_id,sender_role,read_by_merchant_at,read_by_customer_at);

CREATE TABLE IF NOT EXISTS commerce_platform_admin_audit(
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  details TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_platform_admin_audit_time
  ON commerce_platform_admin_audit(created_at DESC);

UPDATE commerce_meta SET value='7' WHERE key='schema_version';
