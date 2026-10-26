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
-- Preserve stock consistency while distinguishing real COD movement audit entries.
DROP TRIGGER IF EXISTS commerce_record_order_stock;
CREATE TRIGGER commerce_record_order_stock AFTER INSERT ON commerce_order_lines
BEGIN
  INSERT INTO commerce_inventory_movements(id,store_id,product_id,order_id,quantity_change,reason)
  SELECT lower(hex(randomblob(16))),o.store_id,NEW.product_id,NEW.order_id,-NEW.quantity,
         CASE WHEN s.is_demo=1 THEN 'demo_sale' ELSE 'online_cod_sale' END
  FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id
  WHERE o.id=NEW.order_id;
END;
DROP TRIGGER IF EXISTS commerce_restore_cancelled_stock;
CREATE TRIGGER commerce_restore_cancelled_stock AFTER UPDATE OF status ON commerce_orders
WHEN NEW.status='cancelled' AND OLD.status!='cancelled'
BEGIN
  UPDATE commerce_products SET stock_qty=stock_qty+COALESCE(
    (SELECT SUM(l.quantity) FROM commerce_order_lines l
      WHERE l.order_id=NEW.id AND l.product_id=commerce_products.id),0)
  WHERE store_id=NEW.store_id AND id IN (SELECT product_id FROM commerce_order_lines WHERE order_id=NEW.id);
  INSERT INTO commerce_inventory_movements(id,store_id,product_id,order_id,quantity_change,reason)
  SELECT lower(hex(randomblob(16))),NEW.store_id,l.product_id,NEW.id,l.quantity,
         CASE WHEN s.is_demo=1 THEN 'demo_cancel_return' ELSE 'cod_cancel_return' END
  FROM commerce_order_lines l JOIN commerce_stores s ON s.id=NEW.store_id
  WHERE l.order_id=NEW.id;
END;

UPDATE commerce_meta SET value='6' WHERE key='schema_version';
