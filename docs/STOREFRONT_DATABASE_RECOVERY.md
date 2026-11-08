# B-SMART operational data recovery and Cloudflare D1 alignment

> **Live audit: 8 November 2026.** The existing Cloudflare D1 database `bsmart-commerce` is live and must be preserved. Do not create a replacement database, seed over it or replay old migrations blindly.

## 1. Source-of-truth map

| Resource | Current verified role | Data boundary |
|---|---|---|
| Cloudflare D1 `bsmart-commerce` | Authoritative for D1 storefront, customer, merchant, catalogue, inventory and order workflows | Existing 22 application tables; schema version **12** |
| Cloudflare Worker `bsmart-commerce-api` | API for D1 commerce | Worker binding `DB` points to existing `bsmart-commerce` |
| Render `thesis` | Hosts React frontend and legacy FastAPI | Existing Render service; FastAPI still has separate SQLAlchemy database |
| Render Postgres `thesis-db` | Resource exists but is not verified as active source of legacy data | Do not assume it contains current records or switch the app to it without audit |
| Cloudflare D1 `bcs-written` | Separate study-content application database | Not B-SMART data; leave untouched |

The frontend currently has two data paths:
- Cloudflare Worker for D1 storefront, merchant and customer commerce IDs/slugs.
- FastAPI for legacy business login and original operational modules.

These systems are not synchronized. A D1 database ID is not a SQLAlchemy connection string.

## 2. Live D1 inventory

The existing D1 database was queried before and after the upgrade. Migrations 0009–0012 were applied sequentially after checking the live schema; `commerce_meta.schema_version=12`.

| Data | Preserved count/state |
|---|---:|
| Application tables | 22 |
| Store rows | 11 (10 seeded samples + 1 CI fixture) |
| Product rows | 260 |
| Orders / order lines | 3 / 3 |
| Inventory movement rows | 3 |
| Cashbook entries | 1 |
| Merchant accounts | 1 legacy CI account |
| Customer accounts | 0 |
| Verified real operational merchant stores | 0 |
| Public active stores / listed products | 0 / 0 |

All 11 stores remain inactive and marked `is_demo=1`. Existing rows have not been reset or deleted. Public visibility is intentionally disabled until genuine merchant-owned stores are verified and approved. None of the test orders or cashbook entries represents real revenue.

## 3. D1 backup and migration evidence

A D1 export job completed before the schema 9–12 changes. Export bookmark:
`00000051-00000000-0000511d-88b8dfddc66393a0b11aaa65163e45cd`.

This confirms an export operation completed; it does **not** prove that a full restore was tested. A restore drill into an isolated recovery database is still required before declaring disaster recovery complete.

The historical migrations were applied manually through Cloudflare API and may not be registered in Wrangler's `d1_migrations` table. Never blindly run `wrangler d1 migrations apply --remote`. Before a future migration, take an export, inspect live schema, apply only missing reviewed additive SQL, then verify columns, indexes, triggers and record counts.

## 4. Legacy FastAPI data boundary

The original FastAPI operational application still uses SQLAlchemy and its separate database configuration. Source code defines 78 operational model tables, 36 platform-control model tables and 54 registered routers. These include organization/user identity, branches, POS, batch/expiry stock, purchasing, suppliers, cash, payments, accounting journals, payroll, staff, CRM, receivables, approvals, audit, recommendations and platform administration.

The last recorded Render startup diagnostic reported SQLite with 1 organization, 0 stores, 4 catalogue products and 0 listed store products. That runtime database is not the Cloudflare D1 commerce database. The current GitHub tree contains no verified `bsmart.db` or SQLite backup file. An earlier user-provided ZIP was reported to contain only `bsmart.db-wal` and `bsmart.db-shm`, not the primary database file. No historical real merchant/customer/sales dataset can be recreated from the D1 sample catalogue.

**Required before legacy migration:** locate and verify the actual source database or a valid backup. If none exists, the owner must explicitly approve a clean-start migration that does not pretend historical records were preserved.

## 5. Safe Cloudflare-primary migration plan

1. Preserve the existing D1 database ID and `DB` binding.
2. Obtain the legacy source database and checksum it; inspect it read-only.
3. Inventory table schemas, foreign keys, tenant relationships, row counts and financial/stock balances.
4. Map the legacy SQLAlchemy schema into D1-native tables and Worker endpoints. Do not try to connect SQLAlchemy directly to a D1 database ID.
5. Migrate one bounded module at a time: identity/tenants → products/inventory → POS/sales → purchasing → finance → CRM/workforce → platform controls.
6. Test all writes as atomic D1 batches where required; test idempotency, concurrency, rollback and cross-tenant access.
7. Reconcile row counts, stock ledgers, receivables, cash, journals and audit history.
8. Switch one frontend module only after tests pass. Keep old routes available until cutover is verified.
9. Do not dual-write the same sale, stock movement or payment to SQLite and D1.
10. Verify export/restore before retiring the old database.

## 6. Current safe rollout boundary

- D1 storefront, customer, merchant, catalogue, inventory and order routes remain on the existing Worker.
- Inactive sample stores and the retained CI fixture remain preserved but hidden from public discovery.
- New merchant-owned stores remain private drafts until Platform Admin approval.
- Approved stores currently support COD/manual fulfilment only.
- Online payment gateways, courier integration and automated refunds are not enabled.
- The legacy FastAPI operational modules are not yet D1-backed; do not claim otherwise.
