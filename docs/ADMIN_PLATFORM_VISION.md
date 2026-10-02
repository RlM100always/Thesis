# B-SMART Platform Admin — Vision & Roadmap

**Status:** VISION — not yet implemented.
**Purpose:** This document is the authoritative roadmap for transforming the current admin panel into a production-grade SaaS control-plane. Read before adding any admin feature.

---

## Current State Assessment

| Area | Current | Primary Gap |
|---|---|---|
| Tenant management | Partial | No lifecycle state machine, no health scoring, no contract/billing |
| User management | Partial | No access certification, no risk detection, no governance workflow |
| Security | Basic | No JIT access, no approval flow, no threat response, no policy engine |
| Feature rollout | Basic | No gradual rollout, no guardrails, no automatic rollback |
| Integrations | Very basic | No credential lifecycle, no webhook replay, no provider failover |
| Billing & revenue | Almost none | No plan engine, no usage metering, no invoice/collection ledger |
| Reliability ops | Weak | No incident command, no job queue console, no tenant-aware SLO |
| Customer success | Almost none | No support cases, no SLA, no intervention playbook |
| Data governance | None | No retention policy, no export workflow, no privacy request handling |
| AI governance | None | No model registry, no cost control, no outcome monitoring |

---

## Core Operating Logic

Every admin action must follow this chain — never shortcut it:

```
Business signal
      ↓
Risk or opportunity detection
      ↓
Admin mission queue
      ↓
Policy and approval check
      ↓
Action execution
      ↓
Immutable audit evidence
      ↓
Tenant and business outcome measurement
```

The goal is not "show 1,250 users." It is:

> 17 tenants have increasing WhatsApp delivery failures. ~380 order notifications are blocked. Activating the SMS fallback route will cost an estimated ৳1,840. Approve?

---

## Actor Structure

| Actor | Primary Responsibility |
|---|---|
| Platform Owner | Top-level governance, commercial policy |
| Operations Admin | Tenant lifecycle, onboarding orchestration, incidents |
| Support Admin | Cases, SLA, consented support sessions |
| Finance Admin | Billing, invoice, refund, MFS reconciliation |
| Security Admin | Access governance, risk inbox, session investigation |
| Release Manager | Feature rollout, configuration versioning, rollback |
| Integration Admin | Provider health, webhook inbox, credential rotation |
| Data Protection Admin | Export, retention, deletion, privacy requests |
| AI Operations Admin | Model registry, prompt governance, cost, outcome monitoring |
| Auditor | Read-only access to evidence and reports only |

### Non-negotiable architectural rule

Navigation permissions and backend permissions must derive from the same policy source. The chain is:

```
Admin identity → Platform role → Permission policy → Tenant scope
      → Resource and action → Risk check → Approval requirement
      → Execution → Audit event
```

---

## 50 Capabilities

### Phase 1 — Foundation (implement first)

**1. Dynamic Mission Queue**
Automatically surfaces admin tasks from: stalled onboarding, outdated backups, payment mismatches, security risks, provider failures, and subscription due dates. Each task has owner, priority, deadline, affected tenant, estimated impact, and recommended action.

**2. Universal Command Search**
Single search across tenant, user, invoice, subscription, sale, order, employee, support case, webhook, and audit event. Results deep-link to the correct record in the relevant module.

**3. Personalised Admin Workspace**
Each actor role (see above) sees a role-filtered default dashboard. Each admin can arrange widgets, filters, and saved views.

**4. Shift Handover System**
Unresolved incidents, pending approvals, and priority tenants are formally handed between on-call shifts. Responsibility stays with the outgoing team until the incoming team acknowledges.

**5. Decision Journal**
Every significant admin action records: decision reason, supporting evidence, attachments, approver, and expected outcome — not just who did what, but why.

**6. Formal Tenant State Machine**
```
Lead → Trial → Onboarding → Live → At Risk
                               ↓
                        Grace Period
                               ↓
                   Suspended → Offboarded
```
Transitions are rule-driven, not manual text fields.

**7. Automated Onboarding Orchestrator**
After signup: business profile, owner identity, subscription, branch, tax settings, payment config, role assignment, product catalogue, first transaction — orchestrated as a repeatable, automated process (per AWS SaaS guidance).

