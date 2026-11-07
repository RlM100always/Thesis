-- Generated from api.domain_models and api.admin_models.
-- Schema only: no business records, users, stores, orders or payments.
-- Model tables: 122. Existing commerce_* tables are not modified.
-- Safe to reapply: table and index DDL use IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS access_certification_cycles (
	id VARCHAR(36) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	initiated_by_id VARCHAR(36) NOT NULL, 
	due_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(initiated_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS access_certification_items (
	id VARCHAR(36) NOT NULL, 
	cycle_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	permission VARCHAR(100) NOT NULL, 
	reviewer_id VARCHAR(36), 
	decision VARCHAR(20), 
	decision_reason VARCHAR(300), 
	decided_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cycle_id) REFERENCES access_certification_cycles (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS accounts (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	type VARCHAR(20) NOT NULL, 
	is_system BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, code), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS admin_conversations (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	unread_by_admin INTEGER NOT NULL, 
	unread_by_business INTEGER NOT NULL, 
	last_message_at DATETIME, 
	last_message_preview VARCHAR(120), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);
CREATE TABLE IF NOT EXISTS admin_messages (
	id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	sender_type VARCHAR(10) NOT NULL, 
	sender_user_id VARCHAR(36), 
	content TEXT NOT NULL, 
	attachment_url VARCHAR(512), 
	attachment_name VARCHAR(260), 
	attachment_size INTEGER, 
	created_at DATETIME NOT NULL, 
	read_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES admin_conversations (id), 
	FOREIGN KEY(sender_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS admin_mission_items (
	id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	priority INTEGER NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	description TEXT, 
	affected_org_id VARCHAR(36), 
	affected_user_id VARCHAR(36), 
	owner_admin_id VARCHAR(36), 
	estimated_impact VARCHAR(200), 
	recommended_action TEXT, 
	status VARCHAR(20) NOT NULL, 
	deadline_at DATETIME, 
	resolved_at DATETIME, 
	resolved_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(affected_org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(affected_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_admin_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(resolved_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS ai_cost_budgets (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	feature VARCHAR(80) NOT NULL, 
	monthly_token_limit INTEGER, 
	monthly_cost_limit_bdt NUMERIC(14, 2), 
	on_breach VARCHAR(30) NOT NULL, 
	created_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, feature), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS ai_kill_switches (
	id VARCHAR(36) NOT NULL, 
	feature VARCHAR(80) NOT NULL, 
	disabled BOOLEAN NOT NULL, 
	reason VARCHAR(300), 
	requires_human_approval_above_risk NUMERIC(5, 2), 
	disabled_by_id VARCHAR(36), 
	disabled_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (feature), 
	FOREIGN KEY(disabled_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS approval_requests (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	payload TEXT NOT NULL, 
	requested_by_user_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	decided_by_user_id VARCHAR(36), 
	decided_at DATETIME, 
	decision_reason VARCHAR(300), 
	result_reference_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by_user_id) REFERENCES users (id), 
	FOREIGN KEY(decided_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS approval_rules (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	threshold NUMERIC(14, 2) NOT NULL, 
	approver_role VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, kind), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS attendance_records (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	user_id VARCHAR(36) NOT NULL, 
	check_in_at DATETIME NOT NULL, 
	check_out_at DATETIME, 
	source VARCHAR(20) NOT NULL, 
	corrects_record_id VARCHAR(36), 
	note VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(corrects_record_id) REFERENCES attendance_records (id)
);
CREATE TABLE IF NOT EXISTS audit_logs (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	actor_user_id VARCHAR(36), 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id VARCHAR(36), 
	metadata_json TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS batch_stock (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (branch_id, batch_id), 
	CHECK (quantity >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(batch_id) REFERENCES batches (id)
);
CREATE TABLE IF NOT EXISTS batches (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	batch_no VARCHAR(80) NOT NULL, 
	expiry_date DATE, 
	unit_cost NUMERIC(14, 2), 
	supplier_id VARCHAR(36), 
	received_at DATETIME NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	status_reason VARCHAR(160), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, product_id, batch_no), 
	CONSTRAINT ck_batch_status CHECK (status in ('active','blocked')), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);
CREATE TABLE IF NOT EXISTS billing_ledger_entries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	entry_type VARCHAR(30) NOT NULL, 
	amount_bdt NUMERIC(14, 2) NOT NULL, 
	description VARCHAR(300) NOT NULL, 
	reference_id VARCHAR(36), 
	period_month VARCHAR(7), 
	due_at DATETIME, 
	paid_at DATETIME, 
	status VARCHAR(20) NOT NULL, 
	created_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS branches (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	division VARCHAR(30), 
	district VARCHAR(50), 
	address TEXT, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, code), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS cash_closes (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	business_date DATE NOT NULL, 
	opening_cash NUMERIC(14, 2) NOT NULL, 
	expected_cash NUMERIC(14, 2) NOT NULL, 
	counted_cash NUMERIC(14, 2) NOT NULL, 
	variance NUMERIC(14, 2) NOT NULL, 
	breakdown_json TEXT, 
	note VARCHAR(300), 
	closed_by VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, branch_id, business_date), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);
CREATE TABLE IF NOT EXISTS cash_movements (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	shift_id VARCHAR(36) NOT NULL, 
	direction VARCHAR(10) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	reason VARCHAR(200) NOT NULL, 
	created_by VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount > 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(shift_id) REFERENCES cashier_shifts (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS cashier_shifts (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	drawer_label VARCHAR(60), 
	status VARCHAR(10) NOT NULL, 
	opening_cash NUMERIC(14, 2) NOT NULL, 
	opened_at DATETIME NOT NULL, 
	expected_cash NUMERIC(14, 2), 
	counted_cash NUMERIC(14, 2), 
	variance NUMERIC(14, 2), 
	note VARCHAR(300), 
	closed_at DATETIME, 
	closed_by VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS churn_risk_scores (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	score NUMERIC(5, 2) NOT NULL, 
	factors_json TEXT NOT NULL, 
	risk_level VARCHAR(20) NOT NULL, 
	recovery_owner_id VARCHAR(36), 
	computed_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(recovery_owner_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS cod_handovers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	delivery_id VARCHAR(36) NOT NULL, 
	shift_id VARCHAR(36) NOT NULL, 
	handed_over_amount NUMERIC(14, 2) NOT NULL, 
	shortage_amount NUMERIC(14, 2) NOT NULL, 
	received_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (delivery_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(delivery_id) REFERENCES deliveries (id) ON DELETE CASCADE, 
	FOREIGN KEY(shift_id) REFERENCES cashier_shifts (id), 
	FOREIGN KEY(received_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS collection_statements (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	reference VARCHAR(100) NOT NULL, 
	amount_bdt NUMERIC(14, 2) NOT NULL, 
	received_at DATETIME NOT NULL, 
	organization_id VARCHAR(36), 
	matched_invoice_id VARCHAR(36), 
	status VARCHAR(20) NOT NULL, 
	notes VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS commercial_overrides (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	description VARCHAR(300) NOT NULL, 
	value_json TEXT NOT NULL, 
	granted_by_id VARCHAR(36) NOT NULL, 
	expires_at DATETIME, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(granted_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS commission_entries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	sales_order_id VARCHAR(36) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	reason VARCHAR(20) NOT NULL, 
	occurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount <> 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(sales_order_id) REFERENCES sales_orders (id)
);
CREATE TABLE IF NOT EXISTS commission_rules (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	rate_percent NUMERIC(5, 2) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS config_versions (
	id VARCHAR(36) NOT NULL, 
	config_key VARCHAR(100) NOT NULL, 
	version INTEGER NOT NULL, 
	value_json TEXT NOT NULL, 
	previous_value_json TEXT, 
	diff_summary TEXT, 
	deployed_at DATETIME, 
	approved_by_id VARCHAR(36), 
	created_by_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS customers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	display_name VARCHAR(160), 
	phone_hash VARCHAR(128), 
	marketing_consent BOOLEAN NOT NULL, 
	credit_limit NUMERIC(14, 2), 
	price_tier VARCHAR(20) DEFAULT 'retail' NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, code), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS data_inventory_items (
	id VARCHAR(36) NOT NULL, 
	module VARCHAR(60) NOT NULL, 
	data_category VARCHAR(40) NOT NULL, 
	description VARCHAR(300) NOT NULL, 
	table_name VARCHAR(80), 
	legal_basis VARCHAR(100), 
	retention_days INTEGER, 
	last_reviewed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS decision_journal (
	id VARCHAR(36) NOT NULL, 
	actor_admin_id VARCHAR(36) NOT NULL, 
	action_kind VARCHAR(60) NOT NULL, 
	affected_org_id VARCHAR(36), 
	decision_reason TEXT NOT NULL, 
	evidence_url VARCHAR(500), 
	approver_id VARCHAR(36), 
	expected_outcome TEXT, 
	correlation_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_admin_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(affected_org_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	FOREIGN KEY(approver_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	sales_order_id VARCHAR(36) NOT NULL, 
	rider_user_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	cod_amount_expected NUMERIC(14, 2) NOT NULL, 
	cod_amount_collected NUMERIC(14, 2), 
	proof_note VARCHAR(300), 
	failure_reason VARCHAR(300), 
	delivered_at DATETIME, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(sales_order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(rider_user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS emergency_containment_events (
	id VARCHAR(36) NOT NULL, 
	actor_id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	actions_taken_json TEXT NOT NULL, 
	reason VARCHAR(300) NOT NULL, 
	reversed_at DATETIME, 
	reversed_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	FOREIGN KEY(reversed_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS expenses (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	category VARCHAR(80) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	payment_method VARCHAR(30) NOT NULL, 
	note TEXT, 
	incurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount > 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);
CREATE TABLE IF NOT EXISTS feature_rollout_configs (
	id VARCHAR(36) NOT NULL, 
	feature_key VARCHAR(60) NOT NULL, 
	current_stage VARCHAR(30) NOT NULL, 
	stages_json TEXT NOT NULL, 
	guardrail_error_threshold NUMERIC(5, 2), 
	guardrail_ticket_threshold INTEGER, 
	auto_rollback_enabled BOOLEAN NOT NULL, 
	rollback_count INTEGER NOT NULL, 
	last_rollback_at DATETIME, 
	created_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (feature_key), 
	FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS feedback_entries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36), 
	sales_order_id VARCHAR(36), 
	score INTEGER NOT NULL, 
	comment TEXT, 
	follow_up_ticket_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (score >= 0 AND score <= 10), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(sales_order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(follow_up_ticket_id) REFERENCES support_tickets (id)
);
CREATE TABLE IF NOT EXISTS fiscal_periods (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	period_month DATE NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	closed_by_user_id VARCHAR(36) NOT NULL, 
	closed_at DATETIME NOT NULL, 
	reopened_by_user_id VARCHAR(36), 
	reopened_at DATETIME, 
	reopen_reason VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, period_month), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(closed_by_user_id) REFERENCES users (id), 
	FOREIGN KEY(reopened_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS import_batches (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	uploaded_by VARCHAR(36) NOT NULL, 
	original_filename VARCHAR(255) NOT NULL, 
	stored_path TEXT NOT NULL, 
	checksum_sha256 VARCHAR(64) NOT NULL, 
	source_system VARCHAR(80) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	row_count INTEGER NOT NULL, 
	mapping_json TEXT, 
	validation_json TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, checksum_sha256), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploaded_by) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS incident_events (
	id VARCHAR(36) NOT NULL, 
	incident_id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(30) NOT NULL, 
	actor_id VARCHAR(36), 
	body TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(incident_id) REFERENCES incident_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS incident_records (
	id VARCHAR(36) NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	commander_id VARCHAR(36), 
	status VARCHAR(20) NOT NULL, 
	affected_features_json TEXT, 
	affected_org_count INTEGER NOT NULL, 
	mitigation TEXT, 
	root_cause TEXT, 
	customer_communication TEXT, 
	resolved_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(commander_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS integration_certifications (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	integration VARCHAR(40) NOT NULL, 
	sandbox_tested BOOLEAN NOT NULL, 
	callback_validated BOOLEAN NOT NULL, 
	refund_tested BOOLEAN NOT NULL, 
	credential_verified BOOLEAN NOT NULL, 
	certified_at DATETIME, 
	certified_by_id VARCHAR(36), 
	notes VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(certified_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS inventory_balances (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, branch_id, product_id), 
	CHECK (quantity >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS jit_access_grants (
	id VARCHAR(36) NOT NULL, 
	grantee_id VARCHAR(36) NOT NULL, 
	granted_by_id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	permission VARCHAR(100) NOT NULL, 
	reason VARCHAR(300) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	revoked_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(grantee_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(granted_by_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(revoked_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS job_records (
	id VARCHAR(36) NOT NULL, 
	job_type VARCHAR(60) NOT NULL, 
	organization_id VARCHAR(36), 
	status VARCHAR(20) NOT NULL, 
	payload_json TEXT, 
	result_json TEXT, 
	error TEXT, 
	attempt_count INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	idempotency_key VARCHAR(100), 
	started_at DATETIME, 
	completed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	UNIQUE (idempotency_key)
);
CREATE TABLE IF NOT EXISTS journal_entries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	occurred_at DATETIME NOT NULL, 
	memo VARCHAR(200), 
	reference_type VARCHAR(30) NOT NULL, 
	reference_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);
CREATE TABLE IF NOT EXISTS journal_lines (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	journal_entry_id VARCHAR(36) NOT NULL, 
	account_id VARCHAR(36) NOT NULL, 
	debit NUMERIC(14, 2) NOT NULL, 
	credit NUMERIC(14, 2) NOT NULL, 
	party_type VARCHAR(20), 
	party_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (debit >= 0 AND credit >= 0), 
	CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE, 
	FOREIGN KEY(account_id) REFERENCES accounts (id)
);
CREATE TABLE IF NOT EXISTS lead_activities (
	id VARCHAR(36) NOT NULL, 
	lead_id VARCHAR(36) NOT NULL, 
	author_user_id VARCHAR(36) NOT NULL, 
	note TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS leads (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	phone_hash VARCHAR(128), 
	source VARCHAR(60), 
	stage VARCHAR(20) NOT NULL, 
	estimated_value NUMERIC(14, 2), 
	owner_user_id VARCHAR(36), 
	lost_reason VARCHAR(200), 
	converted_customer_id VARCHAR(36), 
	closed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id), 
	FOREIGN KEY(converted_customer_id) REFERENCES customers (id)
);
CREATE TABLE IF NOT EXISTS leave_requests (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	leave_type VARCHAR(30) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	reason VARCHAR(300), 
	status VARCHAR(20) NOT NULL, 
	decided_by_user_id VARCHAR(36), 
	decided_at DATETIME, 
	decision_reason VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (end_date >= start_date), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(decided_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS ledger_entries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	ledger_type VARCHAR(20) NOT NULL, 
	party_type VARCHAR(20), 
	party_id VARCHAR(36), 
	category VARCHAR(80), 
	amount_delta NUMERIC(14, 2) NOT NULL, 
	payment_method VARCHAR(30), 
	reference_type VARCHAR(30) NOT NULL, 
	reference_id VARCHAR(36) NOT NULL, 
	note TEXT, 
	occurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_delta <> 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);
CREATE TABLE IF NOT EXISTS loyalty_entries (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	points_delta NUMERIC(14, 3) NOT NULL, 
	reason VARCHAR(20) NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id VARCHAR(36), 
	occurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (points_delta <> 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);
CREATE TABLE IF NOT EXISTS loyalty_rules (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	points_per_taka NUMERIC(14, 2) NOT NULL, 
	redemption_value NUMERIC(14, 4) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS membership_branches (
	id VARCHAR(36) NOT NULL, 
	membership_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (membership_id, branch_id), 
	FOREIGN KEY(membership_id) REFERENCES memberships (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS memberships (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	base_salary NUMERIC(14, 2), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, user_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_outcome_records (
	id VARCHAR(36) NOT NULL, 
	feature VARCHAR(80) NOT NULL, 
	vertical VARCHAR(40) NOT NULL, 
	organization_id VARCHAR(36), 
	recommendation_id VARCHAR(36), 
	outcome VARCHAR(20) NOT NULL, 
	accepted BOOLEAN, 
	financial_impact_bdt NUMERIC(14, 2), 
	notes VARCHAR(300), 
	recorded_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS model_registry_entries (
	id VARCHAR(36) NOT NULL, 
	feature VARCHAR(80) NOT NULL, 
	model_id VARCHAR(100) NOT NULL, 
	prompt_version VARCHAR(40), 
	knowledge_source VARCHAR(200), 
	fallback_behavior VARCHAR(100), 
	deployed_at DATETIME, 
	deprecated_at DATETIME, 
	deployed_by_id VARCHAR(36), 
	is_active BOOLEAN NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deployed_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS notifications (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	recipient_user_id VARCHAR(36) NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body TEXT, 
	link_type VARCHAR(30), 
	link_id VARCHAR(36), 
	read_at DATETIME, 
	snoozed_until DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS org_invoices (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	subscription_id VARCHAR(36), 
	amount_bdt NUMERIC(12, 2) NOT NULL, 
	period_label VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	due_date DATETIME, 
	paid_at DATETIME, 
	notes VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(subscription_id) REFERENCES org_subscriptions (id)
);
CREATE TABLE IF NOT EXISTS org_plan_subscriptions (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	started_at DATETIME NOT NULL, 
	ends_at DATETIME, 
	status VARCHAR(20) NOT NULL, 
	granted_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT, 
	FOREIGN KEY(granted_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS org_subscriptions (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	plan_code VARCHAR(40) NOT NULL, 
	plan_name VARCHAR(80) NOT NULL, 
	price_bdt NUMERIC(12, 2) NOT NULL, 
	billing_cycle VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	trial_ends_at DATETIME, 
	current_period_start DATETIME, 
	current_period_end DATETIME, 
	assigned_by_user_id VARCHAR(36), 
	notes VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(assigned_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS organization_settings (
	organization_id VARCHAR(36) NOT NULL, 
	business_mode VARCHAR(20) NOT NULL, 
	payment_methods_json TEXT NOT NULL, 
	sales_channels_json TEXT NOT NULL, 
	reorder_budget_bdt NUMERIC(14, 2), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (organization_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS organizations (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	sector VARCHAR(40) NOT NULL, 
	size_class VARCHAR(20), 
	currency VARCHAR(3) NOT NULL, 
	timezone VARCHAR(40) NOT NULL, 
	locale VARCHAR(10) NOT NULL, 
	address VARCHAR(300), 
	phone VARCHAR(30), 
	vat_reg_no VARCHAR(40), 
	receipt_footer VARCHAR(200), 
	active BOOLEAN NOT NULL, 
	suspended_at DATETIME, 
	suspended_reason VARCHAR(300), 
	feature_flags_json TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS outbound_messages (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	recipient VARCHAR(40) NOT NULL, 
	template VARCHAR(80) NOT NULL, 
	body TEXT NOT NULL, 
	idempotency_key VARCHAR(100) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	provider_message_id VARCHAR(160), 
	last_error VARCHAR(500), 
	requested_by_user_id VARCHAR(36) NOT NULL, 
	sent_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, idempotency_key), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS payments (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36) NOT NULL, 
	method VARCHAR(30) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	reference VARCHAR(120), 
	status VARCHAR(20) NOT NULL, 
	paid_at DATETIME NOT NULL, 
	shift_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount > 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(shift_id) REFERENCES cashier_shifts (id)
);
CREATE TABLE IF NOT EXISTS payroll_lines (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	payroll_run_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	base_salary NUMERIC(14, 2) NOT NULL, 
	commission_amount NUMERIC(14, 2) NOT NULL, 
	advance_deduction NUMERIC(14, 2) NOT NULL, 
	net_pay NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (payroll_run_id, user_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS payroll_runs (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	approved_by_user_id VARCHAR(36), 
	approved_at DATETIME, 
	paid_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, period_start, period_end), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id), 
	FOREIGN KEY(approved_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS plans (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	price_bdt NUMERIC(14, 2) NOT NULL, 
	billing_cycle VARCHAR(20) NOT NULL, 
	branch_limit INTEGER, 
	employee_limit INTEGER, 
	transaction_limit INTEGER, 
	ai_token_quota INTEGER, 
	sms_quota INTEGER, 
	whatsapp_quota INTEGER, 
	support_tier VARCHAR(20) NOT NULL, 
	modules_json TEXT, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS privacy_requests (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	request_type VARCHAR(30) NOT NULL, 
	subject_email VARCHAR(254) NOT NULL, 
	description TEXT, 
	status VARCHAR(20) NOT NULL, 
	assigned_to_id VARCHAR(36), 
	verification_completed BOOLEAN NOT NULL, 
	evidence_url VARCHAR(500), 
	due_at DATETIME, 
	completed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS product_reviews (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	store_customer_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36), 
	rating INTEGER NOT NULL, 
	comment VARCHAR(1000), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, product_id, store_customer_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(store_customer_id) REFERENCES store_customers (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS product_variants (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	options TEXT NOT NULL, 
	price_deltas TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS products (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	sku VARCHAR(80) NOT NULL, 
	barcode VARCHAR(80), 
	name VARCHAR(200) NOT NULL, 
	category VARCHAR(100), 
	unit VARCHAR(20) NOT NULL, 
	selling_price NUMERIC(14, 2) NOT NULL, 
	cost_price NUMERIC(14, 2) NOT NULL, 
	reorder_level NUMERIC(14, 3) NOT NULL, 
	wholesale_price NUMERIC(14, 2), 
	track_expiry BOOLEAN DEFAULT 0 NOT NULL, 
	active BOOLEAN NOT NULL, 
	stock_alert_threshold INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, sku), 
	CHECK (selling_price >= 0), 
	CHECK (cost_price >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS provider_credentials (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(40) NOT NULL, 
	credential_name VARCHAR(100) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	expires_at DATETIME, 
	last_rotated_at DATETIME, 
	rotated_by_id VARCHAR(36), 
	notes VARCHAR(300), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(rotated_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS purchase_order_items (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	purchase_order_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	received_quantity NUMERIC(14, 3) NOT NULL, 
	unit_cost NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0 AND unit_cost >= 0), 
	CHECK (received_quantity >= 0 AND received_quantity <= quantity), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS purchase_orders (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	supplier_id VARCHAR(36) NOT NULL, 
	order_number VARCHAR(80) NOT NULL, 
	ordered_at DATETIME NOT NULL, 
	expected_at DATETIME, 
	status VARCHAR(20) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, order_number), 
	CHECK (total >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);
CREATE TABLE IF NOT EXISTS purchase_return_items (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	purchase_return_id VARCHAR(36) NOT NULL, 
	purchase_order_item_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	quantity NUMERIC(14, 3) NOT NULL, 
	unit_cost NUMERIC(14, 2) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0 AND unit_cost >= 0 AND amount >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(purchase_return_id) REFERENCES purchase_returns (id) ON DELETE CASCADE, 
	FOREIGN KEY(purchase_order_item_id) REFERENCES purchase_order_items (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(batch_id) REFERENCES batches (id)
);
CREATE TABLE IF NOT EXISTS purchase_returns (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	purchase_order_id VARCHAR(36) NOT NULL, 
	supplier_id VARCHAR(36) NOT NULL, 
	return_number VARCHAR(80) NOT NULL, 
	claim_type VARCHAR(30) NOT NULL, 
	reason VARCHAR(300) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	submitted_at DATETIME NOT NULL, 
	dispatched_at DATETIME, 
	settled_at DATETIME, 
	credit_note_number VARCHAR(100), 
	supplier_note TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, return_number), 
	UNIQUE (organization_id, supplier_id, credit_note_number), 
	CHECK (total >= 0), 
	CONSTRAINT ck_purchase_return_status CHECK (status in ('submitted','dispatched','settled','rejected')), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);
CREATE TABLE IF NOT EXISTS recommendation_decisions (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	recommendation_id VARCHAR(36) NOT NULL, 
	decided_by VARCHAR(36), 
	decision VARCHAR(20) NOT NULL, 
	modified_quantity INTEGER, 
	defer_until VARCHAR(10), 
	note TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_decision CHECK (decision in ('accept','reject','modify','defer')), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(recommendation_id) REFERENCES recommendations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS recommendation_outcomes (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	recommendation_id VARCHAR(36) NOT NULL, 
	observed_at DATETIME NOT NULL, 
	observation_window_days INTEGER NOT NULL, 
	action_taken BOOLEAN, 
	stockout_days_before INTEGER, 
	stockout_days_after INTEGER, 
	holding_cost_before_bdt NUMERIC(14, 2), 
	holding_cost_after_bdt NUMERIC(14, 2), 
	expired_value_bdt NUMERIC(14, 2), 
	customer_responded BOOLEAN, 
	predicted_quantity INTEGER, 
	realised_quantity INTEGER, 
	realised_benefit_bdt NUMERIC(14, 2), 
	drift_flag BOOLEAN NOT NULL, 
	note TEXT, 
	measured_by VARCHAR(12) DEFAULT 'manual' NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(recommendation_id) REFERENCES recommendations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS recommendations (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	run_id VARCHAR(36) NOT NULL, 
	cutoff_date VARCHAR(10) NOT NULL, 
	rank_in_rt INTEGER NOT NULL, 
	action_type VARCHAR(20) NOT NULL, 
	target_sku VARCHAR(160), 
	target_customer_id VARCHAR(64), 
	division VARCHAR(60), 
	quantity INTEGER, 
	benefit_bdt NUMERIC(14, 2) NOT NULL, 
	action_cost_bdt NUMERIC(14, 2) NOT NULL, 
	risk_bdt NUMERIC(14, 2) NOT NULL, 
	utility_bdt NUMERIC(14, 2) NOT NULL, 
	confidence VARCHAR(20) NOT NULL, 
	feasible BOOLEAN NOT NULL, 
	infeasible_reason TEXT, 
	reason TEXT, 
	explanation_json TEXT, 
	model_version VARCHAR(80), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_reco_type CHECK (action_type in ('reorder','expiry','retention')), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS reference_values (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	parent_code VARCHAR(50), 
	label_en VARCHAR(120) NOT NULL, 
	label_bn VARCHAR(120) NOT NULL, 
	details VARCHAR(240), 
	source_url VARCHAR(500) NOT NULL, 
	verified_on DATE NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (kind, code)
);
CREATE TABLE IF NOT EXISTS refunds (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	sales_return_id VARCHAR(36) NOT NULL, 
	method VARCHAR(30) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	reference VARCHAR(120), 
	refunded_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount > 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(sales_return_id) REFERENCES sales_returns (id)
);
CREATE TABLE IF NOT EXISTS reservations (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	sales_document_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(sales_document_id) REFERENCES sales_documents (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS retention_policies (
	id VARCHAR(36) NOT NULL, 
	data_category VARCHAR(60) NOT NULL, 
	retention_days INTEGER NOT NULL, 
	action_on_expiry VARCHAR(20) NOT NULL, 
	requires_approval BOOLEAN NOT NULL, 
	legal_hold_override BOOLEAN NOT NULL, 
	notes VARCHAR(300), 
	created_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (data_category), 
	FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS roster_shifts (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	shift_date DATE NOT NULL, 
	start_time VARCHAR(5) NOT NULL, 
	end_time VARCHAR(5) NOT NULL, 
	station VARCHAR(60), 
	created_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (end_time > start_time), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS sale_item_batches (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	sales_order_item_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	returned_quantity NUMERIC(14, 3) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(sales_order_item_id) REFERENCES sales_order_items (id) ON DELETE CASCADE, 
	FOREIGN KEY(batch_id) REFERENCES batches (id)
);
CREATE TABLE IF NOT EXISTS sales_document_lines (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	unit_price NUMERIC(14, 2) NOT NULL, 
	discount_amount NUMERIC(14, 2) NOT NULL, 
	line_total NUMERIC(14, 2) NOT NULL, 
	variant_label VARCHAR(100), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0 AND unit_price >= 0 AND discount_amount >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(document_id) REFERENCES sales_documents (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS sales_documents (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36), 
	document_type VARCHAR(20) NOT NULL, 
	document_number VARCHAR(80) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	channel VARCHAR(30) NOT NULL, 
	issued_at DATETIME NOT NULL, 
	valid_until DATE, 
	expected_delivery_at DATETIME, 
	notes TEXT, 
	subtotal NUMERIC(14, 2) NOT NULL, 
	discount_amount NUMERIC(14, 2) NOT NULL, 
	tax_amount NUMERIC(14, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	invoice_id VARCHAR(36), 
	shipping_name VARCHAR(160), 
	shipping_phone VARCHAR(32), 
	shipping_address TEXT, 
	access_token VARCHAR(64), 
	store_customer_id VARCHAR(36), 
	delivery_fee NUMERIC(14, 2) NOT NULL, 
	payment_status VARCHAR(20) NOT NULL, 
	payment_screenshot_url TEXT, 
	status_note VARCHAR(500), 
	coupon_code VARCHAR(50), 
	coupon_discount NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, document_number), 
	CONSTRAINT ck_sales_document_type CHECK (document_type in ('quotation','order')), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(invoice_id) REFERENCES sales_orders (id)
);
CREATE TABLE IF NOT EXISTS sales_order_items (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	unit_price NUMERIC(14, 2) NOT NULL, 
	unit_cost_at_sale NUMERIC(14, 2) NOT NULL, 
	discount_amount NUMERIC(14, 2) NOT NULL, 
	line_total NUMERIC(14, 2) NOT NULL, 
	returned_quantity NUMERIC(14, 3) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0), 
	CHECK (unit_price >= 0 AND discount_amount >= 0 AND line_total >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(order_id) REFERENCES sales_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS sales_orders (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36), 
	invoice_number VARCHAR(80) NOT NULL, 
	sold_at DATETIME NOT NULL, 
	channel VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	subtotal NUMERIC(14, 2) NOT NULL, 
	discount_amount NUMERIC(14, 2) NOT NULL, 
	tax_amount NUMERIC(14, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, invoice_number), 
	CHECK (subtotal >= 0 AND discount_amount >= 0 AND tax_amount >= 0 AND total >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);
CREATE TABLE IF NOT EXISTS sales_return_items (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	sales_return_id VARCHAR(36) NOT NULL, 
	sales_order_item_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	restock BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0 AND amount >= 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(sales_return_id) REFERENCES sales_returns (id) ON DELETE CASCADE, 
	FOREIGN KEY(sales_order_item_id) REFERENCES sales_order_items (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS sales_returns (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	sales_order_id VARCHAR(36) NOT NULL, 
	return_number VARCHAR(80) NOT NULL, 
	reason VARCHAR(160) NOT NULL, 
	returned_at DATETIME NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, return_number), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(sales_order_id) REFERENCES sales_orders (id)
);
CREATE TABLE IF NOT EXISTS sales_targets (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	target_amount NUMERIC(14, 2) NOT NULL, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, user_id, period_start), 
	CHECK (period_end >= period_start), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS security_alerts (
	id VARCHAR(36) NOT NULL, 
	alert_type VARCHAR(50) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	organization_id VARCHAR(36), 
	user_id VARCHAR(36), 
	evidence_json TEXT, 
	status VARCHAR(20) NOT NULL, 
	resolved_by_id VARCHAR(36), 
	response_action VARCHAR(200), 
	resolved_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(resolved_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS shift_handovers (
	id VARCHAR(36) NOT NULL, 
	from_admin_id VARCHAR(36) NOT NULL, 
	to_admin_id VARCHAR(36), 
	summary TEXT NOT NULL, 
	open_incidents INTEGER NOT NULL, 
	pending_approvals INTEGER NOT NULL, 
	priority_org_ids_json TEXT, 
	acknowledged_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(from_admin_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(to_admin_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS site_content (
	"key" VARCHAR(80) NOT NULL, 
	value_json TEXT NOT NULL, 
	updated_by_user_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY ("key"), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS staff_advance_repayments (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	advance_id VARCHAR(36) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	occurred_at DATETIME NOT NULL, 
	recorded_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount > 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(advance_id) REFERENCES staff_advances (id) ON DELETE CASCADE, 
	FOREIGN KEY(recorded_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS staff_advances (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	reason VARCHAR(300), 
	status VARCHAR(20) NOT NULL, 
	issued_at DATETIME NOT NULL, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS stock_count_lines (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	stock_count_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	system_qty NUMERIC(14, 3) NOT NULL, 
	counted_qty NUMERIC(14, 3), 
	counted_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (stock_count_id, product_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(stock_count_id) REFERENCES stock_counts (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
CREATE TABLE IF NOT EXISTS stock_counts (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	note VARCHAR(300), 
	started_by_user_id VARCHAR(36) NOT NULL, 
	started_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(started_by_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS stock_movements (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	movement_type VARCHAR(30) NOT NULL, 
	quantity_delta NUMERIC(14, 3) NOT NULL, 
	unit_cost NUMERIC(14, 2), 
	reference_type VARCHAR(30), 
	reference_id VARCHAR(36), 
	batch_id VARCHAR(36), 
	occurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity_delta <> 0), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(batch_id) REFERENCES batches (id)
);
CREATE TABLE IF NOT EXISTS store_coupons (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	discount_type VARCHAR(10) NOT NULL, 
	discount_value NUMERIC(14, 2) NOT NULL, 
	min_order_bdt NUMERIC(14, 2) NOT NULL, 
	max_uses INTEGER, 
	used_count INTEGER NOT NULL, 
	valid_from DATETIME, 
	valid_to DATETIME, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, code), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS store_customer_addresses (
	id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	label VARCHAR(40) NOT NULL, 
	recipient_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	division VARCHAR(50) NOT NULL, 
	district VARCHAR(50) NOT NULL, 
	thana VARCHAR(80), 
	address_detail VARCHAR(400) NOT NULL, 
	postal_code VARCHAR(12), 
	is_default BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES store_customers (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS store_customer_cart_items (
	id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	quantity INTEGER NOT NULL, 
	variant_label VARCHAR(100), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_sc_cart_product UNIQUE (customer_id, store_id, product_id), 
	CONSTRAINT ck_sc_cart_quantity CHECK (quantity >= 1 AND quantity <= 99), 
	FOREIGN KEY(customer_id) REFERENCES store_customers (id) ON DELETE CASCADE, 
	FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS store_customer_wishlist_items (
	id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_sc_wishlist_product UNIQUE (customer_id, store_id, product_id), 
	FOREIGN KEY(customer_id) REFERENCES store_customers (id) ON DELETE CASCADE, 
	FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS store_customers (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(200), 
	phone VARCHAR(20), 
	display_name VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(300), 
	avatar_data_url TEXT, 
	division VARCHAR(50), 
	district VARCHAR(50), 
	thana VARCHAR(80), 
	address_detail VARCHAR(400), 
	referral_code VARCHAR(20), 
	referred_by VARCHAR(20), 
	is_active BOOLEAN NOT NULL, 
	token_version INTEGER NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS store_messages (
	id VARCHAR(36) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	sender VARCHAR(10) NOT NULL, 
	body TEXT NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	read_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE, 
	FOREIGN KEY(customer_id) REFERENCES store_customers (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS store_products (
	id VARCHAR(36) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	is_listed BOOLEAN NOT NULL, 
	sort_order INTEGER NOT NULL, 
	online_price_bdt NUMERIC(14, 2), 
	description_long TEXT, 
	image_data_url TEXT, 
	tags VARCHAR(300), 
	is_featured BOOLEAN NOT NULL, 
	max_order_qty INTEGER, 
	sale_price NUMERIC(14, 2), 
	sale_start VARCHAR(30), 
	sale_end VARCHAR(30), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (store_id, product_id), 
	FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS stores (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	display_name VARCHAR(160) NOT NULL, 
	tagline VARCHAR(300), 
	logo_data_url TEXT, 
	cover_data_url TEXT, 
	theme_preset VARCHAR(20) NOT NULL, 
	theme_color VARCHAR(7) NOT NULL, 
	category VARCHAR(60), 
	area VARCHAR(120), 
	show_phone BOOLEAN NOT NULL, 
	show_exact_address BOOLEAN NOT NULL, 
	show_hours BOOLEAN NOT NULL, 
	show_stock_level VARCHAR(20) NOT NULL, 
	show_price BOOLEAN NOT NULL, 
	payment_cod BOOLEAN NOT NULL, 
	payment_bkash BOOLEAN NOT NULL, 
	payment_nagad BOOLEAN NOT NULL, 
	bkash_number VARCHAR(20), 
	nagad_number VARCHAR(20), 
	min_order_bdt NUMERIC(10, 2), 
	delivery_note VARCHAR(300), 
	hours_json TEXT, 
	meta_title VARCHAR(160), 
	meta_desc VARCHAR(320), 
	delivery_inside_dhaka NUMERIC(10, 2), 
	delivery_outside_dhaka NUMERIC(10, 2), 
	delivery_free_above NUMERIC(14, 2), 
	allow_zone_restriction BOOLEAN NOT NULL, 
	allowed_divisions VARCHAR(200), 
	sslcz_store_id VARCHAR(100), 
	sslcz_store_passwd VARCHAR(200), 
	sslcz_is_live BOOLEAN NOT NULL, 
	bkash_app_key VARCHAR(100), 
	bkash_app_secret VARCHAR(200), 
	bkash_username VARCHAR(50), 
	bkash_password VARCHAR(100), 
	bkash_is_live BOOLEAN NOT NULL, 
	nagad_merchant_id VARCHAR(50), 
	nagad_merchant_number VARCHAR(20), 
	nagad_pub_key TEXT, 
	nagad_priv_key TEXT, 
	nagad_is_live BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS suppliers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	typical_lead_days INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, code), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS support_case_events (
	id VARCHAR(36) NOT NULL, 
	case_id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(30) NOT NULL, 
	actor_id VARCHAR(36), 
	body TEXT, 
	metadata_json TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES support_cases (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS support_cases (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36), 
	source VARCHAR(30) NOT NULL, 
	subject VARCHAR(300) NOT NULL, 
	description TEXT, 
	priority VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	assigned_to_id VARCHAR(36), 
	affected_feature VARCHAR(60), 
	sla_response_due_at DATETIME, 
	sla_resolution_due_at DATETIME, 
	first_response_at DATETIME, 
	resolved_at DATETIME, 
	created_by_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS support_sessions (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(36) NOT NULL, 
	case_id VARCHAR(36), 
	consent_granted_by_id VARCHAR(36), 
	permissions_json TEXT NOT NULL, 
	purpose VARCHAR(300) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	ended_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(agent_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(case_id) REFERENCES support_cases (id) ON DELETE SET NULL, 
	FOREIGN KEY(consent_granted_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS support_tickets (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	customer_id VARCHAR(36), 
	subject VARCHAR(200) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	priority VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	assigned_to_user_id VARCHAR(36), 
	resolved_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id), 
	FOREIGN KEY(assigned_to_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS sync_operations (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	operation_id VARCHAR(100) NOT NULL, 
	operation_type VARCHAR(30) NOT NULL, 
	payload_hash VARCHAR(64) NOT NULL, 
	entity_type VARCHAR(30) NOT NULL, 
	entity_id VARCHAR(36) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, operation_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS team_messages (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36), 
	user_id VARCHAR(36) NOT NULL, 
	body TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS tenant_data_export_requests (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	requested_by_id VARCHAR(36), 
	status VARCHAR(20) NOT NULL, 
	scope_json TEXT, 
	file_manifest_json TEXT, 
	checksum VARCHAR(64), 
	expires_at DATETIME, 
	completed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS tenant_state_events (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	from_state VARCHAR(30) NOT NULL, 
	to_state VARCHAR(30) NOT NULL, 
	reason VARCHAR(300), 
	actor_admin_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_admin_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS ticket_messages (
	id VARCHAR(36) NOT NULL, 
	ticket_id VARCHAR(36) NOT NULL, 
	author_user_id VARCHAR(36) NOT NULL, 
	body TEXT NOT NULL, 
	internal BOOLEAN DEFAULT 0 NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ticket_id) REFERENCES support_tickets (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_user_id) REFERENCES users (id)
);
CREATE TABLE IF NOT EXISTS usage_aggregates (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	metric VARCHAR(40) NOT NULL, 
	period_month VARCHAR(7) NOT NULL, 
	total NUMERIC(20, 6) NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, metric, period_month), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS usage_events (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	metric VARCHAR(40) NOT NULL, 
	quantity NUMERIC(20, 6) NOT NULL, 
	occurred_at DATETIME NOT NULL, 
	reference_id VARCHAR(36), 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS user_sessions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	current_jti_hash VARCHAR(64) NOT NULL, 
	device_label VARCHAR(200), 
	ip_address VARCHAR(64), 
	last_used_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	revoked_reason VARCHAR(60), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	phone VARCHAR(30), 
	avatar_data_url TEXT, 
	google_subject VARCHAR(255), 
	password_hash VARCHAR(255), 
	token_version INTEGER DEFAULT '0' NOT NULL, 
	setup_token_hash VARCHAR(64), 
	setup_token_expires_at DATETIME, 
	active BOOLEAN NOT NULL, 
	is_platform_admin BOOLEAN DEFAULT 'false' NOT NULL, 
	mfa_totp_secret VARCHAR(64), 
	mfa_enabled BOOLEAN DEFAULT 'false' NOT NULL, 
	mfa_recovery_codes_json TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (google_subject)
);
CREATE TABLE IF NOT EXISTS warehouses (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	branch_id VARCHAR(36) NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	is_default BOOLEAN DEFAULT 0 NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (branch_id, code), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS webhook_events (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(40) NOT NULL, 
	event_type VARCHAR(60), 
	signature_valid BOOLEAN, 
	payload_hash VARCHAR(64), 
	processing_status VARCHAR(20) NOT NULL, 
	related_record_id VARCHAR(36), 
	error TEXT, 
	replay_count INTEGER NOT NULL, 
	last_replayed_at DATETIME, 
	organization_id VARCHAR(36), 
	received_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_access_certification_cycles_status ON access_certification_cycles (status);
CREATE INDEX IF NOT EXISTS ix_access_certification_items_cycle_id ON access_certification_items (cycle_id);
CREATE INDEX IF NOT EXISTS ix_accounts_organization_id ON accounts (organization_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_admin_conversations_organization_id ON admin_conversations (organization_id);
CREATE INDEX IF NOT EXISTS ix_admin_messages_conversation_id ON admin_messages (conversation_id);
CREATE INDEX IF NOT EXISTS ix_admin_messages_created_at ON admin_messages (created_at);
CREATE INDEX IF NOT EXISTS ix_admin_mission_items_affected_org_id ON admin_mission_items (affected_org_id);
CREATE INDEX IF NOT EXISTS ix_admin_mission_items_kind ON admin_mission_items (kind);
CREATE INDEX IF NOT EXISTS ix_admin_mission_items_status ON admin_mission_items (status);
CREATE INDEX IF NOT EXISTS ix_ai_kill_switches_feature ON ai_kill_switches (feature);
CREATE INDEX IF NOT EXISTS ix_approval_requests_kind ON approval_requests (kind);
CREATE INDEX IF NOT EXISTS ix_approval_requests_organization_id ON approval_requests (organization_id);
CREATE INDEX IF NOT EXISTS ix_approval_requests_requested_by_user_id ON approval_requests (requested_by_user_id);
CREATE INDEX IF NOT EXISTS ix_approval_requests_status ON approval_requests (status);
CREATE INDEX IF NOT EXISTS ix_approval_rules_organization_id ON approval_rules (organization_id);
CREATE INDEX IF NOT EXISTS ix_attendance_records_branch_id ON attendance_records (branch_id);
CREATE INDEX IF NOT EXISTS ix_attendance_records_check_in_at ON attendance_records (check_in_at);
CREATE INDEX IF NOT EXISTS ix_attendance_records_organization_id ON attendance_records (organization_id);
CREATE INDEX IF NOT EXISTS ix_attendance_records_user_id ON attendance_records (user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs (actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_organization_id ON audit_logs (organization_id);
CREATE INDEX IF NOT EXISTS ix_audit_org_time ON audit_logs (organization_id, created_at);
CREATE INDEX IF NOT EXISTS ix_batch_org_expiry ON batches (organization_id, expiry_date);
CREATE INDEX IF NOT EXISTS ix_batch_stock_batch_id ON batch_stock (batch_id);
CREATE INDEX IF NOT EXISTS ix_batch_stock_branch_id ON batch_stock (branch_id);
CREATE INDEX IF NOT EXISTS ix_batch_stock_organization_id ON batch_stock (organization_id);
CREATE INDEX IF NOT EXISTS ix_batches_organization_id ON batches (organization_id);
CREATE INDEX IF NOT EXISTS ix_batches_product_id ON batches (product_id);
CREATE INDEX IF NOT EXISTS ix_billing_ledger_entries_entry_type ON billing_ledger_entries (entry_type);
CREATE INDEX IF NOT EXISTS ix_billing_ledger_entries_organization_id ON billing_ledger_entries (organization_id);
CREATE INDEX IF NOT EXISTS ix_billing_ledger_entries_status ON billing_ledger_entries (status);
CREATE INDEX IF NOT EXISTS ix_branches_organization_id ON branches (organization_id);
CREATE INDEX IF NOT EXISTS ix_cash_closes_branch_id ON cash_closes (branch_id);
CREATE INDEX IF NOT EXISTS ix_cash_closes_organization_id ON cash_closes (organization_id);
CREATE INDEX IF NOT EXISTS ix_cash_movements_organization_id ON cash_movements (organization_id);
CREATE INDEX IF NOT EXISTS ix_cash_movements_shift_id ON cash_movements (shift_id);
CREATE INDEX IF NOT EXISTS ix_cashier_shifts_branch_id ON cashier_shifts (branch_id);
CREATE INDEX IF NOT EXISTS ix_cashier_shifts_organization_id ON cashier_shifts (organization_id);
CREATE INDEX IF NOT EXISTS ix_cashier_shifts_user_id ON cashier_shifts (user_id);
CREATE INDEX IF NOT EXISTS ix_churn_risk_scores_organization_id ON churn_risk_scores (organization_id);
CREATE INDEX IF NOT EXISTS ix_cod_handovers_delivery_id ON cod_handovers (delivery_id);
CREATE INDEX IF NOT EXISTS ix_cod_handovers_organization_id ON cod_handovers (organization_id);
CREATE INDEX IF NOT EXISTS ix_cod_handovers_shift_id ON cod_handovers (shift_id);
CREATE INDEX IF NOT EXISTS ix_collection_statements_provider ON collection_statements (provider);
CREATE INDEX IF NOT EXISTS ix_collection_statements_reference ON collection_statements (reference);
CREATE INDEX IF NOT EXISTS ix_collection_statements_status ON collection_statements (status);
CREATE INDEX IF NOT EXISTS ix_commercial_overrides_expires_at ON commercial_overrides (expires_at);
CREATE INDEX IF NOT EXISTS ix_commercial_overrides_organization_id ON commercial_overrides (organization_id);
CREATE INDEX IF NOT EXISTS ix_commission_entries_occurred_at ON commission_entries (occurred_at);
CREATE INDEX IF NOT EXISTS ix_commission_entries_organization_id ON commission_entries (organization_id);
CREATE INDEX IF NOT EXISTS ix_commission_entries_sales_order_id ON commission_entries (sales_order_id);
CREATE INDEX IF NOT EXISTS ix_commission_entries_user_id ON commission_entries (user_id);
CREATE INDEX IF NOT EXISTS ix_commission_rules_organization_id ON commission_rules (organization_id);
CREATE INDEX IF NOT EXISTS ix_config_versions_config_key ON config_versions (config_key);
CREATE INDEX IF NOT EXISTS ix_customers_organization_id ON customers (organization_id);
CREATE INDEX IF NOT EXISTS ix_customers_phone_hash ON customers (phone_hash);
CREATE INDEX IF NOT EXISTS ix_data_inventory_items_module ON data_inventory_items (module);
CREATE INDEX IF NOT EXISTS ix_decision_journal_action_kind ON decision_journal (action_kind);
CREATE INDEX IF NOT EXISTS ix_decision_journal_correlation_id ON decision_journal (correlation_id);
CREATE INDEX IF NOT EXISTS ix_decision_org_time ON recommendation_decisions (organization_id, created_at);
CREATE INDEX IF NOT EXISTS ix_deliveries_branch_id ON deliveries (branch_id);
CREATE INDEX IF NOT EXISTS ix_deliveries_organization_id ON deliveries (organization_id);
CREATE INDEX IF NOT EXISTS ix_deliveries_rider_user_id ON deliveries (rider_user_id);
CREATE INDEX IF NOT EXISTS ix_deliveries_sales_order_id ON deliveries (sales_order_id);
CREATE INDEX IF NOT EXISTS ix_deliveries_status ON deliveries (status);
CREATE INDEX IF NOT EXISTS ix_expenses_branch_id ON expenses (branch_id);
CREATE INDEX IF NOT EXISTS ix_expenses_category ON expenses (category);
CREATE INDEX IF NOT EXISTS ix_expenses_incurred_at ON expenses (incurred_at);
CREATE INDEX IF NOT EXISTS ix_expenses_organization_id ON expenses (organization_id);
CREATE INDEX IF NOT EXISTS ix_feature_rollout_configs_feature_key ON feature_rollout_configs (feature_key);
CREATE INDEX IF NOT EXISTS ix_feedback_entries_customer_id ON feedback_entries (customer_id);
CREATE INDEX IF NOT EXISTS ix_feedback_entries_organization_id ON feedback_entries (organization_id);
CREATE INDEX IF NOT EXISTS ix_feedback_entries_sales_order_id ON feedback_entries (sales_order_id);
CREATE INDEX IF NOT EXISTS ix_fiscal_periods_organization_id ON fiscal_periods (organization_id);
CREATE INDEX IF NOT EXISTS ix_import_batches_checksum_sha256 ON import_batches (checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_import_batches_organization_id ON import_batches (organization_id);
CREATE INDEX IF NOT EXISTS ix_import_batches_uploaded_by ON import_batches (uploaded_by);
CREATE INDEX IF NOT EXISTS ix_incident_events_incident_id ON incident_events (incident_id);
CREATE INDEX IF NOT EXISTS ix_incident_records_severity ON incident_records (severity);
CREATE INDEX IF NOT EXISTS ix_incident_records_status ON incident_records (status);
CREATE INDEX IF NOT EXISTS ix_integration_certifications_organization_id ON integration_certifications (organization_id);
CREATE INDEX IF NOT EXISTS ix_inventory_balances_branch_id ON inventory_balances (branch_id);
CREATE INDEX IF NOT EXISTS ix_inventory_balances_organization_id ON inventory_balances (organization_id);
CREATE INDEX IF NOT EXISTS ix_inventory_balances_product_id ON inventory_balances (product_id);
CREATE INDEX IF NOT EXISTS ix_jit_access_grants_expires_at ON jit_access_grants (expires_at);
CREATE INDEX IF NOT EXISTS ix_jit_access_grants_grantee_id ON jit_access_grants (grantee_id);
CREATE INDEX IF NOT EXISTS ix_job_records_job_type ON job_records (job_type);
CREATE INDEX IF NOT EXISTS ix_job_records_status ON job_records (status);
CREATE INDEX IF NOT EXISTS ix_journal_entries_branch_id ON journal_entries (branch_id);
CREATE INDEX IF NOT EXISTS ix_journal_entries_occurred_at ON journal_entries (occurred_at);
CREATE INDEX IF NOT EXISTS ix_journal_entries_organization_id ON journal_entries (organization_id);
CREATE INDEX IF NOT EXISTS ix_journal_entries_reference_id ON journal_entries (reference_id);
CREATE INDEX IF NOT EXISTS ix_journal_line_account ON journal_lines (organization_id, account_id);
CREATE INDEX IF NOT EXISTS ix_journal_lines_account_id ON journal_lines (account_id);
CREATE INDEX IF NOT EXISTS ix_journal_lines_journal_entry_id ON journal_lines (journal_entry_id);
CREATE INDEX IF NOT EXISTS ix_journal_lines_organization_id ON journal_lines (organization_id);
CREATE INDEX IF NOT EXISTS ix_journal_lines_party_id ON journal_lines (party_id);
CREATE INDEX IF NOT EXISTS ix_journal_org_time ON journal_entries (organization_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_lead_activities_lead_id ON lead_activities (lead_id);
CREATE INDEX IF NOT EXISTS ix_leads_organization_id ON leads (organization_id);
CREATE INDEX IF NOT EXISTS ix_leads_owner_user_id ON leads (owner_user_id);
CREATE INDEX IF NOT EXISTS ix_leads_phone_hash ON leads (phone_hash);
CREATE INDEX IF NOT EXISTS ix_leads_stage ON leads (stage);
CREATE INDEX IF NOT EXISTS ix_leave_requests_organization_id ON leave_requests (organization_id);
CREATE INDEX IF NOT EXISTS ix_leave_requests_status ON leave_requests (status);
CREATE INDEX IF NOT EXISTS ix_leave_requests_user_id ON leave_requests (user_id);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_branch_id ON ledger_entries (branch_id);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_category ON ledger_entries (category);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_occurred_at ON ledger_entries (occurred_at);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_organization_id ON ledger_entries (organization_id);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_party_id ON ledger_entries (party_id);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_reference_id ON ledger_entries (reference_id);
CREATE INDEX IF NOT EXISTS ix_ledger_org_type_party_time ON ledger_entries (organization_id, ledger_type, party_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_loyalty_entries_customer_id ON loyalty_entries (customer_id);
CREATE INDEX IF NOT EXISTS ix_loyalty_entries_occurred_at ON loyalty_entries (occurred_at);
CREATE INDEX IF NOT EXISTS ix_loyalty_entries_organization_id ON loyalty_entries (organization_id);
CREATE INDEX IF NOT EXISTS ix_loyalty_rules_organization_id ON loyalty_rules (organization_id);
CREATE INDEX IF NOT EXISTS ix_membership_branches_branch_id ON membership_branches (branch_id);
CREATE INDEX IF NOT EXISTS ix_membership_branches_membership_id ON membership_branches (membership_id);
CREATE INDEX IF NOT EXISTS ix_memberships_organization_id ON memberships (organization_id);
CREATE INDEX IF NOT EXISTS ix_memberships_user_id ON memberships (user_id);
CREATE INDEX IF NOT EXISTS ix_model_outcome_records_feature ON model_outcome_records (feature);
CREATE INDEX IF NOT EXISTS ix_model_outcome_records_vertical ON model_outcome_records (vertical);
CREATE INDEX IF NOT EXISTS ix_model_registry_entries_feature ON model_registry_entries (feature);
CREATE INDEX IF NOT EXISTS ix_model_registry_entries_is_active ON model_registry_entries (is_active);
CREATE INDEX IF NOT EXISTS ix_notifications_organization_id ON notifications (organization_id);
CREATE INDEX IF NOT EXISTS ix_notifications_recipient_user_id ON notifications (recipient_user_id);
CREATE INDEX IF NOT EXISTS ix_org_invoices_created_at ON org_invoices (created_at);
CREATE INDEX IF NOT EXISTS ix_org_invoices_organization_id ON org_invoices (organization_id);
CREATE INDEX IF NOT EXISTS ix_org_plan_subscriptions_organization_id ON org_plan_subscriptions (organization_id);
CREATE INDEX IF NOT EXISTS ix_org_plan_subscriptions_status ON org_plan_subscriptions (status);
CREATE UNIQUE INDEX IF NOT EXISTS ix_org_subscriptions_organization_id ON org_subscriptions (organization_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_organizations_slug ON organizations (slug);
CREATE INDEX IF NOT EXISTS ix_outbound_messages_channel ON outbound_messages (channel);
CREATE INDEX IF NOT EXISTS ix_outbound_messages_idempotency_key ON outbound_messages (idempotency_key);
CREATE INDEX IF NOT EXISTS ix_outbound_messages_organization_id ON outbound_messages (organization_id);
CREATE INDEX IF NOT EXISTS ix_outbound_messages_status ON outbound_messages (status);
CREATE INDEX IF NOT EXISTS ix_outcome_org_time ON recommendation_outcomes (organization_id, observed_at);
CREATE INDEX IF NOT EXISTS ix_payments_order_id ON payments (order_id);
CREATE INDEX IF NOT EXISTS ix_payments_organization_id ON payments (organization_id);
CREATE INDEX IF NOT EXISTS ix_payments_shift_id ON payments (shift_id);
CREATE INDEX IF NOT EXISTS ix_payroll_lines_organization_id ON payroll_lines (organization_id);
CREATE INDEX IF NOT EXISTS ix_payroll_lines_payroll_run_id ON payroll_lines (payroll_run_id);
CREATE INDEX IF NOT EXISTS ix_payroll_lines_user_id ON payroll_lines (user_id);
CREATE INDEX IF NOT EXISTS ix_payroll_runs_organization_id ON payroll_runs (organization_id);
CREATE INDEX IF NOT EXISTS ix_payroll_runs_status ON payroll_runs (status);
CREATE UNIQUE INDEX IF NOT EXISTS ix_plans_code ON plans (code);
CREATE INDEX IF NOT EXISTS ix_privacy_requests_request_type ON privacy_requests (request_type);
CREATE INDEX IF NOT EXISTS ix_privacy_requests_status ON privacy_requests (status);
CREATE INDEX IF NOT EXISTS ix_product_reviews_organization_id ON product_reviews (organization_id);
CREATE INDEX IF NOT EXISTS ix_product_reviews_product_id ON product_reviews (product_id);
CREATE INDEX IF NOT EXISTS ix_product_reviews_store_customer_id ON product_reviews (store_customer_id);
CREATE INDEX IF NOT EXISTS ix_product_variants_organization_id ON product_variants (organization_id);
CREATE INDEX IF NOT EXISTS ix_product_variants_product_id ON product_variants (product_id);
CREATE INDEX IF NOT EXISTS ix_products_barcode ON products (barcode);
CREATE INDEX IF NOT EXISTS ix_products_category ON products (category);
CREATE INDEX IF NOT EXISTS ix_products_organization_id ON products (organization_id);
CREATE INDEX IF NOT EXISTS ix_provider_credentials_expires_at ON provider_credentials (expires_at);
CREATE INDEX IF NOT EXISTS ix_provider_credentials_provider ON provider_credentials (provider);
CREATE INDEX IF NOT EXISTS ix_provider_credentials_status ON provider_credentials (status);
CREATE INDEX IF NOT EXISTS ix_purchase_order_items_organization_id ON purchase_order_items (organization_id);
CREATE INDEX IF NOT EXISTS ix_purchase_order_items_product_id ON purchase_order_items (product_id);
CREATE INDEX IF NOT EXISTS ix_purchase_order_items_purchase_order_id ON purchase_order_items (purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_branch_id ON purchase_orders (branch_id);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_ordered_at ON purchase_orders (ordered_at);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_organization_id ON purchase_orders (organization_id);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_supplier_id ON purchase_orders (supplier_id);
CREATE INDEX IF NOT EXISTS ix_purchase_org_branch_time ON purchase_orders (organization_id, branch_id, ordered_at);
CREATE INDEX IF NOT EXISTS ix_purchase_return_items_batch_id ON purchase_return_items (batch_id);
CREATE INDEX IF NOT EXISTS ix_purchase_return_items_organization_id ON purchase_return_items (organization_id);
CREATE INDEX IF NOT EXISTS ix_purchase_return_items_product_id ON purchase_return_items (product_id);
CREATE INDEX IF NOT EXISTS ix_purchase_return_items_purchase_order_item_id ON purchase_return_items (purchase_order_item_id);
CREATE INDEX IF NOT EXISTS ix_purchase_return_items_purchase_return_id ON purchase_return_items (purchase_return_id);
CREATE INDEX IF NOT EXISTS ix_purchase_return_org_time ON purchase_returns (organization_id, submitted_at);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_branch_id ON purchase_returns (branch_id);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_organization_id ON purchase_returns (organization_id);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_purchase_order_id ON purchase_returns (purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_status ON purchase_returns (status);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_submitted_at ON purchase_returns (submitted_at);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_supplier_id ON purchase_returns (supplier_id);
CREATE INDEX IF NOT EXISTS ix_reco_org_cutoff ON recommendations (organization_id, cutoff_date);
CREATE INDEX IF NOT EXISTS ix_recommendation_decisions_decision ON recommendation_decisions (decision);
CREATE INDEX IF NOT EXISTS ix_recommendation_decisions_organization_id ON recommendation_decisions (organization_id);
CREATE INDEX IF NOT EXISTS ix_recommendation_decisions_recommendation_id ON recommendation_decisions (recommendation_id);
CREATE INDEX IF NOT EXISTS ix_recommendation_outcomes_organization_id ON recommendation_outcomes (organization_id);
CREATE INDEX IF NOT EXISTS ix_recommendation_outcomes_recommendation_id ON recommendation_outcomes (recommendation_id);
CREATE INDEX IF NOT EXISTS ix_recommendations_action_type ON recommendations (action_type);
CREATE INDEX IF NOT EXISTS ix_recommendations_branch_id ON recommendations (branch_id);
CREATE INDEX IF NOT EXISTS ix_recommendations_cutoff_date ON recommendations (cutoff_date);
CREATE INDEX IF NOT EXISTS ix_recommendations_organization_id ON recommendations (organization_id);
CREATE INDEX IF NOT EXISTS ix_recommendations_run_id ON recommendations (run_id);
CREATE INDEX IF NOT EXISTS ix_reference_kind_parent ON reference_values (kind, parent_code);
CREATE INDEX IF NOT EXISTS ix_reference_values_kind ON reference_values (kind);
CREATE INDEX IF NOT EXISTS ix_reference_values_parent_code ON reference_values (parent_code);
CREATE INDEX IF NOT EXISTS ix_refunds_organization_id ON refunds (organization_id);
CREATE INDEX IF NOT EXISTS ix_refunds_sales_return_id ON refunds (sales_return_id);
CREATE INDEX IF NOT EXISTS ix_reservations_branch_id ON reservations (branch_id);
CREATE INDEX IF NOT EXISTS ix_reservations_organization_id ON reservations (organization_id);
CREATE INDEX IF NOT EXISTS ix_reservations_product_id ON reservations (product_id);
CREATE INDEX IF NOT EXISTS ix_reservations_sales_document_id ON reservations (sales_document_id);
CREATE INDEX IF NOT EXISTS ix_reservations_status ON reservations (status);
CREATE INDEX IF NOT EXISTS ix_retention_policies_data_category ON retention_policies (data_category);
CREATE INDEX IF NOT EXISTS ix_roster_shifts_branch_id ON roster_shifts (branch_id);
CREATE INDEX IF NOT EXISTS ix_roster_shifts_organization_id ON roster_shifts (organization_id);
CREATE INDEX IF NOT EXISTS ix_roster_shifts_shift_date ON roster_shifts (shift_date);
CREATE INDEX IF NOT EXISTS ix_roster_shifts_user_id ON roster_shifts (user_id);
CREATE INDEX IF NOT EXISTS ix_sale_item_batches_batch_id ON sale_item_batches (batch_id);
CREATE INDEX IF NOT EXISTS ix_sale_item_batches_organization_id ON sale_item_batches (organization_id);
CREATE INDEX IF NOT EXISTS ix_sale_item_batches_sales_order_item_id ON sale_item_batches (sales_order_item_id);
CREATE INDEX IF NOT EXISTS ix_sales_document_lines_document_id ON sales_document_lines (document_id);
CREATE INDEX IF NOT EXISTS ix_sales_document_lines_organization_id ON sales_document_lines (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_document_lines_product_id ON sales_document_lines (product_id);
CREATE INDEX IF NOT EXISTS ix_sales_document_org_time ON sales_documents (organization_id, issued_at);
CREATE UNIQUE INDEX IF NOT EXISTS ix_sales_documents_access_token ON sales_documents (access_token);
CREATE INDEX IF NOT EXISTS ix_sales_documents_branch_id ON sales_documents (branch_id);
CREATE INDEX IF NOT EXISTS ix_sales_documents_customer_id ON sales_documents (customer_id);
CREATE INDEX IF NOT EXISTS ix_sales_documents_document_type ON sales_documents (document_type);
CREATE INDEX IF NOT EXISTS ix_sales_documents_invoice_id ON sales_documents (invoice_id);
CREATE INDEX IF NOT EXISTS ix_sales_documents_issued_at ON sales_documents (issued_at);
CREATE INDEX IF NOT EXISTS ix_sales_documents_organization_id ON sales_documents (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_documents_status ON sales_documents (status);
CREATE INDEX IF NOT EXISTS ix_sales_documents_store_customer_id ON sales_documents (store_customer_id);
CREATE INDEX IF NOT EXISTS ix_sales_order_items_order_id ON sales_order_items (order_id);
CREATE INDEX IF NOT EXISTS ix_sales_order_items_organization_id ON sales_order_items (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_order_items_product_id ON sales_order_items (product_id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_branch_id ON sales_orders (branch_id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_customer_id ON sales_orders (customer_id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_organization_id ON sales_orders (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_sold_at ON sales_orders (sold_at);
CREATE INDEX IF NOT EXISTS ix_sales_org_branch_time ON sales_orders (organization_id, branch_id, sold_at);
CREATE INDEX IF NOT EXISTS ix_sales_return_items_organization_id ON sales_return_items (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_return_items_product_id ON sales_return_items (product_id);
CREATE INDEX IF NOT EXISTS ix_sales_return_items_sales_order_item_id ON sales_return_items (sales_order_item_id);
CREATE INDEX IF NOT EXISTS ix_sales_return_items_sales_return_id ON sales_return_items (sales_return_id);
CREATE INDEX IF NOT EXISTS ix_sales_returns_branch_id ON sales_returns (branch_id);
CREATE INDEX IF NOT EXISTS ix_sales_returns_organization_id ON sales_returns (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_returns_returned_at ON sales_returns (returned_at);
CREATE INDEX IF NOT EXISTS ix_sales_returns_sales_order_id ON sales_returns (sales_order_id);
CREATE INDEX IF NOT EXISTS ix_sales_targets_organization_id ON sales_targets (organization_id);
CREATE INDEX IF NOT EXISTS ix_sales_targets_user_id ON sales_targets (user_id);
CREATE INDEX IF NOT EXISTS ix_sc_address_customer_default ON store_customer_addresses (customer_id, is_default);
CREATE INDEX IF NOT EXISTS ix_sc_cart_customer_store ON store_customer_cart_items (customer_id, store_id);
CREATE INDEX IF NOT EXISTS ix_sc_wishlist_customer_created ON store_customer_wishlist_items (customer_id, created_at);
CREATE INDEX IF NOT EXISTS ix_security_alerts_alert_type ON security_alerts (alert_type);
CREATE INDEX IF NOT EXISTS ix_security_alerts_severity ON security_alerts (severity);
CREATE INDEX IF NOT EXISTS ix_security_alerts_status ON security_alerts (status);
CREATE INDEX IF NOT EXISTS ix_staff_advance_repayments_advance_id ON staff_advance_repayments (advance_id);
CREATE INDEX IF NOT EXISTS ix_staff_advance_repayments_organization_id ON staff_advance_repayments (organization_id);
CREATE INDEX IF NOT EXISTS ix_staff_advances_organization_id ON staff_advances (organization_id);
CREATE INDEX IF NOT EXISTS ix_staff_advances_status ON staff_advances (status);
CREATE INDEX IF NOT EXISTS ix_staff_advances_user_id ON staff_advances (user_id);
CREATE INDEX IF NOT EXISTS ix_stock_count_lines_organization_id ON stock_count_lines (organization_id);
CREATE INDEX IF NOT EXISTS ix_stock_count_lines_product_id ON stock_count_lines (product_id);
CREATE INDEX IF NOT EXISTS ix_stock_count_lines_stock_count_id ON stock_count_lines (stock_count_id);
CREATE INDEX IF NOT EXISTS ix_stock_counts_branch_id ON stock_counts (branch_id);
CREATE INDEX IF NOT EXISTS ix_stock_counts_organization_id ON stock_counts (organization_id);
CREATE INDEX IF NOT EXISTS ix_stock_counts_started_at ON stock_counts (started_at);
CREATE INDEX IF NOT EXISTS ix_stock_movements_batch_id ON stock_movements (batch_id);
CREATE INDEX IF NOT EXISTS ix_stock_movements_branch_id ON stock_movements (branch_id);
CREATE INDEX IF NOT EXISTS ix_stock_movements_organization_id ON stock_movements (organization_id);
CREATE INDEX IF NOT EXISTS ix_stock_movements_product_id ON stock_movements (product_id);
CREATE INDEX IF NOT EXISTS ix_stock_org_branch_product_time ON stock_movements (organization_id, branch_id, product_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_store_coupons_organization_id ON store_coupons (organization_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_addresses_customer_id ON store_customer_addresses (customer_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_cart_items_customer_id ON store_customer_cart_items (customer_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_cart_items_product_id ON store_customer_cart_items (product_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_cart_items_store_id ON store_customer_cart_items (store_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_wishlist_items_customer_id ON store_customer_wishlist_items (customer_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_wishlist_items_product_id ON store_customer_wishlist_items (product_id);
CREATE INDEX IF NOT EXISTS ix_store_customer_wishlist_items_store_id ON store_customer_wishlist_items (store_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_store_customers_email ON store_customers (email);
CREATE INDEX IF NOT EXISTS ix_store_customers_phone ON store_customers (phone);
CREATE UNIQUE INDEX IF NOT EXISTS ix_store_customers_referral_code ON store_customers (referral_code);
CREATE INDEX IF NOT EXISTS ix_store_messages_customer_id ON store_messages (customer_id);
CREATE INDEX IF NOT EXISTS ix_store_messages_store_id ON store_messages (store_id);
CREATE INDEX IF NOT EXISTS ix_store_msg_store_customer ON store_messages (store_id, customer_id);
CREATE INDEX IF NOT EXISTS ix_store_products_product_id ON store_products (product_id);
CREATE INDEX IF NOT EXISTS ix_store_products_store_id ON store_products (store_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_stores_organization_id ON stores (organization_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_stores_slug ON stores (slug);
CREATE INDEX IF NOT EXISTS ix_suppliers_organization_id ON suppliers (organization_id);
CREATE INDEX IF NOT EXISTS ix_support_case_events_case_id ON support_case_events (case_id);
CREATE INDEX IF NOT EXISTS ix_support_cases_organization_id ON support_cases (organization_id);
CREATE INDEX IF NOT EXISTS ix_support_cases_priority ON support_cases (priority);
CREATE INDEX IF NOT EXISTS ix_support_cases_status ON support_cases (status);
CREATE INDEX IF NOT EXISTS ix_support_sessions_expires_at ON support_sessions (expires_at);
CREATE INDEX IF NOT EXISTS ix_support_sessions_organization_id ON support_sessions (organization_id);
CREATE INDEX IF NOT EXISTS ix_support_tickets_assigned_to_user_id ON support_tickets (assigned_to_user_id);
CREATE INDEX IF NOT EXISTS ix_support_tickets_branch_id ON support_tickets (branch_id);
CREATE INDEX IF NOT EXISTS ix_support_tickets_customer_id ON support_tickets (customer_id);
CREATE INDEX IF NOT EXISTS ix_support_tickets_organization_id ON support_tickets (organization_id);
CREATE INDEX IF NOT EXISTS ix_support_tickets_status ON support_tickets (status);
CREATE INDEX IF NOT EXISTS ix_sync_operations_entity_id ON sync_operations (entity_id);
CREATE INDEX IF NOT EXISTS ix_sync_operations_operation_id ON sync_operations (operation_id);
CREATE INDEX IF NOT EXISTS ix_sync_operations_operation_type ON sync_operations (operation_type);
CREATE INDEX IF NOT EXISTS ix_sync_operations_organization_id ON sync_operations (organization_id);
CREATE INDEX IF NOT EXISTS ix_team_messages_org_time ON team_messages (organization_id, created_at);
CREATE INDEX IF NOT EXISTS ix_team_messages_organization_id ON team_messages (organization_id);
CREATE INDEX IF NOT EXISTS ix_team_messages_user_id ON team_messages (user_id);
CREATE INDEX IF NOT EXISTS ix_tenant_data_export_requests_organization_id ON tenant_data_export_requests (organization_id);
CREATE INDEX IF NOT EXISTS ix_tenant_data_export_requests_status ON tenant_data_export_requests (status);
CREATE INDEX IF NOT EXISTS ix_tenant_state_events_organization_id ON tenant_state_events (organization_id);
CREATE INDEX IF NOT EXISTS ix_ticket_messages_ticket_id ON ticket_messages (ticket_id);
CREATE INDEX IF NOT EXISTS ix_usage_aggregates_organization_id ON usage_aggregates (organization_id);
CREATE INDEX IF NOT EXISTS ix_usage_events_metric ON usage_events (metric);
CREATE INDEX IF NOT EXISTS ix_usage_events_occurred_at ON usage_events (occurred_at);
CREATE INDEX IF NOT EXISTS ix_usage_events_organization_id ON usage_events (organization_id);
CREATE INDEX IF NOT EXISTS ix_usage_org_metric_time ON usage_events (organization_id, metric, occurred_at);
CREATE INDEX IF NOT EXISTS ix_user_sessions_current_jti_hash ON user_sessions (current_jti_hash);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_setup_token_hash ON users (setup_token_hash);
CREATE INDEX IF NOT EXISTS ix_warehouses_branch_id ON warehouses (branch_id);
CREATE INDEX IF NOT EXISTS ix_warehouses_organization_id ON warehouses (organization_id);
CREATE INDEX IF NOT EXISTS ix_webhook_events_processing_status ON webhook_events (processing_status);
CREATE INDEX IF NOT EXISTS ix_webhook_events_provider ON webhook_events (provider);
CREATE INDEX IF NOT EXISTS ix_webhook_events_received_at ON webhook_events (received_at);
CREATE TABLE IF NOT EXISTS operational_schema_meta (version INTEGER PRIMARY KEY, source TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
INSERT OR IGNORE INTO operational_schema_meta(version,source) VALUES (1,'api.domain_models+api.admin_models');
