# B-SMART operational data recovery and Cloudflare D1 alignment

> **Live audit: 7 November 2026.** This document supersedes the earlier 26 October note that said no B-SMART D1 database existed. The existing Cloudflare D1 database `bsmart-commerce` is live and must be preserved. Do not create a replacement database, seed over it, or replay old migrations blindly.

## 1. Actual source-of-truth map

| Resource | Current verified role | Data boundary |
|---|---|---|
| Cloudflare D1 `bsmart-commerce` | **Authoritative for the D1 storefront and merchant/customer commerce slice** | 22 application tables; schema version 8 |
| Cloudflare Worker `bsmart-commerce-api` | API for the D1 storefront slice | Worker binding `DB` points to `bsmart-commerce` |
| Render service `thesis` | Hosts the React build and legacy FastAPI API | Latest startup log reports SQLite, not D1 |
| Render Postgres `thesis-db` | Existing but unused by the running website | Do not assume it contains the current application data; external query access is blocked |
| Cloudflare D1 `bcs-written` | Separate study-content application database | Not B-SMART commerce data; do not bind, merge, or migrate it into `bsmart-commerce` |

The frontend deliberately uses two data paths today:
- D1 Worker for D1 store IDs/slugs (`demo-bsmart-*`, `merchant-*`, `shop-*`).
- FastAPI for legacy tenant login and the original operational business modules.

These paths are not synchronized. Changing `DATABASE_URL` to a D1 database ID is not a valid migration.

## 2. Live `bsmart-commerce` data inventory

The live D1 database was queried read-only on 7 November 2026.

| Data | Count / state |
|---|---:|
| D1 application tables | 22 |
| Schema version (`commerce_meta`) | 8 |
| Seeded fictional demo stores | 10 |
| Seeded demo products | 259 |
| Retained POS CI test store | 1 |
| Product in the POS CI fixture | 1 |
| Total stores / products | 11 / 260 |
| Orders / order lines | 3 / 3 |
| Inventory movement rows | 3 |
| Cashbook entries | 1 |
| Merchant accounts | 1 legacy CI account |
| Customer accounts | 0 |
| Real merchant-owned operational stores | 0 |

All 11 store rows currently have `is_demo=1`. The three orders are demo/test records: two in the seeded grocery shop and one POS test order in the CI fixture. The single cashbook receipt belongs to that test POS order. None is verified real-world customer revenue or a real fulfilment obligation.

The known CI fixture has slug `shop-752c1d2b-b92`, area `Automated Test Only`, and name `POS CI Test Unverified Shop`. Keep its rows for audit/reconciliation, but exclude it from public customer discovery and checkout. The data-alignment branch adds that public visibility guard; it does not delete or rewrite the fixture rows.

### Integrity checks

The following read-only checks returned zero exceptions:
- orphan products, orders, order lines, inventory movements and cashbook entries;
- order subtotal/total mismatches against order lines;
- payment-state mismatches for the existing store/order types;
- negative product stock.

The checks do not prove that the sample catalogue is real business data. All seeded stores remain explicitly demo-only.

## 3. What is not yet in D1

The original FastAPI operational application still uses SQLAlchemy sessions and its own database configuration. Its source currently defines:
- 78 operational model tables in `api/domain_models.py`;
- 36 platform-control model tables in `api/admin_models.py`;
- 54 registered FastAPI routers.

Those modules include organization/user identity, branches, full POS, stock/batches/expiry, purchasing, supplier claims, cash, payments, accounting journals, payroll, staff, CRM, receivables, approvals, audit, recommendations, platform administration and related workflows. They have **not** been migrated to the current `bsmart-commerce` D1 schema.

The latest Render startup diagnostic (7 November 2026) reports:
```
db_backend=sqlite
organizations=1
stores=0
active_stores=0
catalog_products=4
listed_store_products=0
```

That is the current legacy FastAPI runtime database, not the Cloudflare D1 catalogue. The Render Postgres resource exists separately but is not the database used by the running service. Do not point the app at it or create another paid database as a shortcut.

The other D1 database, `bcs-written`, contains study-content tables (subjects, chapters, questions, rich blocks and related content). It is a different application dataset and must remain untouched.

## 4. Historical recovery boundary

The earlier uploaded `thesis.zip` did not contain the primary `bsmart.db` SQLite file; it contained only `bsmart.db-wal` and `bsmart.db-shm`. The earlier R2 check found setup metadata rather than a complete operational database snapshot. That history does not provide a verified restore of old real merchants, customers, sales or orders.

Do not manufacture historical records from demo catalogue data. If a separate trusted backup is later found, inventory it read-only first, verify its tenant ownership and dates, then plan a controlled import with provenance.

## 5. Safe D1 migration rules

1. **Keep the existing database ID and binding.** The current Worker `DB` binding must continue to point to `bsmart-commerce`.
2. **Back up before every schema/data write.** Use a D1 SQL export or a verified time-travel restore point. Record the bookmark and verify the export before migration.
3. **Inspect live schema before applying SQL.** The eight historical migrations were applied manually through the Cloudflare API; they were not registered in Wrangler's `d1_migrations` table.
4. **Never blindly run** `wrangler d1 migrations apply --remote` on this database. Replaying existing `ALTER TABLE` statements can fail or cause drift.
5. **Use additive, reviewed migrations.** Preserve existing IDs, slugs, product IDs, order IDs, stock quantities, order lines, audit rows and payment states.
6. **Port transactional workflows to Worker/D1-native batches.** Do not pretend a D1 database ID is a PostgreSQL URL or a drop-in SQLAlchemy connection. Checkout, stock movement, payment collection and accounting need tested atomic operations.
7. **Migrate one bounded module at a time.** Build the D1 schema and Worker endpoints, test against an isolated copy, compare row counts and totals, then switch that module's frontend API. Keep old FastAPI routes available until the new D1 path passes regression tests.
8. **Do not dual-write the same business event** to SQLite and D1. Choose one authoritative writer for each migrated module and record migration provenance.

## 6. Current safe rollout boundary

- D1 storefront, customer, merchant, catalogue, stock and order routes remain on the existing Worker.
- The known POS CI fixture is retained but hidden from public store discovery by the alignment change.
- Seeded `demo-bsmart-*` stores remain demo-only; do not promote them to real shops.
- New merchant-owned stores remain private drafts until Platform Admin approval.
- Approved stores support COD/manual fulfilment only. Online payment, courier API and automated refunds are not active.
- The full FastAPI operational modules remain a separate migration project; they must not be described as D1-backed until their data paths are actually ported and tested.
