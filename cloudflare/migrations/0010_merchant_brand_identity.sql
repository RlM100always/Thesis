-- D1 v10: merchant brand identity, public contact (real merchants only).
-- Apply ONCE after v9 and successful backup/recovery checks.
ALTER TABLE commerce_stores ADD COLUMN logo_image_url TEXT;
ALTER TABLE commerce_stores ADD COLUMN cover_image_url TEXT;
ALTER TABLE commerce_stores ADD COLUMN public_phone TEXT;
ALTER TABLE commerce_stores ADD COLUMN public_address TEXT;
UPDATE commerce_meta SET value='10' WHERE key='schema_version';