**8. Tenant 360 Timeline**
Single timeline showing signup, login, configuration changes, subscription events, support cases, payments, security events, communications, incidents, and admin actions — no cross-module navigation needed.

**9. Explainable Tenant Health Score**
Composite of: recent business activity, failed integrations, outstanding payment, support escalations, employee adoption, backup condition, security risk, feature usage. Score is accompanied by reasons and recommended interventions.

**10. Controlled Tenant Offboarding**
Pre-offboarding checklist: invoice settlement, data export, provider disconnect, active session revocation, retention period acknowledgement, deletion approval. No single-click permanent delete.

**DB models needed:** `TenantStateEvent`, `AdminMissionItem`, `ShiftHandover`, `DecisionJournal`

---

### Phase 2 — Revenue Operations

**11. Plan and Entitlement Engine**
Each plan defines: modules, branch limit, employee limit, transaction limit, AI usage, messaging quota, support tier. Frontend menu and backend authorization use the same entitlement source.

**12. Contract and Commercial Override**
Per-tenant: negotiated price, free period, extra branches, discount, custom entitlement expiry. Expiring overrides return to review queue automatically.

**13. Usage Metering**
Per tenant: active users, branches, storage, SMS, WhatsApp, AI tokens, invoices, transactions. Stored as raw events and monthly aggregates.

**14. BDT Billing Ledger**
Double-entry style: invoice, payment, credit note, discount, refund, grace period, outstanding balance. Supports fixed fee, usage-based charge, overage, credit, graduated tiers (Stripe billing model).

**15. Collection and Reconciliation Workbench**
bKash, Nagad, bank transfer, manual collection matched against invoices. Separate queues for: unmatched payment, partial payment, duplicate reference, disputed amount.

**DB models needed:** `Plan`, `PlanEntitlement`, `CommercialOverride`, `UsageEvent`, `UsageAggregate`, `BillingLedgerEntry`, `CollectionStatement`, `ReconciliationItem`

---

### Phase 3 — Controlled Operations

**16. Unified Support Case**
Call, email, WhatsApp, in-app request, and admin-created issue — all in one case system. Each case linked to tenant, subscription, affected feature, and recent incidents.

**17. SLA Management**
Response and resolution SLA calculated by priority and support plan. Escalation fires before breach, not after.

**18. Consented Support Session**
Tenant owner grants time-limited, permission-scoped access to a support agent. No permanent unrestricted impersonation.

**19. Intervention Playbook**
Condition-based playbooks ("first sale not made", "integration failing", "staff adoption low") trigger step-by-step actions: email, notification, training link, support task creation.

**20. Renewal and Churn Risk**
Risk score from: low activity, repeated support issues, failed payment, poor adoption, unresolved incidents. Each risk is explainable and has a recovery owner.

**21. Security Risk Inbox**
Aggregates: impossible login, repeated failures, new device, MFA removal, privilege escalation, unusual export. Each alert has severity, evidence, and response action.

**22. Just-in-Time Privileged Access**
Sensitive access granted for specific reason and specific duration. Permission revokes automatically on expiry.

**23. Separation of Duties**
Enforced: one admin cannot both create and approve a refund, delete and approve a backup, or grant themselves privilege.

**24. Periodic Access Certification**
Scheduled reviews: tenant owners and platform security team certify which access is still needed. Dormant privileged accounts flagged automatically.

**25. Emergency Containment**
Single action: freeze tenant logins, revoke suspicious sessions, disable API keys, halt provider communications.

**26. Service Dependency Map**
Visual: POS → inventory → payment → SMS/WhatsApp → AI → database → background jobs → storage. When a provider goes down, the map shows which features and tenants are affected.

**27. Tenant-Aware SLO**
Success rate, latency, and error rate per tenant, plan, and module — not just global averages. An enterprise tenant failure cannot be hidden inside a healthy global average.

**28. Background Job Console**
View: pending, running, failed, retried, dead-letter jobs. Actions: safe retry, cancellation. Guards: duplicate protection.

**29. Incident Command Center**
Unified: severity, commander, timeline, impacted tenants, mitigation steps, customer communication log, root cause.

**30. Recovery Orchestration**
Beyond backup existence: tenant-specific restore, restore rehearsal, recovery evidence, RPO and RTO measurement.

**31. Environment Promotion**
Dev → staging → pilot → production with approval and validation at each gate.

