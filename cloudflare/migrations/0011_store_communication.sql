-- D1 v11: merchant-owned information for transparent storefronts.
-- Content is descriptive only. Does NOT configure carrier, delivery charges,
-- order promises, refunds, or payment processing.
-- Apply ONCE after v10 with backup, staging verification and operator review.
ALTER TABLE commerce_stores ADD COLUMN announcement_text TEXT NOT NULL DEFAULT '';
ALTER TABLE commerce_stores ADD COLUMN about_text TEXT NOT NULL DEFAULT '';
ALTER TABLE commerce_stores ADD COLUMN delivery_policy_text TEXT NOT NULL DEFAULT '';
ALTER TABLE commerce_stores ADD COLUMN return_policy_text TEXT NOT NULL DEFAULT '';
UPDATE commerce_meta SET value='11' WHERE key='schema_version';
