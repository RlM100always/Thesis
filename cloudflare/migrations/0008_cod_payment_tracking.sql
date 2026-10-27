-- Persist COD collection state separately from fulfilment status.
-- Online payment providers and automatic refunds remain disabled.
ALTER TABLE commerce_orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid'
  CHECK(payment_status IN ('demo_no_payment','pending_cod','paid','cancelled_no_payment','unpaid'));
ALTER TABLE commerce_orders ADD COLUMN payment_received_at TEXT;
ALTER TABLE commerce_orders ADD COLUMN payment_received_by TEXT;
ALTER TABLE commerce_orders ADD COLUMN payment_note TEXT;

UPDATE commerce_orders
SET payment_status = CASE
  WHEN COALESCE((SELECT is_demo FROM commerce_stores WHERE id=commerce_orders.store_id),1)=1
       OR payment_method IN ('demo','demo_pos') THEN 'demo_no_payment'
  WHEN payment_method='cod' AND status='cancelled' THEN 'cancelled_no_payment'
  WHEN payment_method='cod' THEN 'pending_cod'
  ELSE 'unpaid'
END;

CREATE TRIGGER IF NOT EXISTS commerce_set_initial_payment_status
AFTER INSERT ON commerce_orders
BEGIN
  UPDATE commerce_orders
  SET payment_status = CASE
    WHEN COALESCE((SELECT is_demo FROM commerce_stores WHERE id=NEW.store_id),1)=1
         OR NEW.payment_method IN ('demo','demo_pos') THEN 'demo_no_payment'
    WHEN NEW.payment_method='cod' THEN 'pending_cod'
    ELSE 'unpaid'
  END
  WHERE id=NEW.id;
END;

DROP TRIGGER IF EXISTS commerce_restore_cancelled_stock;
CREATE TRIGGER commerce_restore_cancelled_stock
AFTER UPDATE OF status ON commerce_orders
WHEN NEW.status='cancelled' AND OLD.status!='cancelled'
BEGIN
  UPDATE commerce_orders
  SET payment_status = CASE
    WHEN payment_method='cod'
      AND COALESCE((SELECT is_demo FROM commerce_stores WHERE id=NEW.store_id),1)=0
      AND payment_status!='paid' THEN 'cancelled_no_payment'
    ELSE payment_status
  END
  WHERE id=NEW.id;

  UPDATE commerce_products
  SET stock_qty=stock_qty+COALESCE(
    (SELECT SUM(l.quantity) FROM commerce_order_lines l WHERE l.order_id=NEW.id AND l.product_id=commerce_products.id),0)
  WHERE store_id=NEW.store_id
    AND id IN (SELECT product_id FROM commerce_order_lines WHERE order_id=NEW.id);
  INSERT INTO commerce_inventory_movements(id,store_id,product_id,order_id,quantity_change,reason)
  SELECT lower(hex(randomblob(16))),NEW.store_id,l.product_id,NEW.id,l.quantity,'demo_cancel_return'
  FROM commerce_order_lines l WHERE l.order_id=NEW.id;
END;

UPDATE commerce_meta SET value='8' WHERE key='schema_version';