**32. Tenant Segmentation for Features**
Target features by: sector, subscription tier, region, employee count, business maturity, app version, or named tenants.

**33. Progressive Rollout**
Sequence: internal tenants → pilot group → 5% → 20% → 50% → all.

**34. Guardrail and Automatic Rollback**
During rollout: if error rate, payment failure rate, support ticket rate, or conversion degrades past threshold → pause or rollback automatically.

**35. Configuration Versioning**
Each feature config has: version, diff, approver, deployment time, rollback point.

**36. Provider Credential Lifecycle**
States: active, expiring, expired, revoked, rotation required. Secrets never shown in plaintext on any interface.

**37. Webhook Inbox**
Per webhook: provider, signature status, payload reference, processing result, linked business record. Failed webhooks can be safely replayed.

**38. Provider Routing and Failover**
When primary SMS gateway fails, configured policy selects secondary. Cost, delivery rate, and tenant preference all factor in.

**39. Integration Reconciliation**
Track provider requests through states: requested → accepted → delivered → failed → reversed → reconciled.

**40. Tenant Integration Certification**
Before going live: sandbox transaction, callback validation, refund test, credential verification must all pass.

**DB models needed:** `SupportCase`, `SlaTimer`, `SupportSession`, `InterventionPlaybook`, `SecurityAlert`, `JitAccessGrant`, `IncidentRecord`, `FeatureFlag`, `FeatureRolloutStage`, `ProviderCredential`, `WebhookEvent`, `IntegrationCertification`

---

### Phase 4 — Governance

**41. Data Inventory**
Catalogue of which modules hold personal, financial, employee, customer, and audit data.

**42. Tenant Data Export**
Structured export on owner request. Package includes: file manifest, generation time, checksum, expiry.

**43. Retention Policy Engine**
Separate policies for invoice, attendance, communication, logs, backup. On expiry: archive or purge with approval.

**44. Privacy Request Workflow**
Access, correction, portability, and deletion requests handled with verification, approval, and evidence.

**45. Immutable Audit Evidence**
Per sensitive action: actor, tenant, previous value, new value, reason, device, timestamp, correlation ID. Standard admins cannot edit audit events.

**46. Model and Prompt Registry**
Per feature: which model version, prompt version, knowledge source, and fallback is in use.

**47. AI Cost Control**
Per tenant/feature/user: token budget, request quota, latency budget. On budget breach: downgrade to cheaper model, switch to manual mode, or require approval.

**48. Recommendation Lineage**
For every AI recommendation (reorder, fraud alert, forecast, employee insight): input sources and reasoning summary visible to admin.

**49. Model Outcome Monitoring**
Recommendation accuracy and acceptance rate per vertical (retail, restaurant, manufacturing, service) tracked separately. Financial loss from wrong recommendations captured.

**50. Human Approval and AI Kill Switch**
AI cannot finalize: price changes, payroll actions, supplier orders, refunds, or customer blocks. Risk threshold breach triggers human approval requirement or feature-level kill switch.

**DB models needed:** `DataInventoryItem`, `TenantDataExportRequest`, `RetentionPolicy`, `PrivacyRequest`, `ModelRegistryEntry`, `AiCostBudget`, `RecommendationLineage`, `ModelOutcomeRecord`, `AiKillSwitch`

---

## Implementation Order Summary

| Phase | Capabilities | When |
|---|---|---|
| Foundation | 1–10 (mission queue, tenant lifecycle, 360 timeline, health score, audit) | Sprint 1–2 |
| Revenue Operations | 11–15 (plan engine, usage metering, billing ledger, collection) | Sprint 3–4 |
| Controlled Operations | 16–40 (support, SLA, JIT access, incident, rollout, webhooks) | Sprint 5–8 |
| Governance | 41–50 (data retention, privacy, AI governance, outcome monitoring) | Sprint 9–10 |

---

## What is already partially implemented

- Platform routes: `api/platform_routes.py` — tenant listing, basic user management
- Audit log: `api/audit.py`, `api/audit_routes.py` — exists but not immutable-enforced
- Permission matrix: `api/permissions.py` — server-side enforcement exists
- Feature flags: partial in domain models
- Approval workflow: `api/approvals.py`, `api/approval_routes.py` — exists for business actions

Before starting any phase, read the current state of these files to avoid duplicating or breaking existing work.
