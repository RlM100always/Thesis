-- D1 v7: merchant operational insights, safer stock corrections and order timeline.
-- Apply ONCE after migration 0006 and an independently tested D1 backup.
ALTER TABLE commerce_products ADD COLUMN reorder_point INTEGER NOT NULL DEFAULT 5
  CHECK(reorder_point>=0 AND reorder_point<=1000000);
CREATE INDEX IF NOT EXISTS idx_cp_reorder ON commerce_products(store_id,is_listed,stock_qty);
CREATE TABLE IF NOT EXISTS commerce_inventory_corrections(
 id TEXT PRIMARY KEY,
 store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 product_id TEXT NOT NULL REFERENCES commerce_products(id),
 delta INTEGER NOT NULL CHECK(delta BETWEEN -10000 AND 10000 AND delta!=0),
 reason TEXT NOT NULL CHECK(reason IN ('restock','damage','stocktake','return','other')),
 note TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cic_store ON commerce_inventory_corrections(store_id,created_at);
CREATE TRIGGER IF NOT EXISTS cic_validate BEFORE INSERT ON commerce_inventory_corrections
BEGIN
 SELECT CASE WHEN NOT EXISTS (
   SELECT 1 FROM commerce_products WHERE id=NEW.product_id AND store_id=NEW.store_id
 ) THEN RAISE(ABORT,'Product does not belong to store') END;
 SELECT CASE WHEN NOT EXISTS (
   SELECT 1 FROM commerce_products WHERE id=NEW.product_id AND store_id=NEW.store_id
     AND stock_qty + NEW.delta BETWEEN 0 AND 1000000
 ) THEN RAISE(ABORT,'Insufficient stock or inventory limit exceeded') END;
END;
CREATE TRIGGER IF NOT EXISTS cic_apply AFTER INSERT ON commerce_inventory_corrections
BEGIN
 UPDATE commerce_products SET stock_qty=stock_qty+NEW.delta WHERE id=NEW.product_id AND store_id=NEW.store_id;
 INSERT INTO commerce_stock_adjustments(id,store_id,product_id,old_quantity,new_quantity,delta,reason)
 SELECT lower(hex(randomblob(16))),NEW.store_id,NEW.product_id,
  p.stock_qty-NEW.delta,p.stock_qty,NEW.delta,NEW.reason ||
  CASE WHEN NEW.note='' THEN '' ELSE ': ' || NEW.note END
 FROM commerce_products p WHERE p.id=NEW.product_id AND p.store_id=NEW.store_id;
END;
CREATE TABLE IF NOT EXISTS commerce_order_events(
 id TEXT PRIMARY KEY,
 store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 order_id TEXT NOT NULL REFERENCES commerce_orders(id),
 old_status TEXT,
 new_status TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_coe_order ON commerce_order_events(store_id,order_id,created_at);
-- Historical records have a truthful baseline without invented transitions.
INSERT INTO commerce_order_events(id,store_id,order_id,old_status,new_status,created_at)
SELECT 'existing-'||id,store_id,id,NULL,status,placed_at FROM commerce_orders;
CREATE TRIGGER IF NOT EXISTS coe_insert AFTER INSERT ON commerce_orders
BEGIN
 INSERT INTO commerce_order_events(id,store_id,order_id,old_status,new_status)
 VALUES(lower(hex(randomblob(16))),NEW.store_id,NEW.id,NULL,NEW.status);
END;
CREATE TRIGGER IF NOT EXISTS coe_status_update AFTER UPDATE OF status ON commerce_orders
WHEN NEW.status != OLD.status
BEGIN
 INSERT INTO commerce_order_events(id,store_id,order_id,old_status,new_status)
 VALUES(lower(hex(randomblob(16))),NEW.store_id,NEW.id,OLD.status,NEW.status);
END;
CREATE TRIGGER IF NOT EXISTS coe_no_modify BEFORE UPDATE ON commerce_order_events
BEGIN SELECT RAISE(ABORT,'Order events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS coe_no_delete BEFORE DELETE ON commerce_order_events
BEGIN SELECT RAISE(ABORT,'Order events are append-only'); END;
UPDATE commerce_meta SET value='7' WHERE key='schema_version';
