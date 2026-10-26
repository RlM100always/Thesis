-- Cloudflare runtime uses an isolated high-entropy access key, not plaintext passwords.
-- Legacy unused password_* fields remain for compatibility but are set to
-- ACCESS_KEY_ONLY / DISABLED; do not authenticate against those fields.
-- Apply once after 0003 on a NEW database; this has already been applied remotely.
ALTER TABLE merchant_accounts ADD COLUMN access_key_digest TEXT;
UPDATE commerce_meta SET value='4' WHERE key='schema_version';
