-- v12: Product gallery and store FAQ are merchant-authored content only.
-- Apply ONCE after 0011 on a verified backup/staging D1 database.
-- Arrays are JSON: product gallery max 4 HTTPS images and store FAQ max 6 Q&A.
ALTER TABLE commerce_products ADD COLUMN gallery_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(gallery_json) AND json_type(gallery_json)='array');
ALTER TABLE commerce_stores ADD COLUMN faq_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(faq_json) AND json_type(faq_json)='array');
UPDATE commerce_meta SET value='12' WHERE key='schema_version';
