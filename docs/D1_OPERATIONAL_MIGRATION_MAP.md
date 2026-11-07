# B-SMART operational migration map to the existing Cloudflare D1 database

**Audit date:** 7 November 2026  
**Target database:** existing Cloudflare D1 `bsmart-commerce` (ID remains unchanged)  
**Target Worker:** `bsmart-commerce-api`  
**Policy:** additive migration only; preserve all current D1 rows and IDs.

## 1. Current state

The existing D1 database has schema version 8 and 22 application tables. Those tables implement the storefront/merchant/customer commerce slice only:

`commerce_cashbook`, `commerce_customer_accounts`, `commerce_customer_addresses`, `commerce_customer_cart_items`, `commerce_customer_login_attempts`, `commerce_customer_messages`, `commerce_customer_sessions`, `commerce_customer_wishlist_items`, `commerce_customers`, `commerce_inventory_movements`, `commerce_meta`, `commerce_order_lines`, `commerce_order_returns`, `commerce_orders`, `commerce_platform_admin_audit`, `commerce_product_reviews`, `commerce_products`, `commerce_stock_adjustments`, `commerce_stores`, `merchant_accounts`, `merchant_login_attempts`, `merchant_sessions`

The current D1 dataset contains 10 fictional demo stores / 259 demo products plus one retained CI test fixture and its test product. All 11 store rows are marked demo. The fixture is hidden from customer discovery by the alignment change, but its rows remain in D1.

The Render-hosted FastAPI runtime is **not connected to D1**. Its latest startup diagnostic reports SQLite, one organization, zero stores, four catalogue products and zero listed store products. The existing Render Postgres resource is not configured as the running service's database. The separate Cloudflare D1 database `bcs-written` is another application and is excluded from this migration.

## 2. Existing SQLAlchemy schema that must be ported

The current FastAPI code defines **78 operational tables** in `api/domain_models.py` and **36 platform-control tables** in `api/admin_models.py` (114 total). FastAPI currently registers **54 routers**. None of these model tables currently exists in the `bsmart-commerce` D1 database.

### Operational tables (78)

- `organizations` — Organization
- `organization_settings` — OrganizationSetting
- `reference_values` — ReferenceValue
- `outbound_messages` — OutboundMessage
- `users` — User
- `memberships` — Membership
- `branches` — Branch
- `membership_branches` — MembershipBranch
- `products` — Product
- `customers` — Customer
- `support_tickets` — SupportTicket
- `ticket_messages` — TicketMessage
- `leads` — Lead
- `lead_activities` — LeadActivity
- `feedback_entries` — Feedback
- `notifications` — Notification
- `attendance_records` — AttendanceRecord
- `leave_requests` — LeaveRequest
- `roster_shifts` — RosterShift
- `suppliers` — Supplier
- `stores` — Store
- `store_products` — StoreProduct
- `sales_orders` — SalesOrder
- `sync_operations` — SyncOperation
- `sales_order_items` — SalesOrderItem
- `sales_documents` — SalesDocument
- `sales_document_lines` — SalesDocumentLine
- `payments` — Payment
- `stock_movements` — StockMovement
- `batches` — Batch
- `batch_stock` — BatchStock
- `stock_count_lines` — StockCountLine
- `sale_item_batches` — SaleItemBatch
- `cash_closes` — CashClose
- `cash_movements` — CashMovement
- `inventory_balances` — InventoryBalance
- `expenses` — Expense
- `loyalty_rules` — LoyaltyRule
- `loyalty_entries` — LoyaltyEntry
- `sales_targets` — SalesTarget
- `commission_rules` — CommissionRule
- `commission_entries` — CommissionEntry
- `deliveries` — Delivery
- `cod_handovers` — CODHandover
- `staff_advances` — StaffAdvance
- `staff_advance_repayments` — StaffAdvanceRepayment
- `payroll_runs` — PayrollRun
- `payroll_lines` — PayrollLine
- `fiscal_periods` — FiscalPeriod
- `approval_rules` — ApprovalRule
- `purchase_orders` — PurchaseOrder
- `purchase_order_items` — PurchaseOrderItem
- `purchase_returns` — PurchaseReturn
- `purchase_return_items` — PurchaseReturnItem
- `ledger_entries` — LedgerEntry
- `accounts` — Account
- `journal_entries` — JournalEntry
- `journal_lines` — JournalLine
- `sales_returns` — SalesReturn
- `sales_return_items` — SalesReturnItem
- `refunds` — Refund
- `audit_logs` — AuditLog
- `import_batches` — ImportBatch
- `recommendations` — Recommendation
- `recommendation_decisions` — RecommendationDecision
- `recommendation_outcomes` — RecommendationOutcome
- `org_subscriptions` — OrgSubscription
- `org_invoices` — OrgInvoice
- `admin_conversations` — AdminConversation
- `admin_messages` — AdminMessage
- `store_customers` — StoreCustomer
- `store_messages` — StoreMessage
- `store_customer_addresses` — StoreCustomerAddress
- `store_customer_wishlist_items` — StoreCustomerWishlistItem
- `store_customer_cart_items` — StoreCustomerCartItem
- `store_coupons` — StoreCoupon
- `product_variants` — ProductVariant
- `product_reviews` — ProductReview

