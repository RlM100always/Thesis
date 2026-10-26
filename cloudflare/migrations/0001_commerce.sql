-- B-SMART D1 storefront demo schema v1. Run with Wrangler from cloudflare/.
-- Never apply to any other Cloudflare application/database.
CREATE TABLE IF NOT EXISTS commerce_stores(
 id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 tagline TEXT, category TEXT, area TEXT, theme TEXT NOT NULL DEFAULT 'clean',
 color TEXT NOT NULL DEFAULT '#0a8752', is_demo INTEGER NOT NULL DEFAULT 1,
 is_active INTEGER NOT NULL DEFAULT 1, delivery_note TEXT DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS commerce_products(
 id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 sku TEXT NOT NULL, name TEXT NOT NULL, category TEXT,
 price_bdt INTEGER NOT NULL CHECK(price_bdt>=0),
 stock_qty INTEGER NOT NULL DEFAULT 0 CHECK(stock_qty>=0),
 is_listed INTEGER NOT NULL DEFAULT 1, is_featured INTEGER NOT NULL DEFAULT 0,
 image_url TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(store_id,sku)
);
CREATE INDEX IF NOT EXISTS idx_cp_store ON commerce_products(store_id,is_listed);
CREATE TABLE IF NOT EXISTS commerce_orders(
 id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES commerce_stores(id),
 order_number TEXT NOT NULL UNIQUE, access_token TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL DEFAULT 'placed', subtotal_bdt INTEGER NOT NULL CHECK(subtotal_bdt>=0),
 total_bdt INTEGER NOT NULL CHECK(total_bdt>=0), payment_method TEXT NOT NULL DEFAULT 'demo',
 shipping_name TEXT, shipping_phone TEXT, shipping_address TEXT,
 placed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_co_store ON commerce_orders(store_id,placed_at);
CREATE TABLE IF NOT EXISTS commerce_order_lines(
 order_id TEXT NOT NULL REFERENCES commerce_orders(id),
 product_id TEXT NOT NULL REFERENCES commerce_products(id),
 product_name TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>0),
 price_bdt INTEGER NOT NULL CHECK(price_bdt>=0),
 line_total_bdt INTEGER NOT NULL CHECK(line_total_bdt>=0),
 PRIMARY KEY(order_id,product_id)
);
CREATE TABLE IF NOT EXISTS commerce_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT OR IGNORE INTO commerce_meta(key,value) VALUES('schema_version','1');

-- Fail the entire D1 batch if a product has moved, is not published, or is sold out.
CREATE TRIGGER IF NOT EXISTS commerce_order_line_validate
BEFORE INSERT ON commerce_order_lines
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM commerce_orders o JOIN commerce_products p ON p.id=NEW.product_id
    WHERE o.id=NEW.order_id AND o.store_id=p.store_id AND p.is_listed=1
      AND p.stock_qty>=NEW.quantity AND p.price_bdt=NEW.price_bdt
  ) THEN RAISE(ABORT,'Product unavailable, price changed or insufficient stock') END;
END;
CREATE TRIGGER IF NOT EXISTS commerce_order_line_stock
AFTER INSERT ON commerce_order_lines
BEGIN
 UPDATE commerce_products SET stock_qty=stock_qty-NEW.quantity WHERE id=NEW.product_id;
END;
