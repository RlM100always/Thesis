-- v2 anonymized demo customers, auditable inventory changes and reversals.
-- This file was ALREADY applied to the connected bsmart-commerce D1 remotely;
-- do not rerun the ALTER TABLE in production through manual SQL.
CREATE TABLE IF NOT EXISTS commerce_customers(
 id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 display_name TEXT NOT NULL DEFAULT 'Anonymous demo customer',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_demo_customers_store ON commerce_customers(store_id);
ALTER TABLE commerce_orders ADD COLUMN customer_id TEXT REFERENCES commerce_customers(id);
CREATE TABLE IF NOT EXISTS commerce_inventory_movements(
 id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 product_id TEXT NOT NULL REFERENCES commerce_products(id),
 order_id TEXT NOT NULL REFERENCES commerce_orders(id),
 quantity_change INTEGER NOT NULL, reason TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_demo_inv_order ON commerce_inventory_movements(order_id);
CREATE TRIGGER IF NOT EXISTS commerce_record_order_stock
AFTER INSERT ON commerce_order_lines
BEGIN
 INSERT INTO commerce_inventory_movements(id,store_id,product_id,order_id,quantity_change,reason)
 SELECT lower(hex(randomblob(16))),o.store_id,NEW.product_id,NEW.order_id,-NEW.quantity,'demo_sale'
 FROM commerce_orders o WHERE o.id=NEW.order_id;
END;
CREATE TRIGGER IF NOT EXISTS commerce_restore_cancelled_stock
AFTER UPDATE OF status ON commerce_orders
WHEN NEW.status='cancelled' AND OLD.status!='cancelled'
BEGIN
 UPDATE commerce_products
 SET stock_qty=stock_qty+COALESCE(
   (SELECT SUM(l.quantity) FROM commerce_order_lines l WHERE l.order_id=NEW.id AND l.product_id=commerce_products.id),0)
 WHERE store_id=NEW.store_id AND id IN (SELECT product_id FROM commerce_order_lines WHERE order_id=NEW.id);
 INSERT INTO commerce_inventory_movements(id,store_id,product_id,order_id,quantity_change,reason)
 SELECT lower(hex(randomblob(16))),NEW.store_id,l.product_id,NEW.id,l.quantity,'demo_cancel_return'
 FROM commerce_order_lines l WHERE l.order_id=NEW.id;
END;
UPDATE commerce_meta SET value='2' WHERE key='schema_version';
