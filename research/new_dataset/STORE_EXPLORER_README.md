# Restored research store explorer — 25 October 2026

The previous reset removed former built-in datasets and replaced the research UI with a blank / awaiting-import view. **This was a regression.** The new B-SMART dataset ZIP already contains **32 synthetic shops**, but their data had not been wired into the website.

## What is restored

- Frontend Research Portal now browses all **32 shops**, searches by name/ID/district and filters across **8 divisions**.
- For each shop it displays 2023–2025 synthetic revenue and orders, unique customer IDs, sales lines, units sold, purchase orders, stock movements, net stock ledger quantities, simulated unmet-demand events, one latest invoice example and top SKU example.
- API: `GET /api/research/portal/shops` and `GET /api/research/portal/shops/{shop_id}`, powered by committed `shops_overview.psv` and `shop_examples.psv`.
- Summaries were calculated from the **same integrated v1 ZIP**, then reconciled to **365,447 orders, 736,683 lines, 122,422 purchase orders, 994,808 movements** and exactly 32 shops.
- The page clearly shows that all stores and transactions are **100% synthetic**.

## What has NOT been restored or invented

- These are **aggregate previews**, not full invoice-, product-, customer- and lot-level data imported into the production operational database. Original ~61 MB ZIP remains user-downloadable; it is not in this repository and has not been uploaded to the server.
- The original operational tenant's persistent database is independent of the dataset code. A GitHub commit cannot restore rows lost due to Render's ephemeral SQLite, previous manual deletion or a prior unavailable backup.
- The seven earlier sector datasets or previous trained model weights have **not** been restored. They remain in the archival Git branch. Old ML accuracy figures remain retired.
- The new RQ1–RQ4 models have not been retrained, and this page does not display simulated RQ4 users as real people.

## Source and QA

Full synthetic source: `B-SMART_ALL_DATASETS_ONE_DOWNLOAD.zip` with checksum in `manifest.json`. Derivation used the `shops.csv`, `sales_orders.csv`, `sales_lines.csv`, `purchase_orders.csv`, `inventory_movements.csv`, `returns.csv`, `customers.csv` and `simulated_unmet_demand.csv` from that ZIP. Yearly totals in `shops_overview.psv` are rounded BDT for charting; lifetime totals retain decimals.

Run `pytest tests/test_research_store_catalogue.py` to verify shop-count, ID uniqueness, aggregate arithmetic and evidence-tier markings.

Full data browsing/searching, operational tenant import, pipeline training and durable Render persistence remain separate subsequent work.
