"""Admin platform models — production SaaS control-plane tables.

Covers all 50 capabilities in docs/ADMIN_PLATFORM_VISION.md:
Foundation → Revenue Operations → Controlled Operations → Governance.
None of these tables carry tenant business data; they are platform-admin records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Foundation ────────────────────────────────────────────────────────────────

class AdminMissionItem(Base):
    """Platform-level admin task queue — auto-generated from signals."""
    __tablename__ = "admin_mission_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    affected_org_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    affected_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owner_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    estimated_impact: Mapped[str | None] = mapped_column(String(200))
    recommended_action: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ShiftHandover(Base):
    """Formal handover of unresolved items between on-call admin shifts."""
    __tablename__ = "shift_handovers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    from_admin_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text)
    open_incidents: Mapped[int] = mapped_column(Integer, default=0)
    pending_approvals: Mapped[int] = mapped_column(Integer, default=0)
    priority_org_ids_json: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DecisionJournal(Base):
    """Why a significant admin action was taken — not just what."""
    __tablename__ = "decision_journal"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    actor_admin_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action_kind: Mapped[str] = mapped_column(String(60), index=True)
    affected_org_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    decision_reason: Mapped[str] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(500))
    approver_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TenantStateEvent(Base):
    """Audit trail for tenant lifecycle state transitions."""
    __tablename__ = "tenant_state_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    from_state: Mapped[str] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(300))
    actor_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Revenue Operations ────────────────────────────────────────────────────────

class Plan(Base):
    """Subscription plan definition."""
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    price_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly")
    branch_limit: Mapped[int | None] = mapped_column(Integer)
    employee_limit: Mapped[int | None] = mapped_column(Integer)
    transaction_limit: Mapped[int | None] = mapped_column(Integer)
    ai_token_quota: Mapped[int | None] = mapped_column(Integer)
    sms_quota: Mapped[int | None] = mapped_column(Integer)
    whatsapp_quota: Mapped[int | None] = mapped_column(Integer)
    support_tier: Mapped[str] = mapped_column(String(20), default="standard")
    modules_json: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class OrgPlanSubscription(Base):
    """Which plan a tenant is on, with start/end dates."""
    __tablename__ = "org_plan_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    granted_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CommercialOverride(Base):
    """Per-tenant negotiated exception (free period, extra branches, discount)."""
    __tablename__ = "commercial_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300))
    value_json: Mapped[str] = mapped_column(Text)
    granted_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class UsageEvent(Base):
    """Raw per-tenant resource consumption event."""
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_org_metric_time", "organization_id", "metric", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(40), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("1"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    reference_id: Mapped[str | None] = mapped_column(String(36))


class UsageAggregate(Base):
    """Monthly rollup of usage per tenant per metric."""
    __tablename__ = "usage_aggregates"
    __table_args__ = (UniqueConstraint("organization_id", "metric", "period_month"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(40))
    period_month: Mapped[str] = mapped_column(String(7))
    total: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class BillingLedgerEntry(Base):
    """Double-entry billing ledger: invoice, payment, credit, refund."""
    __tablename__ = "billing_ledger_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entry_type: Mapped[str] = mapped_column(String(30), index=True)
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(String(300))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    period_month: Mapped[str | None] = mapped_column(String(7))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class CollectionStatement(Base):
    """bKash/Nagad/bank statement import for reconciliation."""
    __tablename__ = "collection_statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    reference: Mapped[str] = mapped_column(String(100), index=True)
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    matched_invoice_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="unmatched", index=True)
    notes: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Customer Success & Support ────────────────────────────────────────────────

class SupportCase(Base):
    """Unified support case from any channel."""
    __tablename__ = "support_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(30), default="manual")
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    assigned_to_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    affected_feature: Mapped[str | None] = mapped_column(String(60))
    sla_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class SupportCaseEvent(Base):
    """Timeline event on a support case (comment, status change, assignment)."""
    __tablename__ = "support_case_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("support_cases.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SupportSession(Base):
    """Consented time-limited support agent access to a tenant."""
    __tablename__ = "support_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    agent_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    case_id: Mapped[str | None] = mapped_column(
        ForeignKey("support_cases.id", ondelete="SET NULL"), nullable=True
    )
    consent_granted_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    permissions_json: Mapped[str] = mapped_column(Text, default='["read"]')
    purpose: Mapped[str] = mapped_column(String(300))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ChurnRiskScore(Base):
    """Computed tenant-level churn/renewal risk for customer success."""
    __tablename__ = "churn_risk_scores"
    __table_args__ = (UniqueConstraint("organization_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    factors_json: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    recovery_owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Security Governance ───────────────────────────────────────────────────────

class SecurityAlert(Base):
    """Platform-level security signal (impossible login, privilege escalation, etc.)."""
    __tablename__ = "security_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    alert_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    evidence_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    resolved_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    response_action: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class JitAccessGrant(Base):
    """Time-limited privileged access grant with automatic expiry."""
    __tablename__ = "jit_access_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    grantee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    granted_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    permission: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(300))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AccessCertificationCycle(Base):
    """Periodic access review cycle."""
    __tablename__ = "access_certification_cycles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(200))
    initiated_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AccessCertificationItem(Base):
    """One access record to certify in a cycle."""
    __tablename__ = "access_certification_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    cycle_id: Mapped[str] = mapped_column(
        ForeignKey("access_certification_cycles.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    permission: Mapped[str] = mapped_column(String(100))
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str | None] = mapped_column(String(20))
    decision_reason: Mapped[str | None] = mapped_column(String(300))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EmergencyContainmentEvent(Base):
    """Record of an emergency containment action."""
    __tablename__ = "emergency_containment_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    actions_taken_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(300))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Reliability & Incident Operations ────────────────────────────────────────

class IncidentRecord(Base):
    """Platform incident with commander, timeline and impact."""
    __tablename__ = "incident_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(20), default="p2", index=True)
    commander_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    affected_features_json: Mapped[str | None] = mapped_column(Text)
    affected_org_count: Mapped[int] = mapped_column(Integer, default=0)
    mitigation: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    customer_communication: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class IncidentEvent(Base):
    """Timeline entry for an incident."""
    __tablename__ = "incident_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_records.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class JobRecord(Base):
    """Background job tracking for the admin job console."""
    __tablename__ = "job_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    job_type: Mapped[str] = mapped_column(String(60), index=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    payload_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Release & Feature Governance ─────────────────────────────────────────────

class FeatureRolloutConfig(Base):
    """Progressive rollout configuration for a feature flag."""
    __tablename__ = "feature_rollout_configs"
    __table_args__ = (UniqueConstraint("feature_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    feature_key: Mapped[str] = mapped_column(String(60), index=True)
    current_stage: Mapped[str] = mapped_column(String(30), default="internal")
    stages_json: Mapped[str] = mapped_column(Text)
    guardrail_error_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    guardrail_ticket_threshold: Mapped[int | None] = mapped_column(Integer)
    auto_rollback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rollback_count: Mapped[int] = mapped_column(Integer, default=0)
    last_rollback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ConfigVersion(Base):
    """Versioned configuration snapshot with diff and rollback point."""
    __tablename__ = "config_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    config_key: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    value_json: Mapped[str] = mapped_column(Text)
    previous_value_json: Mapped[str | None] = mapped_column(Text)
    diff_summary: Mapped[str | None] = mapped_column(Text)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Integration Operations ────────────────────────────────────────────────────

class ProviderCredential(Base):
    """Provider credential lifecycle tracking (no secret values stored here)."""
    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    credential_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class WebhookEvent(Base):
    """Inbound webhook events from providers with replay support."""
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    event_type: Mapped[str | None] = mapped_column(String(60))
    signature_valid: Mapped[bool | None] = mapped_column(Boolean)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    related_record_id: Mapped[str | None] = mapped_column(String(36))
    error: Mapped[str | None] = mapped_column(Text)
    replay_count: Mapped[int] = mapped_column(Integer, default=0)
    last_replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class IntegrationCertification(Base):
    """Pre-production integration checklist per tenant."""
    __tablename__ = "integration_certifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    integration: Mapped[str] = mapped_column(String(40))
    sandbox_tested: Mapped[bool] = mapped_column(Boolean, default=False)
    callback_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    refund_tested: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    certified_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


# ── Data Governance ───────────────────────────────────────────────────────────

class DataInventoryItem(Base):
    """Catalogue of personal/financial data holdings per module."""
    __tablename__ = "data_inventory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    module: Mapped[str] = mapped_column(String(60), index=True)
    data_category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300))
    table_name: Mapped[str | None] = mapped_column(String(80))
    legal_basis: Mapped[str | None] = mapped_column(String(100))
    retention_days: Mapped[int | None] = mapped_column(Integer)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TenantDataExportRequest(Base):
    """Structured data export request from a tenant."""
    __tablename__ = "tenant_data_export_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    requested_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    scope_json: Mapped[str | None] = mapped_column(Text)
    file_manifest_json: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RetentionPolicy(Base):
    """Data retention policy per data category."""
    __tablename__ = "retention_policies"
    __table_args__ = (UniqueConstraint("data_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    data_category: Mapped[str] = mapped_column(String(60), index=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    action_on_expiry: Mapped[str] = mapped_column(String(20), default="archive")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    legal_hold_override: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(300))
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class PrivacyRequest(Base):
    """DSR (data subject request) workflow."""
    __tablename__ = "privacy_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    request_type: Mapped[str] = mapped_column(String(30), index=True)
    subject_email: Mapped[str] = mapped_column(String(254))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    assigned_to_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verification_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_url: Mapped[str | None] = mapped_column(String(500))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── AI Governance ─────────────────────────────────────────────────────────────

class ModelRegistryEntry(Base):
    """AI model/prompt version registry per feature."""
    __tablename__ = "model_registry_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    feature: Mapped[str] = mapped_column(String(80), index=True)
    model_id: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    knowledge_source: Mapped[str | None] = mapped_column(String(200))
    fallback_behavior: Mapped[str | None] = mapped_column(String(100))
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deployed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiCostBudget(Base):
    """Per-tenant/feature AI token and cost budgets."""
    __tablename__ = "ai_cost_budgets"
    __table_args__ = (UniqueConstraint("organization_id", "feature"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    feature: Mapped[str] = mapped_column(String(80))
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_cost_limit_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    on_breach: Mapped[str] = mapped_column(String(30), default="downgrade")
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AiKillSwitch(Base):
    """Emergency AI feature disable control."""
    __tablename__ = "ai_kill_switches"
    __table_args__ = (UniqueConstraint("feature"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    feature: Mapped[str] = mapped_column(String(80), index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(300))
    requires_human_approval_above_risk: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    disabled_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ModelOutcomeRecord(Base):
    """Tracks AI recommendation accuracy and financial impact per vertical."""
    __tablename__ = "model_outcome_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    feature: Mapped[str] = mapped_column(String(80), index=True)
    vertical: Mapped[str] = mapped_column(String(40), index=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(String(36))
    outcome: Mapped[str] = mapped_column(String(20))
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    financial_impact_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(String(300))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
