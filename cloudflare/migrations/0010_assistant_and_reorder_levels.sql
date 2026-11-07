-- Owner reorder thresholds and privacy-preserving AI assistant rate limits.
-- Apply only after backing up D1 and verifying migrations 0009 and 0010 are absent.
ALTER TABLE commerce_products ADD COLUMN reorder_level INTEGER NOT NULL DEFAULT 5
  CHECK(reorder_level >= 0 AND reorder_level <= 1000000);

CREATE TABLE IF NOT EXISTS commerce_ai_rate_limits(
  key_hash TEXT PRIMARY KEY,
  window_id INTEGER NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_commerce_ai_rate_limits_updated
  ON commerce_ai_rate_limits(updated_at);

UPDATE commerce_meta SET value='10' WHERE key='schema_version';