### Platform-control tables (36)

- `admin_mission_items` — AdminMissionItem
- `shift_handovers` — ShiftHandover
- `decision_journal` — DecisionJournal
- `tenant_state_events` — TenantStateEvent
- `plans` — Plan
- `org_plan_subscriptions` — OrgPlanSubscription
- `commercial_overrides` — CommercialOverride
- `usage_events` — UsageEvent
- `usage_aggregates` — UsageAggregate
- `billing_ledger_entries` — BillingLedgerEntry
- `collection_statements` — CollectionStatement
- `support_cases` — SupportCase
- `support_case_events` — SupportCaseEvent
- `support_sessions` — SupportSession
- `churn_risk_scores` — ChurnRiskScore
- `security_alerts` — SecurityAlert
- `jit_access_grants` — JitAccessGrant
- `access_certification_cycles` — AccessCertificationCycle
- `access_certification_items` — AccessCertificationItem
- `emergency_containment_events` — EmergencyContainmentEvent
- `incident_records` — IncidentRecord
- `incident_events` — IncidentEvent
- `job_records` — JobRecord
- `feature_rollout_configs` — FeatureRolloutConfig
- `config_versions` — ConfigVersion
- `provider_credentials` — ProviderCredential
- `webhook_events` — WebhookEvent
- `integration_certifications` — IntegrationCertification
- `data_inventory_items` — DataInventoryItem
- `tenant_data_export_requests` — TenantDataExportRequest
- `retention_policies` — RetentionPolicy
- `privacy_requests` — PrivacyRequest
- `model_registry_entries` — ModelRegistryEntry
- `ai_cost_budgets` — AiCostBudget
- `ai_kill_switches` — AiKillSwitch
- `model_outcome_records` — ModelOutcomeRecord

## 3. Porting phases

| Phase | Scope | D1 design requirement |
|---|---|---|
| 0 | Inventory, backup and source-of-truth freeze | Read-only audit, verified export, record counts, migration manifest |
| 1 | Identity and tenant foundation | Organizations, users, memberships, branches, permissions, sessions, settings |
| 2 | Product and inventory | Products, stock movements, balances, batches, expiry, counts, transfers |
| 3 | Sales and purchasing | POS, sales documents, payments, suppliers, purchase orders, purchase returns, delivery |
| 4 | Finance and workforce | Cash, receivables, expenses, journals, ledger, payroll, attendance, leave, approvals |
| 5 | Platform and integrations | Admin control-plane, subscriptions, usage, support, incidents, provider credentials, webhooks |
| 6 | Analytics and research | Imports, snapshots, recommendations, decisions, outcomes, model registry and audit |
| 7 | Cutover | Switch each module only after row-count, balance, tenant-isolation and concurrency tests pass |

## 4. Non-negotiable data rules

1. Keep the existing D1 database ID `887fa347-9c22-46b1-a7cf-91a7dbdfc311` and Worker binding `DB`.
2. Do not rename, truncate, reseed or repurpose existing `commerce_*` tables.
3. Keep current demo store, product, order, line, inventory and cashbook IDs stable.
4. Never import the unrelated `bcs-written` study-content database into B-SMART.
5. Do not treat the Render SQLite diagnostic's four catalogue products as a replacement for the 259 D1 demo products.
6. Do not point SQLAlchemy's `DATABASE_URL` at a D1 database ID. D1 is accessed through a Worker binding and requires Worker-native atomic batches for transactional writes.
7. Do not dual-write the same sale, stock movement or payment to SQLite and D1. One module has one authoritative writer at a time.
8. Every migrated tenant-owned row must carry and enforce its organization/branch ownership. Cross-tenant reads and writes must fail closed.
9. Each migration must be additive, idempotent where possible, tested on an isolated copy, and reconciled before cutover.
10. Keep old FastAPI routes in place until their D1 replacement passes API contract, permission, concurrency, rollback and data reconciliation tests.

## 5. Cutover acceptance checks

A module is not marked D1-backed merely because a table exists. Before switching its frontend route, verify:

- all model columns, unique constraints, foreign keys and check constraints have a reviewed D1 equivalent;
- create/read/update/delete operations preserve existing API contracts and tenant boundaries;
- transactional workflows use one D1 batch where required;
- duplicate requests are idempotent and concurrency races are tested;
- balances reconcile (stock ledger, receivables, cash, journals and payment states);
- exports and restore have been tested;
- production UI reads and writes only the selected authoritative D1 path;
- old SQLite data is either imported with provenance or explicitly confirmed as disposable/test-only.

**Current completion:** Phase 0 read-only inventory and integrity checks are complete. Phase 1–7 are not complete. Existing storefront D1 functionality remains live and separate from the legacy FastAPI operational modules.
