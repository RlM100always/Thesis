-- Store-specific coupons and immutable redemption history.
-- Apply only after backup and live-schema verification.
ALTER TABLE commerce_orders ADD COLUMN coupon_code TEXT;
ALTER TABLE commerce_orders ADD COLUMN coupon_discount_bdt INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS commerce_coupons(
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES commerce_stores(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  discount_type TEXT NOT NULL CHECK(discount_type IN ('percent','fixed')),
  discount_value INTEGER NOT NULL CHECK(discount_value > 0),
  min_order_bdt INTEGER NOT NULL DEFAULT 0 CHECK(min_order_bdt >= 0),
  max_discount_bdt INTEGER CHECK(max_discount_bdt IS NULL OR max_discount_bdt > 0),
  usage_limit INTEGER CHECK(usage_limit IS NULL OR usage_limit > 0),
  per_customer_limit INTEGER CHECK(per_customer_limit IS NULL OR per_customer_limit > 0),
  starts_at TEXT,
  ends_at TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(store_id,code),
  CHECK(discount_type!='percent' OR discount_value<=100),
  CHECK(ends_at IS NULL OR starts_at IS NULL OR ends_at>starts_at)
);
CREATE INDEX IF NOT EXISTS idx_commerce_coupons_store_active
  ON commerce_coupons(store_id,is_active,code);

CREATE TABLE IF NOT EXISTS commerce_coupon_redemptions(
  id TEXT PRIMARY KEY,
  coupon_id TEXT NOT NULL REFERENCES commerce_coupons(id),
  store_id TEXT NOT NULL REFERENCES commerce_stores(id),
  order_id TEXT NOT NULL UNIQUE REFERENCES commerce_orders(id),
  account_id TEXT,
  customer_key_hash TEXT NOT NULL,
  discount_bdt INTEGER NOT NULL CHECK(discount_bdt>=0),
  redeemed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_commerce_coupon_redemptions_coupon
  ON commerce_coupon_redemptions(coupon_id,redeemed_at);
CREATE INDEX IF NOT EXISTS idx_commerce_coupon_redemptions_customer
  ON commerce_coupon_redemptions(coupon_id,customer_key_hash);

CREATE TRIGGER IF NOT EXISTS commerce_coupon_total_limit
BEFORE INSERT ON commerce_coupon_redemptions
WHEN (SELECT usage_limit FROM commerce_coupons WHERE id=NEW.coupon_id) IS NOT NULL
 AND (SELECT COUNT(*) FROM commerce_coupon_redemptions WHERE coupon_id=NEW.coupon_id) >=
     (SELECT usage_limit FROM commerce_coupons WHERE id=NEW.coupon_id)
BEGIN
  SELECT RAISE(ABORT,'COUPON_USAGE_LIMIT');
END;

CREATE TRIGGER IF NOT EXISTS commerce_coupon_customer_limit
BEFORE INSERT ON commerce_coupon_redemptions
WHEN (SELECT per_customer_limit FROM commerce_coupons WHERE id=NEW.coupon_id) IS NOT NULL
 AND (SELECT COUNT(*) FROM commerce_coupon_redemptions
      WHERE coupon_id=NEW.coupon_id AND customer_key_hash=NEW.customer_key_hash) >=
     (SELECT per_customer_limit FROM commerce_coupons WHERE id=NEW.coupon_id)
BEGIN
  SELECT RAISE(ABORT,'COUPON_CUSTOMER_LIMIT');
END;

UPDATE commerce_meta SET value='11' WHERE key='schema_version';
