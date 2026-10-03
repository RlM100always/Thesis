"""Admin platform control-plane — all 50 capabilities from ADMIN_PLATFORM_VISION.md.

Routes are grouped by phase:
  Phase 1 — Foundation
  Phase 2 — Revenue Operations
  Phase 3 — Controlled Operations (support, security, reliability, release, integration)
  Phase 4 — Governance (data & AI)

All routes require platform-admin authentication via get_platform_admin.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_platform_admin
from .database import get_db
from .domain_models import (
    AuditLog, Branch, Membership, Organization, Product, SalesOrder, User,
    UserSession,
)
from .admin_models import (
    AccessCertificationCycle, AccessCertificationItem, AiCostBudget,
    AiKillSwitch, BillingLedgerEntry, ChurnRiskScore, CollectionStatement,
    CommercialOverride, ConfigVersion, DataInventoryItem,
    DecisionJournal, EmergencyContainmentEvent, FeatureRolloutConfig,
    AdminMissionItem, IncidentEvent, IncidentRecord, IntegrationCertification,
    JitAccessGrant, JobRecord, ModelOutcomeRecord, ModelRegistryEntry,
    OrgPlanSubscription, Plan, PrivacyRequest, ProviderCredential,
    RetentionPolicy, SecurityAlert, ShiftHandover, SupportCase,
    SupportCaseEvent, SupportSession, TenantDataExportRequest,
    TenantStateEvent, UsageAggregate, UsageEvent, WebhookEvent,
)

router = APIRouter(prefix="/api/admin", tags=["admin-platform"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(get_platform_admin)]

TENANT_STATES = ("lead", "trial", "onboarding", "live", "at_risk",
                 "grace_period", "suspended", "offboarded")
VALID_TRANSITIONS = {
    "lead": ("trial",),
    "trial": ("onboarding", "offboarded"),
    "onboarding": ("live", "suspended", "offboarded"),
    "live": ("at_risk", "suspended", "offboarded"),
    "at_risk": ("live", "grace_period", "suspended"),
    "grace_period": ("live", "suspended"),
    "suspended": ("live", "offboarded"),
    "offboarded": (),
}


def _money(v) -> float:
    return round(float(v or 0), 2)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — FOUNDATION
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. Admin Mission Queue ────────────────────────────────────────────────────

@router.get("/mission-queue")
def get_admin_mission_queue(admin: Admin, db: Db, status: str = "open"):
    """Auto-generated + manually added admin tasks, priority ordered."""
    items = list(db.scalars(
        select(AdminMissionItem)
        .where(AdminMissionItem.status == status)
        .order_by(AdminMissionItem.priority.desc(), AdminMissionItem.created_at)
        .limit(100)
    ))
    org_ids = {i.affected_org_id for i in items if i.affected_org_id}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"count": len(items), "items": [
        {
            "id": i.id, "kind": i.kind, "priority": i.priority,
            "title": i.title, "description": i.description,
            "affected_org_name": orgs.get(i.affected_org_id),
            "affected_org_id": i.affected_org_id,
            "estimated_impact": i.estimated_impact,
            "recommended_action": i.recommended_action,
            "status": i.status, "deadline_at": i.deadline_at.isoformat() if i.deadline_at else None,
            "created_at": i.created_at.isoformat(),
        }
        for i in items
    ]}


@router.post("/mission-queue/generate")
def generate_mission_queue(admin: Admin, db: Db):
    """Scan real tables and create mission items for actionable signals."""
    now = _utcnow()
    created = 0

    # Stale tenants — no sale in 14 days
    cutoff14 = now - timedelta(days=14)
    last_sale = dict(db.execute(
        select(SalesOrder.organization_id, func.max(SalesOrder.sold_at))
        .group_by(SalesOrder.organization_id)
    ).all())
    active_orgs = list(db.scalars(
        select(Organization).where(
            Organization.active.is_(True), Organization.suspended_at.is_(None)
        )
    ))
    existing_kinds_orgs = {
        (i.kind, i.affected_org_id)
        for i in db.scalars(select(AdminMissionItem).where(AdminMissionItem.status == "open"))
    }
    for org in active_orgs:
        last = last_sale.get(org.id)
        if last is None or (last.replace(tzinfo=last.tzinfo or timezone.utc) < cutoff14):
            key = ("stale_tenant", org.id)
            if key not in existing_kinds_orgs:
                age = (now - (last.replace(tzinfo=timezone.utc) if last else org.created_at.replace(tzinfo=timezone.utc))).days
                db.add(AdminMissionItem(
                    kind="stale_tenant", priority=min(90, 30 + age * 2),
                    title=f"⚠ {org.name} — {age} দিন ধরে কোনো বিক্রি নেই",
                    description="Tenant inactive: potential churn or onboarding blockage.",
                    affected_org_id=org.id,
                    estimated_impact="Revenue risk",
                    recommended_action="Review onboarding checklist or contact tenant owner.",
                ))
                created += 1

    # Expiring JIT grants
    exp_cutoff = now + timedelta(hours=1)
    for grant in db.scalars(
        select(JitAccessGrant).where(
            JitAccessGrant.revoked_at.is_(None),
            JitAccessGrant.expires_at <= exp_cutoff,
            JitAccessGrant.expires_at > now,
        )
    ):
        key = ("jit_expiring", grant.id)
        if ("jit_expiring", grant.grantee_id) not in existing_kinds_orgs:
            db.add(AdminMissionItem(
                kind="jit_expiring", priority=70,
                title="JIT access মেয়াদ শেষ হতে চলেছে",
                description=f"Grant {grant.id} expires within 1 hour.",
                affected_org_id=grant.organization_id,
                estimated_impact="Access control",
                recommended_action="Review and extend or allow expiry.",
            ))
            created += 1

    db.commit()
    return {"created": created, "message": f"{created}টি নতুন mission item তৈরি হয়েছে।"}


class MissionItemIn(BaseModel):
    kind: str = Field(max_length=40)
    priority: int = Field(default=50, ge=1, le=100)
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    affected_org_id: str | None = None
    estimated_impact: str | None = None
    recommended_action: str | None = None
    deadline_at: datetime | None = None


@router.post("/mission-queue")
def create_mission_item(payload: MissionItemIn, admin: Admin, db: Db):
    item = AdminMissionItem(**payload.model_dump())
    db.add(item)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.mission_item_created",
                    entity_type="admin_mission_item", entity_id=item.id))
    db.commit()
    return {"id": item.id, "status": "created"}


class MissionStatusIn(BaseModel):
    status: Literal["open", "in_progress", "resolved", "dismissed"]


@router.patch("/mission-queue/{item_id}")
def update_mission_item_status(item_id: str, payload: MissionStatusIn, admin: Admin, db: Db):
    item = db.get(AdminMissionItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = payload.status
    if payload.status == "resolved":
        item.resolved_at = _utcnow()
        item.resolved_by_id = admin.id
    db.add(AuditLog(actor_user_id=admin.id, action="platform.mission_item_updated",
                    entity_type="admin_mission_item", entity_id=item.id,
                    metadata_json=json.dumps({"status": payload.status})))
    db.commit()
    return {"id": item.id, "status": item.status}


# ── 2. Universal Command Search ───────────────────────────────────────────────

@router.get("/search")
def universal_search(admin: Admin, db: Db, q: str = Query(min_length=2, max_length=100)):
    """Cross-entity search: tenants, users, support cases, incidents."""
    like = f"%{q}%"
    results = []

    orgs = list(db.scalars(
        select(Organization).where(
            Organization.name.ilike(like) | Organization.slug.ilike(like)
        ).limit(8)
    ))
    for org in orgs:
        results.append({"type": "organization", "id": org.id, "label": org.name,
                        "sub": org.slug, "link_type": "org", "link_id": org.id})

    users = list(db.scalars(
        select(User).where(
            User.email.ilike(like) | User.display_name.ilike(like)
        ).limit(8)
    ))
    for user in users:
        results.append({"type": "user", "id": user.id, "label": user.display_name,
                        "sub": user.email, "link_type": "user", "link_id": user.id})

    cases = list(db.scalars(
        select(SupportCase).where(SupportCase.subject.ilike(like)).limit(5)
    ))
    for c in cases:
        results.append({"type": "support_case", "id": c.id, "label": c.subject,
                        "sub": c.status, "link_type": "support_case", "link_id": c.id})

    incidents = list(db.scalars(
        select(IncidentRecord).where(IncidentRecord.title.ilike(like)).limit(5)
    ))
    for inc in incidents:
        results.append({"type": "incident", "id": inc.id, "label": inc.title,
                        "sub": inc.severity, "link_type": "incident", "link_id": inc.id})

    return {"query": q, "count": len(results), "results": results}


# ── 4. Shift Handover ─────────────────────────────────────────────────────────

class ShiftHandoverIn(BaseModel):
    to_admin_id: str | None = None
    summary: str = Field(min_length=5)
    open_incidents: int = 0
    pending_approvals: int = 0
    priority_org_ids: list[str] = Field(default_factory=list)


@router.post("/shift-handovers")
def create_shift_handover(payload: ShiftHandoverIn, admin: Admin, db: Db):
    handover = ShiftHandover(
        from_admin_id=admin.id,
        to_admin_id=payload.to_admin_id,
        summary=payload.summary,
        open_incidents=payload.open_incidents,
        pending_approvals=payload.pending_approvals,
        priority_org_ids_json=json.dumps(payload.priority_org_ids),
    )
    db.add(handover)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.shift_handover_created",
                    entity_type="shift_handover", entity_id=handover.id))
    db.commit()
    return {"id": handover.id, "status": "created"}


@router.get("/shift-handovers")
def list_shift_handovers(admin: Admin, db: Db):
    rows = list(db.scalars(
        select(ShiftHandover).order_by(ShiftHandover.created_at.desc()).limit(30)
    ))
    admin_ids = {r.from_admin_id for r in rows} | {r.to_admin_id for r in rows if r.to_admin_id}
    admins = {u.id: u.display_name for u in db.scalars(
        select(User).where(User.id.in_(admin_ids or {""}))
    )}
    return {"handovers": [{
        "id": h.id,
        "from_admin": admins.get(h.from_admin_id, h.from_admin_id),
        "to_admin": admins.get(h.to_admin_id) if h.to_admin_id else None,
        "summary": h.summary,
        "open_incidents": h.open_incidents,
        "pending_approvals": h.pending_approvals,
        "priority_org_ids": json.loads(h.priority_org_ids_json or "[]"),
        "acknowledged_at": h.acknowledged_at.isoformat() if h.acknowledged_at else None,
        "created_at": h.created_at.isoformat(),
    } for h in rows]}


@router.post("/shift-handovers/{handover_id}/acknowledge")
def acknowledge_handover(handover_id: str, admin: Admin, db: Db):
    handover = db.get(ShiftHandover, handover_id)
    if handover is None:
        raise HTTPException(status_code=404, detail="Handover not found")
    if handover.acknowledged_at:
        raise HTTPException(status_code=409, detail="Already acknowledged")
    handover.acknowledged_at = _utcnow()
    db.commit()
    return {"id": handover_id, "acknowledged_at": handover.acknowledged_at.isoformat()}


# ── 5. Decision Journal ───────────────────────────────────────────────────────

class DecisionJournalIn(BaseModel):
    action_kind: str = Field(max_length=60)
    affected_org_id: str | None = None
    decision_reason: str = Field(min_length=5)
    evidence_url: str | None = None
    approver_id: str | None = None
    expected_outcome: str | None = None
    correlation_id: str | None = None


@router.post("/decision-journal")
def create_decision_journal(payload: DecisionJournalIn, admin: Admin, db: Db):
    entry = DecisionJournal(actor_admin_id=admin.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    return {"id": entry.id, "created_at": entry.created_at.isoformat()}


@router.get("/decision-journal")
def list_decision_journal(admin: Admin, db: Db, action_kind: str | None = None, limit: int = 50):
    q = select(DecisionJournal).order_by(DecisionJournal.created_at.desc())
    if action_kind:
        q = q.where(DecisionJournal.action_kind == action_kind)
    rows = list(db.scalars(q.limit(min(limit, 200))))
    actor_ids = {r.actor_admin_id for r in rows}
    actors = {u.id: u.display_name for u in db.scalars(
        select(User).where(User.id.in_(actor_ids or {""}))
    )}
    org_ids = {r.affected_org_id for r in rows if r.affected_org_id}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"count": len(rows), "entries": [{
        "id": r.id, "action_kind": r.action_kind,
        "actor": actors.get(r.actor_admin_id), "affected_org": orgs.get(r.affected_org_id),
        "decision_reason": r.decision_reason, "expected_outcome": r.expected_outcome,
        "evidence_url": r.evidence_url, "created_at": r.created_at.isoformat(),
    } for r in rows]}


# ── 6. Tenant State Machine ───────────────────────────────────────────────────

class TenantStateTransitionIn(BaseModel):
    to_state: str
    reason: str | None = None


@router.post("/organizations/{org_id}/state-transition")
def transition_tenant_state(
    org_id: str, payload: TenantStateTransitionIn, admin: Admin, db: Db
):
    """Formal lifecycle transition with validation and audit trail."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if payload.to_state not in TENANT_STATES:
        raise HTTPException(status_code=422, detail=f"Unknown state: {payload.to_state}")

    last_event = db.scalar(
        select(TenantStateEvent)
        .where(TenantStateEvent.organization_id == org_id)
        .order_by(TenantStateEvent.created_at.desc())
    )
    current_state = last_event.to_state if last_event else "onboarding"
    allowed = VALID_TRANSITIONS.get(current_state, ())
    if payload.to_state not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Transition from '{current_state}' to '{payload.to_state}' is not allowed. "
                   f"Allowed: {allowed}"
        )

    event = TenantStateEvent(
        organization_id=org_id,
        from_state=current_state,
        to_state=payload.to_state,
        reason=payload.reason,
        actor_admin_id=admin.id,
    )
    db.add(event)
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.tenant_state_transition",
        entity_type="organization", entity_id=org_id,
        metadata_json=json.dumps({"from": current_state, "to": payload.to_state}),
    ))
    db.commit()
    return {"org_id": org_id, "from_state": current_state, "to_state": payload.to_state}


@router.get("/organizations/{org_id}/state-history")
def get_tenant_state_history(org_id: str, admin: Admin, db: Db):
    events = list(db.scalars(
        select(TenantStateEvent)
        .where(TenantStateEvent.organization_id == org_id)
        .order_by(TenantStateEvent.created_at)
    ))
    return {"org_id": org_id, "events": [
        {"from_state": e.from_state, "to_state": e.to_state,
         "reason": e.reason, "created_at": e.created_at.isoformat()}
        for e in events
    ]}


# ── 9. Tenant Health Score ────────────────────────────────────────────────────

@router.get("/organizations/{org_id}/health-score")
def get_tenant_health_score(org_id: str, admin: Admin, db: Db):
    """Explainable composite health score from real data."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    now = _utcnow()
    factors = {}

    # Recent activity (30 days)
    cutoff30 = now - timedelta(days=30)
    recent_sales = db.scalar(
        select(func.count(SalesOrder.id)).where(
            SalesOrder.organization_id == org_id, SalesOrder.sold_at >= cutoff30
        )
    ) or 0
    factors["recent_activity"] = min(30, recent_sales * 2) if recent_sales > 0 else 0

    # Active members
    member_count = db.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == org_id, Membership.active.is_(True)
        )
    ) or 0
    factors["team_adoption"] = min(20, member_count * 5)

    # Open support cases (negative)
    open_cases = db.scalar(
        select(func.count(SupportCase.id)).where(
            SupportCase.organization_id == org_id,
            SupportCase.status.in_(("open", "pending")),
        )
    ) or 0
    factors["support_pressure"] = -min(20, open_cases * 5)

    # Security (no recent security alerts = positive)
    open_alerts = db.scalar(
        select(func.count(SecurityAlert.id)).where(
            SecurityAlert.organization_id == org_id,
            SecurityAlert.status == "open",
        )
    ) or 0
    factors["security"] = 20 if open_alerts == 0 else max(-10, 20 - open_alerts * 10)

    # Suspension history
    if org.suspended_at:
        factors["suspension_history"] = -10
    else:
        factors["suspension_history"] = 10

    total = max(0, min(100, sum(factors.values()) + 20))  # baseline +20
    risk_level = "low" if total >= 70 else "medium" if total >= 40 else "high"

    return {
        "org_id": org_id, "org_name": org.name,
        "score": total, "risk_level": risk_level,
        "factors": factors,
        "recommendation": (
            "Healthy tenant." if risk_level == "low"
            else "Consider proactive outreach — activity declining."
            if risk_level == "medium"
            else "High-risk tenant: immediate intervention recommended."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — REVENUE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# ── 11. Plan and Entitlement Engine ──────────────────────────────────────────

@router.get("/plans")
def list_plans(admin: Admin, db: Db):
    plans = list(db.scalars(select(Plan).order_by(Plan.price_bdt)))
    return {"plans": [
        {"id": p.id, "code": p.code, "name": p.name, "price_bdt": _money(p.price_bdt),
         "billing_cycle": p.billing_cycle, "branch_limit": p.branch_limit,
         "employee_limit": p.employee_limit, "ai_token_quota": p.ai_token_quota,
         "support_tier": p.support_tier, "active": p.active}
        for p in plans
    ]}


class PlanIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    price_bdt: Decimal = Field(ge=Decimal("0"))
    billing_cycle: Literal["monthly", "quarterly", "annual"] = "monthly"
    branch_limit: int | None = None
    employee_limit: int | None = None
    transaction_limit: int | None = None
    ai_token_quota: int | None = None
    sms_quota: int | None = None
    whatsapp_quota: int | None = None
    support_tier: str = "standard"
    modules_json: str | None = None


@router.post("/plans")
def create_plan(payload: PlanIn, admin: Admin, db: Db):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.plan_created",
                    entity_type="plan", entity_id=plan.id,
                    metadata_json=json.dumps({"code": plan.code})))
    db.commit()
    return {"id": plan.id, "code": plan.code}


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: str, payload: PlanIn, admin: Admin, db: Db):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    for k, v in payload.model_dump().items():
        setattr(plan, k, v)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.plan_updated",
                    entity_type="plan", entity_id=plan.id))
    db.commit()
    return {"id": plan.id, "status": "updated"}


class AssignPlanIn(BaseModel):
    plan_id: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None


@router.post("/organizations/{org_id}/subscription")
def assign_subscription(org_id: str, payload: AssignPlanIn, admin: Admin, db: Db):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    plan = db.get(Plan, payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    sub = OrgPlanSubscription(
        organization_id=org_id, plan_id=payload.plan_id,
        started_at=payload.starts_at or _utcnow(),
        ends_at=payload.ends_at, granted_by_id=admin.id,
    )
    db.add(sub)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.subscription_assigned",
                    entity_type="organization", entity_id=org_id,
                    metadata_json=json.dumps({"plan_code": plan.code})))
    db.commit()
    return {"id": sub.id, "status": "assigned"}


@router.get("/organizations/{org_id}/subscription")
def get_subscription(org_id: str, admin: Admin, db: Db):
    sub = db.scalar(
        select(OrgPlanSubscription)
        .where(OrgPlanSubscription.organization_id == org_id, OrgPlanSubscription.status == "active")
        .order_by(OrgPlanSubscription.started_at.desc())
    )
    if sub is None:
        return {"subscription": None}
    plan = db.get(Plan, sub.plan_id)
    return {"subscription": {
        "id": sub.id, "plan_id": sub.plan_id,
        "plan_name": plan.name if plan else None,
        "started_at": sub.started_at.isoformat(),
        "ends_at": sub.ends_at.isoformat() if sub.ends_at else None,
        "status": sub.status,
    }}


# ── 12. Commercial Override ───────────────────────────────────────────────────

class CommercialOverrideIn(BaseModel):
    kind: str = Field(max_length=40)
    description: str = Field(max_length=300)
    value_json: str
    expires_at: datetime | None = None


@router.post("/organizations/{org_id}/overrides")
def add_commercial_override(org_id: str, payload: CommercialOverrideIn, admin: Admin, db: Db):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    override = CommercialOverride(
        organization_id=org_id, kind=payload.kind, description=payload.description,
        value_json=payload.value_json, granted_by_id=admin.id, expires_at=payload.expires_at,
    )
    db.add(override)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.commercial_override_added",
                    entity_type="organization", entity_id=org_id,
                    metadata_json=json.dumps({"kind": payload.kind})))
    db.commit()
    return {"id": override.id, "status": "created"}


@router.get("/organizations/{org_id}/overrides")
def list_commercial_overrides(org_id: str, admin: Admin, db: Db):
    rows = list(db.scalars(
        select(CommercialOverride).where(
            CommercialOverride.organization_id == org_id,
            CommercialOverride.active.is_(True),
        )
    ))
    return {"overrides": [
        {"id": r.id, "kind": r.kind, "description": r.description,
         "expires_at": r.expires_at.isoformat() if r.expires_at else None,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]}


# ── 13. Usage Metering ────────────────────────────────────────────────────────

@router.get("/usage")
def get_platform_usage(admin: Admin, db: Db, period_month: str | None = None):
    """Cross-tenant usage aggregates for the given month (YYYY-MM)."""
    month = period_month or _utcnow().strftime("%Y-%m")
    rows = list(db.execute(
        select(
            UsageAggregate.organization_id,
            UsageAggregate.metric,
            UsageAggregate.total,
        ).where(UsageAggregate.period_month == month)
    ).all())
    org_ids = {r.organization_id for r in rows}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    by_org: dict[str, dict] = {}
    for r in rows:
        org_entry = by_org.setdefault(r.organization_id, {
            "org_id": r.organization_id, "org_name": orgs.get(r.organization_id),
            "metrics": {},
        })
        org_entry["metrics"][r.metric] = _money(r.total)
    return {"period_month": month, "count": len(by_org), "tenants": list(by_org.values())}


class UsageEventIn(BaseModel):
    organization_id: str
    metric: str = Field(max_length=40)
    quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    reference_id: str | None = None


@router.post("/usage/events")
def record_usage_event(payload: UsageEventIn, admin: Admin, db: Db):
    event = UsageEvent(**payload.model_dump())
    db.add(event)
    month = _utcnow().strftime("%Y-%m")
    agg = db.scalar(
        select(UsageAggregate).where(
            UsageAggregate.organization_id == payload.organization_id,
            UsageAggregate.metric == payload.metric,
            UsageAggregate.period_month == month,
        )
    )
    if agg is None:
        agg = UsageAggregate(
            organization_id=payload.organization_id,
            metric=payload.metric, period_month=month, total=payload.quantity,
        )
        db.add(agg)
    else:
        agg.total = Decimal(str(agg.total)) + payload.quantity
    db.commit()
    return {"status": "recorded"}


# ── 14. Billing Ledger ────────────────────────────────────────────────────────

@router.get("/organizations/{org_id}/billing")
def get_billing_ledger(org_id: str, admin: Admin, db: Db, limit: int = 50):
    entries = list(db.scalars(
        select(BillingLedgerEntry)
        .where(BillingLedgerEntry.organization_id == org_id)
        .order_by(BillingLedgerEntry.created_at.desc())
        .limit(min(limit, 200))
    ))
    balance = sum(
        _money(e.amount_bdt) * (1 if e.entry_type in ("invoice", "overage") else -1)
        for e in entries
    )
    return {
        "org_id": org_id, "outstanding_bdt": balance,
        "entries": [
            {"id": e.id, "entry_type": e.entry_type, "amount_bdt": _money(e.amount_bdt),
             "description": e.description, "status": e.status,
             "period_month": e.period_month,
             "due_at": e.due_at.isoformat() if e.due_at else None,
             "paid_at": e.paid_at.isoformat() if e.paid_at else None,
             "created_at": e.created_at.isoformat()}
            for e in entries
        ],
    }


class BillingEntryIn(BaseModel):
    entry_type: Literal["invoice", "payment", "credit_note", "refund", "overage"]
    amount_bdt: Decimal = Field(gt=Decimal("0"))
    description: str = Field(max_length=300)
    period_month: str | None = None
    due_at: datetime | None = None


@router.post("/organizations/{org_id}/billing")
def add_billing_entry(org_id: str, payload: BillingEntryIn, admin: Admin, db: Db):
    entry = BillingLedgerEntry(
        organization_id=org_id, created_by_id=admin.id, **payload.model_dump()
    )
    db.add(entry)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.billing_entry_added",
                    entity_type="organization", entity_id=org_id,
                    metadata_json=json.dumps({"type": payload.entry_type, "amount": str(payload.amount_bdt)})))
    db.commit()
    return {"id": entry.id, "status": "created"}


# ── 15. Collection Reconciliation ─────────────────────────────────────────────

@router.get("/reconciliation")
def list_collection_statements(admin: Admin, db: Db, status: str = "unmatched"):
    rows = list(db.scalars(
        select(CollectionStatement)
        .where(CollectionStatement.status == status)
        .order_by(CollectionStatement.received_at.desc())
        .limit(100)
    ))
    return {"count": len(rows), "statements": [
        {"id": r.id, "provider": r.provider, "reference": r.reference,
         "amount_bdt": _money(r.amount_bdt),
         "received_at": r.received_at.isoformat(), "status": r.status,
         "notes": r.notes}
        for r in rows
    ]}


class CollectionStatementIn(BaseModel):
    provider: Literal["bkash", "nagad", "bank", "manual"]
    reference: str = Field(max_length=100)
    amount_bdt: Decimal = Field(gt=Decimal("0"))
    received_at: datetime
    organization_id: str | None = None
    notes: str | None = None


@router.post("/reconciliation")
def add_collection_statement(payload: CollectionStatementIn, admin: Admin, db: Db):
    stmt = CollectionStatement(**payload.model_dump())
    db.add(stmt)
    db.commit()
    return {"id": stmt.id, "status": "created"}


class MatchStatementIn(BaseModel):
    matched_invoice_id: str


@router.post("/reconciliation/{stmt_id}/match")
def match_collection_statement(stmt_id: str, payload: MatchStatementIn, admin: Admin, db: Db):
    stmt = db.get(CollectionStatement, stmt_id)
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    stmt.matched_invoice_id = payload.matched_invoice_id
    stmt.status = "matched"
    db.add(AuditLog(actor_user_id=admin.id, action="platform.collection_matched",
                    entity_type="collection_statement", entity_id=stmt_id))
    db.commit()
    return {"id": stmt_id, "status": "matched"}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — CONTROLLED OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# ── 16. Support Cases ─────────────────────────────────────────────────────────

@router.get("/support-cases")
def list_support_cases(
    admin: Admin, db: Db,
    status: str = "open", org_id: str | None = None, limit: int = 50,
):
    q = select(SupportCase).where(SupportCase.status == status)
    if org_id:
        q = q.where(SupportCase.organization_id == org_id)
    cases = list(db.scalars(q.order_by(SupportCase.created_at.desc()).limit(min(limit, 200))))
    org_ids = {c.organization_id for c in cases if c.organization_id}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"count": len(cases), "cases": [
        {"id": c.id, "subject": c.subject, "priority": c.priority, "status": c.status,
         "source": c.source, "org_name": orgs.get(c.organization_id),
         "org_id": c.organization_id, "affected_feature": c.affected_feature,
         "sla_response_due_at": c.sla_response_due_at.isoformat() if c.sla_response_due_at else None,
         "sla_resolution_due_at": c.sla_resolution_due_at.isoformat() if c.sla_resolution_due_at else None,
         "first_response_at": c.first_response_at.isoformat() if c.first_response_at else None,
         "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
         "created_at": c.created_at.isoformat()}
        for c in cases
    ]}


class SupportCaseIn(BaseModel):
    organization_id: str | None = None
    source: Literal["call", "email", "whatsapp", "in_app", "manual"] = "manual"
    subject: str = Field(min_length=3, max_length=300)
    description: str | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    affected_feature: str | None = None


SLA_HOURS = {
    "urgent": (1, 4),
    "high": (4, 24),
    "normal": (8, 72),
    "low": (24, 168),
}


@router.post("/support-cases")
def create_support_case(payload: SupportCaseIn, admin: Admin, db: Db):
    now = _utcnow()
    response_h, resolution_h = SLA_HOURS[payload.priority]
    case = SupportCase(
        **payload.model_dump(),
        created_by_id=admin.id,
        sla_response_due_at=now + timedelta(hours=response_h),
        sla_resolution_due_at=now + timedelta(hours=resolution_h),
    )
    db.add(case)
    db.flush()  # assigns case.id before child record
    db.add(SupportCaseEvent(
        case_id=case.id, event_type="created", actor_id=admin.id,
        body=f"Case created by {admin.display_name}",
    ))
    db.commit()
    return {"id": case.id, "status": "created"}


class CaseStatusIn(BaseModel):
    status: Literal["open", "pending", "resolved", "closed"]
    comment: str | None = None


@router.patch("/support-cases/{case_id}")
def update_case_status(case_id: str, payload: CaseStatusIn, admin: Admin, db: Db):
    case = db.get(SupportCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    case.status = payload.status
    if payload.status == "resolved" and not case.resolved_at:
        case.resolved_at = _utcnow()
    if not case.first_response_at and payload.status in ("pending", "resolved"):
        case.first_response_at = _utcnow()
    db.add(SupportCaseEvent(
        case_id=case_id, event_type="status_change", actor_id=admin.id,
        body=payload.comment or f"Status changed to {payload.status}",
        metadata_json=json.dumps({"new_status": payload.status}),
    ))
    db.commit()
    return {"id": case_id, "status": payload.status}


@router.get("/support-cases/{case_id}/events")
def get_case_events(case_id: str, admin: Admin, db: Db):
    events = list(db.scalars(
        select(SupportCaseEvent)
        .where(SupportCaseEvent.case_id == case_id)
        .order_by(SupportCaseEvent.created_at)
    ))
    return {"case_id": case_id, "events": [
        {"id": e.id, "event_type": e.event_type, "body": e.body,
         "created_at": e.created_at.isoformat()}
        for e in events
    ]}


# ── 17. SLA Summary ───────────────────────────────────────────────────────────

@router.get("/support-cases/sla-summary")
def support_sla_summary(admin: Admin, db: Db):
    now = _utcnow()
    open_cases = list(db.scalars(
        select(SupportCase).where(SupportCase.status.in_(("open", "pending")))
    ))
    breached_response = sum(
        1 for c in open_cases
        if c.sla_response_due_at and c.sla_response_due_at < now and not c.first_response_at
    )
    breached_resolution = sum(
        1 for c in open_cases
        if c.sla_resolution_due_at and c.sla_resolution_due_at < now
    )
    at_risk = sum(
        1 for c in open_cases
        if c.sla_response_due_at and now < c.sla_response_due_at
        < now + timedelta(hours=2)
    )
    return {
        "total_open": len(open_cases),
        "response_breached": breached_response,
        "resolution_breached": breached_resolution,
        "at_risk_response": at_risk,
    }


# ── 18. Consented Support Sessions ───────────────────────────────────────────

class SupportSessionIn(BaseModel):
    organization_id: str
    case_id: str | None = None
    purpose: str = Field(max_length=300)
    permissions: list[str] = Field(default=["read"])
    duration_minutes: int = Field(default=60, ge=15, le=480)


@router.post("/support-sessions")
def create_support_session(payload: SupportSessionIn, admin: Admin, db: Db):
    org = db.get(Organization, payload.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    session = SupportSession(
        organization_id=payload.organization_id,
        agent_id=admin.id,
        case_id=payload.case_id,
        purpose=payload.purpose,
        permissions_json=json.dumps(payload.permissions),
        expires_at=_utcnow() + timedelta(minutes=payload.duration_minutes),
    )
    db.add(session)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.support_session_created",
                    entity_type="organization", entity_id=payload.organization_id,
                    metadata_json=json.dumps({"purpose": payload.purpose})))
    db.commit()
    return {"id": session.id, "expires_at": session.expires_at.isoformat()}


@router.get("/support-sessions")
def list_support_sessions(admin: Admin, db: Db, active_only: bool = True):
    now = _utcnow()
    q = select(SupportSession)
    if active_only:
        q = q.where(SupportSession.expires_at > now, SupportSession.ended_at.is_(None))
    sessions = list(db.scalars(q.order_by(SupportSession.created_at.desc()).limit(50)))
    org_ids = {s.organization_id for s in sessions}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"sessions": [
        {"id": s.id, "org_name": orgs.get(s.organization_id), "purpose": s.purpose,
         "expires_at": s.expires_at.isoformat(), "ended_at": s.ended_at.isoformat() if s.ended_at else None,
         "created_at": s.created_at.isoformat()}
        for s in sessions
    ]}


@router.post("/support-sessions/{session_id}/end")
def end_support_session(session_id: str, admin: Admin, db: Db):
    session = db.get(SupportSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.ended_at = _utcnow()
    db.add(AuditLog(actor_user_id=admin.id, action="platform.support_session_ended",
                    entity_type="support_session", entity_id=session_id))
    db.commit()
    return {"id": session_id, "ended_at": session.ended_at.isoformat()}


# ── 20. Churn Risk ────────────────────────────────────────────────────────────

@router.post("/churn-risk/compute")
def compute_churn_risk(admin: Admin, db: Db):
    """Recompute churn risk for all active tenants from real data."""
    now = _utcnow()
    cutoff30 = now - timedelta(days=30)
    active_orgs = list(db.scalars(
        select(Organization).where(
            Organization.active.is_(True), Organization.suspended_at.is_(None)
        )
    ))
    updated = 0
    for org in active_orgs:
        recent_sales = db.scalar(
            select(func.count(SalesOrder.id)).where(
                SalesOrder.organization_id == org.id, SalesOrder.sold_at >= cutoff30
            )
        ) or 0
        open_cases = db.scalar(
            select(func.count(SupportCase.id)).where(
                SupportCase.organization_id == org.id, SupportCase.status.in_(("open", "pending"))
            )
        ) or 0
        open_alerts = db.scalar(
            select(func.count(SecurityAlert.id)).where(
                SecurityAlert.organization_id == org.id, SecurityAlert.status == "open"
            )
        ) or 0

        risk_score = Decimal("0")
        factors = {}
        if recent_sales == 0:
            risk_score += Decimal("40")
            factors["no_recent_sales"] = 40
        elif recent_sales < 5:
            risk_score += Decimal("20")
            factors["low_activity"] = 20
        if open_cases > 2:
            risk_score += Decimal("20")
            factors["repeated_issues"] = 20
        if open_alerts > 0:
            risk_score += Decimal("10")
            factors["security_risk"] = 10

        risk_level = "high" if risk_score >= 50 else "medium" if risk_score >= 25 else "low"

        existing = db.scalar(
            select(ChurnRiskScore).where(ChurnRiskScore.organization_id == org.id)
        )
        if existing:
            existing.score = risk_score
            existing.factors_json = json.dumps(factors)
            existing.risk_level = risk_level
            existing.computed_at = now
        else:
            db.add(ChurnRiskScore(
                organization_id=org.id, score=risk_score,
                factors_json=json.dumps(factors), risk_level=risk_level,
            ))
        updated += 1
    db.commit()
    return {"updated": updated, "computed_at": now.isoformat()}


@router.get("/churn-risk")
def list_churn_risk(admin: Admin, db: Db, risk_level: str | None = None):
    q = select(ChurnRiskScore)
    if risk_level:
        q = q.where(ChurnRiskScore.risk_level == risk_level)
    rows = list(db.scalars(q.order_by(ChurnRiskScore.score.desc())))
    org_ids = {r.organization_id for r in rows}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"count": len(rows), "risks": [
        {"org_id": r.organization_id, "org_name": orgs.get(r.organization_id),
         "score": _money(r.score), "risk_level": r.risk_level,
         "factors": json.loads(r.factors_json or "{}"),
         "computed_at": r.computed_at.isoformat()}
        for r in rows
    ]}


# ── 21. Security Risk Inbox ───────────────────────────────────────────────────

class SecurityAlertIn(BaseModel):
    alert_type: str = Field(max_length=50)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    organization_id: str | None = None
    user_id: str | None = None
    evidence_json: str | None = None


@router.post("/security-alerts")
def create_security_alert(payload: SecurityAlertIn, admin: Admin, db: Db):
    alert = SecurityAlert(**payload.model_dump())
    db.add(alert)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.security_alert_created",
                    entity_type="security_alert", entity_id=alert.id,
                    metadata_json=json.dumps({"type": payload.alert_type, "severity": payload.severity})))
    db.commit()
    return {"id": alert.id, "status": "created"}


@router.get("/security-alerts")
def list_security_alerts(admin: Admin, db: Db, status: str = "open"):
    alerts = list(db.scalars(
        select(SecurityAlert)
        .where(SecurityAlert.status == status)
        .order_by(SecurityAlert.created_at.desc())
        .limit(100)
    ))
    org_ids = {a.organization_id for a in alerts if a.organization_id}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"count": len(alerts), "alerts": [
        {"id": a.id, "alert_type": a.alert_type, "severity": a.severity,
         "org_name": orgs.get(a.organization_id), "status": a.status,
         "evidence": json.loads(a.evidence_json) if a.evidence_json else None,
         "created_at": a.created_at.isoformat()}
        for a in alerts
    ]}


class AlertResolveIn(BaseModel):
    response_action: str = Field(max_length=200)


@router.post("/security-alerts/{alert_id}/resolve")
def resolve_security_alert(alert_id: str, payload: AlertResolveIn, admin: Admin, db: Db):
    alert = db.get(SecurityAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "resolved"
    alert.response_action = payload.response_action
    alert.resolved_by_id = admin.id
    alert.resolved_at = _utcnow()
    db.add(AuditLog(actor_user_id=admin.id, action="platform.security_alert_resolved",
                    entity_type="security_alert", entity_id=alert_id))
    db.commit()
    return {"id": alert_id, "status": "resolved"}


# ── 22. JIT Access ────────────────────────────────────────────────────────────

class JitGrantIn(BaseModel):
    grantee_id: str
    organization_id: str | None = None
    permission: str = Field(max_length=100)
    reason: str = Field(max_length=300)
    duration_minutes: int = Field(default=60, ge=15, le=1440)


@router.post("/jit-access")
def grant_jit_access(payload: JitGrantIn, admin: Admin, db: Db):
    if admin.id == payload.grantee_id:
        raise HTTPException(status_code=409, detail="Cannot grant JIT access to yourself")
    grant = JitAccessGrant(
        grantee_id=payload.grantee_id,
        granted_by_id=admin.id,
        organization_id=payload.organization_id,
        permission=payload.permission,
        reason=payload.reason,
        expires_at=_utcnow() + timedelta(minutes=payload.duration_minutes),
    )
    db.add(grant)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.jit_access_granted",
                    entity_type="user", entity_id=payload.grantee_id,
                    metadata_json=json.dumps({"permission": payload.permission, "minutes": payload.duration_minutes})))
    db.commit()
    return {"id": grant.id, "expires_at": grant.expires_at.isoformat()}


@router.get("/jit-access")
def list_jit_grants(admin: Admin, db: Db, active_only: bool = True):
    now = _utcnow()
    q = select(JitAccessGrant)
    if active_only:
        q = q.where(JitAccessGrant.revoked_at.is_(None), JitAccessGrant.expires_at > now)
    grants = list(db.scalars(q.order_by(JitAccessGrant.created_at.desc()).limit(50)))
    user_ids = {g.grantee_id for g in grants}
    users = {u.id: u.email for u in db.scalars(
        select(User).where(User.id.in_(user_ids or {""}))
    )}
    return {"grants": [
        {"id": g.id, "grantee_email": users.get(g.grantee_id),
         "permission": g.permission, "reason": g.reason,
         "expires_at": g.expires_at.isoformat(),
         "created_at": g.created_at.isoformat()}
        for g in grants
    ]}


@router.delete("/jit-access/{grant_id}")
def revoke_jit_access(grant_id: str, admin: Admin, db: Db):
    grant = db.get(JitAccessGrant, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Grant not found")
    grant.revoked_at = _utcnow()
    grant.revoked_by_id = admin.id
    db.add(AuditLog(actor_user_id=admin.id, action="platform.jit_access_revoked",
                    entity_type="jit_access_grant", entity_id=grant_id))
    db.commit()
    return {"id": grant_id, "status": "revoked"}


# ── 24. Access Certification ──────────────────────────────────────────────────

class CertCycleIn(BaseModel):
    title: str = Field(max_length=200)
    due_days: int = Field(default=14, ge=3, le=90)


@router.post("/access-certifications")
def create_cert_cycle(payload: CertCycleIn, admin: Admin, db: Db):
    cycle = AccessCertificationCycle(
        title=payload.title,
        initiated_by_id=admin.id,
        due_at=_utcnow() + timedelta(days=payload.due_days),
    )
    db.add(cycle)
    # Auto-populate items from active admin users
    admins = list(db.scalars(
        select(User).where(User.is_platform_admin.is_(True), User.active.is_(True))
    ))
    for u in admins:
        db.add(AccessCertificationItem(
            cycle_id=cycle.id, user_id=u.id,
            permission="platform_admin",
        ))
    db.add(AuditLog(actor_user_id=admin.id, action="platform.access_certification_started",
                    entity_type="access_certification_cycle", entity_id=cycle.id))
    db.commit()
    return {"id": cycle.id, "item_count": len(admins)}


@router.get("/access-certifications")
def list_cert_cycles(admin: Admin, db: Db):
    cycles = list(db.scalars(
        select(AccessCertificationCycle).order_by(AccessCertificationCycle.created_at.desc()).limit(20)
    ))
    return {"cycles": [
        {"id": c.id, "title": c.title, "status": c.status,
         "due_at": c.due_at.isoformat(), "completed_at": c.completed_at.isoformat() if c.completed_at else None,
         "created_at": c.created_at.isoformat()}
        for c in cycles
    ]}


class CertDecisionIn(BaseModel):
    decision: Literal["certify", "revoke"]
    reason: str | None = None


@router.post("/access-certifications/{cycle_id}/items/{item_id}/decide")
def decide_cert_item(
    cycle_id: str, item_id: str, payload: CertDecisionIn, admin: Admin, db: Db
):
    item = db.get(AccessCertificationItem, item_id)
    if item is None or item.cycle_id != cycle_id:
        raise HTTPException(status_code=404, detail="Item not found")
    item.decision = payload.decision
    item.decision_reason = payload.reason
    item.reviewer_id = admin.id
    item.decided_at = _utcnow()
    db.commit()
    return {"id": item_id, "decision": payload.decision}


# ── 25. Emergency Containment ─────────────────────────────────────────────────

class EmergencyContainIn(BaseModel):
    organization_id: str | None = None
    reason: str = Field(min_length=5, max_length=300)
    actions: list[Literal["freeze_logins", "revoke_sessions", "disable_api_keys", "halt_messaging"]]


@router.post("/emergency-containment")
def emergency_containment(payload: EmergencyContainIn, admin: Admin, db: Db):
    actions_taken = []

    if "freeze_logins" in payload.actions and payload.organization_id:
        org = db.get(Organization, payload.organization_id)
        if org:
            org.suspended_at = _utcnow()
            org.suspended_reason = f"Emergency containment: {payload.reason}"
            actions_taken.append("freeze_logins")

    if "revoke_sessions" in payload.actions:
        now = _utcnow()
        q = select(UserSession).where(UserSession.revoked_at.is_(None))
        if payload.organization_id:
            member_ids = list(db.scalars(
                select(Membership.user_id).where(
                    Membership.organization_id == payload.organization_id,
                    Membership.active.is_(True),
                )
            ))
            q = q.where(UserSession.user_id.in_(member_ids or [""]))
        for session in db.scalars(q):
            session.revoked_at = now
            session.revoked_reason = "emergency_containment"
        actions_taken.append("revoke_sessions")

    event = EmergencyContainmentEvent(
        actor_id=admin.id,
        organization_id=payload.organization_id,
        actions_taken_json=json.dumps(actions_taken),
        reason=payload.reason,
    )
    db.add(event)
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.emergency_containment",
        entity_type="emergency", entity_id=event.id,
        metadata_json=json.dumps({"actions": actions_taken, "reason": payload.reason}),
    ))
    db.commit()
    return {"id": event.id, "actions_taken": actions_taken}


# ── 26-29. Incident Command Center ───────────────────────────────────────────

@router.get("/incidents")
def list_incidents(admin: Admin, db: Db, status: str = "open"):
    incidents = list(db.scalars(
        select(IncidentRecord).where(IncidentRecord.status == status)
        .order_by(IncidentRecord.created_at.desc()).limit(50)
    ))
    return {"count": len(incidents), "incidents": [
        {"id": i.id, "title": i.title, "severity": i.severity, "status": i.status,
         "affected_org_count": i.affected_org_count,
         "created_at": i.created_at.isoformat(),
         "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None}
        for i in incidents
    ]}


class IncidentIn(BaseModel):
    title: str = Field(min_length=5, max_length=300)
    severity: Literal["p1", "p2", "p3", "p4"] = "p2"
    affected_features: list[str] = Field(default_factory=list)
    affected_org_count: int = 0


@router.post("/incidents")
def create_incident(payload: IncidentIn, admin: Admin, db: Db):
    incident = IncidentRecord(
        title=payload.title, severity=payload.severity,
        commander_id=admin.id,
        affected_features_json=json.dumps(payload.affected_features),
        affected_org_count=payload.affected_org_count,
    )
    db.add(incident)
    db.flush()  # assigns incident.id before child records
    db.add(IncidentEvent(
        incident_id=incident.id, event_type="opened",
        actor_id=admin.id, body=f"Incident opened by {admin.display_name}",
    ))
    db.add(AuditLog(actor_user_id=admin.id, action="platform.incident_opened",
                    entity_type="incident", entity_id=incident.id,
                    metadata_json=json.dumps({"title": payload.title, "severity": payload.severity})))
    db.commit()
    return {"id": incident.id, "status": "open"}


class IncidentUpdateIn(BaseModel):
    status: Literal["open", "mitigated", "resolved"] | None = None
    mitigation: str | None = None
    root_cause: str | None = None
    customer_communication: str | None = None
    comment: str | None = None


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: str, payload: IncidentUpdateIn, admin: Admin, db: Db):
    incident = db.get(IncidentRecord, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if payload.status:
        incident.status = payload.status
        if payload.status == "resolved" and not incident.resolved_at:
            incident.resolved_at = _utcnow()
    if payload.mitigation:
        incident.mitigation = payload.mitigation
    if payload.root_cause:
        incident.root_cause = payload.root_cause
    if payload.customer_communication:
        incident.customer_communication = payload.customer_communication
    db.add(IncidentEvent(
        incident_id=incident_id, event_type="updated", actor_id=admin.id,
        body=payload.comment or f"Updated by {admin.display_name}",
    ))
    db.commit()
    return {"id": incident_id, "status": incident.status}


@router.get("/incidents/{incident_id}/timeline")
def get_incident_timeline(incident_id: str, admin: Admin, db: Db):
    incident = db.get(IncidentRecord, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    events = list(db.scalars(
        select(IncidentEvent).where(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.created_at)
    ))
    return {
        "id": incident_id, "title": incident.title, "severity": incident.severity,
        "status": incident.status, "mitigation": incident.mitigation,
        "root_cause": incident.root_cause,
        "timeline": [{"event_type": e.event_type, "body": e.body,
                       "created_at": e.created_at.isoformat()} for e in events],
    }


# ── 28. Background Job Console ────────────────────────────────────────────────

@router.get("/jobs")
def list_jobs(admin: Admin, db: Db, status: str = "failed", limit: int = 50):
    jobs = list(db.scalars(
        select(JobRecord).where(JobRecord.status == status)
        .order_by(JobRecord.created_at.desc()).limit(min(limit, 200))
    ))
    return {"count": len(jobs), "jobs": [
        {"id": j.id, "job_type": j.job_type, "status": j.status,
         "attempt_count": j.attempt_count, "max_attempts": j.max_attempts,
         "error": j.error, "created_at": j.created_at.isoformat(),
         "started_at": j.started_at.isoformat() if j.started_at else None,
         "completed_at": j.completed_at.isoformat() if j.completed_at else None}
        for j in jobs
    ]}


class JobIn(BaseModel):
    job_type: str = Field(max_length=60)
    organization_id: str | None = None
    payload_json: str | None = None
    max_attempts: int = Field(default=3, ge=1, le=10)
    idempotency_key: str | None = None


@router.post("/jobs")
def enqueue_job(payload: JobIn, admin: Admin, db: Db):
    job = JobRecord(**payload.model_dump())
    db.add(job)
    db.commit()
    return {"id": job.id, "status": "pending"}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, admin: Admin, db: Db):
    job = db.get(JobRecord, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("failed", "dead"):
        raise HTTPException(status_code=409, detail="Only failed or dead jobs can be retried")
    if job.attempt_count >= job.max_attempts:
        raise HTTPException(status_code=409, detail="Max retry attempts reached")
    job.status = "pending"
    job.error = None
    db.add(AuditLog(actor_user_id=admin.id, action="platform.job_retried",
                    entity_type="job", entity_id=job_id))
    db.commit()
    return {"id": job_id, "status": "pending"}


# ── 31-35. Feature Rollout & Config Versioning ────────────────────────────────

@router.get("/rollout-configs")
def list_rollout_configs(admin: Admin, db: Db):
    configs = list(db.scalars(select(FeatureRolloutConfig)))
    return {"configs": [
        {"id": c.id, "feature_key": c.feature_key, "current_stage": c.current_stage,
         "stages": json.loads(c.stages_json or "[]"),
         "auto_rollback_enabled": c.auto_rollback_enabled,
         "rollback_count": c.rollback_count,
         "last_rollback_at": c.last_rollback_at.isoformat() if c.last_rollback_at else None}
        for c in configs
    ]}


class RolloutConfigIn(BaseModel):
    feature_key: str = Field(max_length=60)
    stages: list[str] = Field(default=["internal", "pilot", "5pct", "20pct", "50pct", "all"])
    guardrail_error_threshold: Decimal | None = None
    guardrail_ticket_threshold: int | None = None
    auto_rollback_enabled: bool = True


@router.post("/rollout-configs")
def create_rollout_config(payload: RolloutConfigIn, admin: Admin, db: Db):
    config = FeatureRolloutConfig(
        feature_key=payload.feature_key,
        stages_json=json.dumps(payload.stages),
        guardrail_error_threshold=payload.guardrail_error_threshold,
        guardrail_ticket_threshold=payload.guardrail_ticket_threshold,
        auto_rollback_enabled=payload.auto_rollback_enabled,
        created_by_id=admin.id,
    )
    db.add(config)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.rollout_config_created",
                    entity_type="feature", entity_id=payload.feature_key))
    db.commit()
    return {"id": config.id, "feature_key": config.feature_key}


class AdvanceStageIn(BaseModel):
    reason: str | None = None


@router.post("/rollout-configs/{config_id}/advance")
def advance_rollout_stage(config_id: str, payload: AdvanceStageIn, admin: Admin, db: Db):
    config = db.get(FeatureRolloutConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    stages = json.loads(config.stages_json or "[]")
    current_idx = stages.index(config.current_stage) if config.current_stage in stages else -1
    if current_idx >= len(stages) - 1:
        raise HTTPException(status_code=409, detail="Already at final stage")
    next_stage = stages[current_idx + 1]
    config.current_stage = next_stage
    db.add(AuditLog(actor_user_id=admin.id, action="platform.rollout_advanced",
                    entity_type="feature", entity_id=config.feature_key,
                    metadata_json=json.dumps({"stage": next_stage, "reason": payload.reason})))
    db.commit()
    return {"feature_key": config.feature_key, "current_stage": next_stage}


@router.post("/rollout-configs/{config_id}/rollback")
def rollback_rollout(config_id: str, admin: Admin, db: Db):
    config = db.get(FeatureRolloutConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    stages = json.loads(config.stages_json or "[]")
    current_idx = stages.index(config.current_stage) if config.current_stage in stages else 1
    if current_idx <= 0:
        raise HTTPException(status_code=409, detail="Already at initial stage")
    prev_stage = stages[current_idx - 1]
    config.current_stage = prev_stage
    config.rollback_count += 1
    config.last_rollback_at = _utcnow()
    db.add(AuditLog(actor_user_id=admin.id, action="platform.rollout_rolled_back",
                    entity_type="feature", entity_id=config.feature_key,
                    metadata_json=json.dumps({"rolled_back_to": prev_stage})))
    db.commit()
    return {"feature_key": config.feature_key, "current_stage": prev_stage}


# Config versioning
@router.get("/config-versions")
def list_config_versions(admin: Admin, db: Db, config_key: str | None = None):
    q = select(ConfigVersion).order_by(ConfigVersion.created_at.desc())
    if config_key:
        q = q.where(ConfigVersion.config_key == config_key)
    versions = list(db.scalars(q.limit(50)))
    return {"versions": [
        {"id": v.id, "config_key": v.config_key, "version": v.version,
         "diff_summary": v.diff_summary, "deployed_at": v.deployed_at.isoformat() if v.deployed_at else None,
         "created_at": v.created_at.isoformat()}
        for v in versions
    ]}


class ConfigVersionIn(BaseModel):
    config_key: str = Field(max_length=100)
    value_json: str
    diff_summary: str | None = None


@router.post("/config-versions")
def save_config_version(payload: ConfigVersionIn, admin: Admin, db: Db):
    last = db.scalar(
        select(ConfigVersion)
        .where(ConfigVersion.config_key == payload.config_key)
        .order_by(ConfigVersion.version.desc())
    )
    version_num = (last.version + 1) if last else 1
    cv = ConfigVersion(
        config_key=payload.config_key, version=version_num,
        value_json=payload.value_json,
        previous_value_json=last.value_json if last else None,
        diff_summary=payload.diff_summary,
        created_by_id=admin.id,
    )
    db.add(cv)
    db.commit()
    return {"id": cv.id, "version": version_num}


# ── 36-40. Integration Operations ────────────────────────────────────────────

@router.get("/provider-credentials")
def list_provider_credentials(admin: Admin, db: Db):
    creds = list(db.scalars(select(ProviderCredential).order_by(ProviderCredential.provider)))
    now = _utcnow()
    return {"credentials": [
        {"id": c.id, "provider": c.provider, "credential_name": c.credential_name,
         "status": c.status,
         "expires_at": c.expires_at.isoformat() if c.expires_at else None,
         "expiring_soon": bool(
             c.expires_at and c.expires_at > now and c.expires_at < now + timedelta(days=30)
         ),
         "last_rotated_at": c.last_rotated_at.isoformat() if c.last_rotated_at else None,
         "notes": c.notes}
        for c in creds
    ]}


class ProviderCredentialIn(BaseModel):
    provider: str = Field(max_length=40)
    credential_name: str = Field(max_length=100)
    status: Literal["active", "expiring", "expired", "revoked"] = "active"
    expires_at: datetime | None = None
    notes: str | None = None


@router.post("/provider-credentials")
def add_provider_credential(payload: ProviderCredentialIn, admin: Admin, db: Db):
    cred = ProviderCredential(**payload.model_dump())
    db.add(cred)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.credential_added",
                    entity_type="provider_credential", entity_id=cred.id,
                    metadata_json=json.dumps({"provider": payload.provider})))
    db.commit()
    return {"id": cred.id, "status": "created"}


@router.post("/provider-credentials/{cred_id}/rotate")
def rotate_credential(cred_id: str, admin: Admin, db: Db):
    cred = db.get(ProviderCredential, cred_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    cred.last_rotated_at = _utcnow()
    cred.status = "active"
    cred.rotated_by_id = admin.id
    db.add(AuditLog(actor_user_id=admin.id, action="platform.credential_rotated",
                    entity_type="provider_credential", entity_id=cred_id))
    db.commit()
    return {"id": cred_id, "last_rotated_at": cred.last_rotated_at.isoformat()}


@router.get("/webhook-events")
def list_webhook_events(admin: Admin, db: Db, status: str = "failed", limit: int = 50):
    events = list(db.scalars(
        select(WebhookEvent).where(WebhookEvent.processing_status == status)
        .order_by(WebhookEvent.received_at.desc()).limit(min(limit, 200))
    ))
    return {"count": len(events), "events": [
        {"id": e.id, "provider": e.provider, "event_type": e.event_type,
         "signature_valid": e.signature_valid, "processing_status": e.processing_status,
         "error": e.error, "replay_count": e.replay_count,
         "received_at": e.received_at.isoformat()}
        for e in events
    ]}


@router.post("/webhook-events/{event_id}/replay")
def replay_webhook(event_id: str, admin: Admin, db: Db):
    event = db.get(WebhookEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    event.replay_count += 1
    event.last_replayed_at = _utcnow()
    event.processing_status = "pending"
    db.add(AuditLog(actor_user_id=admin.id, action="platform.webhook_replayed",
                    entity_type="webhook_event", entity_id=event_id))
    db.commit()
    return {"id": event_id, "replay_count": event.replay_count}


@router.get("/organizations/{org_id}/integration-certifications")
def list_org_certifications(org_id: str, admin: Admin, db: Db):
    certs = list(db.scalars(
        select(IntegrationCertification).where(IntegrationCertification.organization_id == org_id)
    ))
    return {"certifications": [
        {"id": c.id, "integration": c.integration,
         "sandbox_tested": c.sandbox_tested, "callback_validated": c.callback_validated,
         "refund_tested": c.refund_tested, "credential_verified": c.credential_verified,
         "certified_at": c.certified_at.isoformat() if c.certified_at else None}
        for c in certs
    ]}


class IntegrationCertIn(BaseModel):
    integration: str = Field(max_length=40)
    sandbox_tested: bool = False
    callback_validated: bool = False
    refund_tested: bool = False
    credential_verified: bool = False
    notes: str | None = None


@router.post("/organizations/{org_id}/integration-certifications")
def upsert_integration_certification(
    org_id: str, payload: IntegrationCertIn, admin: Admin, db: Db
):
    cert = db.scalar(
        select(IntegrationCertification).where(
            IntegrationCertification.organization_id == org_id,
            IntegrationCertification.integration == payload.integration,
        )
    )
    if cert is None:
        cert = IntegrationCertification(organization_id=org_id, **payload.model_dump())
        db.add(cert)
    else:
        for k, v in payload.model_dump().items():
            setattr(cert, k, v)
    all_done = all([payload.sandbox_tested, payload.callback_validated,
                    payload.refund_tested, payload.credential_verified])
    if all_done and not cert.certified_at:
        cert.certified_at = _utcnow()
        cert.certified_by_id = admin.id
    db.add(AuditLog(actor_user_id=admin.id, action="platform.integration_cert_updated",
                    entity_type="organization", entity_id=org_id,
                    metadata_json=json.dumps({"integration": payload.integration})))
    db.commit()
    return {"id": cert.id, "certified": bool(cert.certified_at)}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════

# ── 41. Data Inventory ────────────────────────────────────────────────────────

@router.get("/data-inventory")
def list_data_inventory(admin: Admin, db: Db):
    items = list(db.scalars(select(DataInventoryItem).order_by(DataInventoryItem.module)))
    return {"count": len(items), "items": [
        {"id": i.id, "module": i.module, "data_category": i.data_category,
         "description": i.description, "table_name": i.table_name,
         "legal_basis": i.legal_basis, "retention_days": i.retention_days}
        for i in items
    ]}


class DataInventoryIn(BaseModel):
    module: str = Field(max_length=60)
    data_category: str = Field(max_length=40)
    description: str = Field(max_length=300)
    table_name: str | None = None
    legal_basis: str | None = None
    retention_days: int | None = None


@router.post("/data-inventory")
def add_data_inventory(payload: DataInventoryIn, admin: Admin, db: Db):
    item = DataInventoryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    return {"id": item.id, "status": "created"}


# ── 42. Tenant Data Export ────────────────────────────────────────────────────

@router.get("/data-exports")
def list_data_exports(admin: Admin, db: Db, status: str | None = None):
    q = select(TenantDataExportRequest).order_by(TenantDataExportRequest.created_at.desc())
    if status:
        q = q.where(TenantDataExportRequest.status == status)
    exports = list(db.scalars(q.limit(50)))
    org_ids = {e.organization_id for e in exports}
    orgs = {o.id: o.name for o in db.scalars(
        select(Organization).where(Organization.id.in_(org_ids or {""}))
    )}
    return {"exports": [
        {"id": e.id, "org_name": orgs.get(e.organization_id), "status": e.status,
         "created_at": e.created_at.isoformat(),
         "completed_at": e.completed_at.isoformat() if e.completed_at else None,
         "expires_at": e.expires_at.isoformat() if e.expires_at else None}
        for e in exports
    ]}


class DataExportIn(BaseModel):
    organization_id: str
    scope: list[str] = Field(default=["sales", "customers", "products"])


@router.post("/data-exports")
def create_data_export(payload: DataExportIn, admin: Admin, db: Db):
    org = db.get(Organization, payload.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    req = TenantDataExportRequest(
        organization_id=payload.organization_id,
        requested_by_id=admin.id,
        scope_json=json.dumps(payload.scope),
        expires_at=_utcnow() + timedelta(days=7),
    )
    db.add(req)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.data_export_requested",
                    entity_type="organization", entity_id=payload.organization_id))
    db.commit()
    return {"id": req.id, "status": "pending"}


@router.post("/data-exports/{export_id}/complete")
def complete_data_export(export_id: str, admin: Admin, db: Db):
    req = db.get(TenantDataExportRequest, export_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Export not found")
    req.status = "ready"
    req.completed_at = _utcnow()
    req.file_manifest_json = json.dumps({"files": ["sales.csv", "customers.csv"], "note": "Manually assembled"})
    db.commit()
    return {"id": export_id, "status": "ready"}


# ── 43. Retention Policies ────────────────────────────────────────────────────

@router.get("/retention-policies")
def list_retention_policies(admin: Admin, db: Db):
    policies = list(db.scalars(select(RetentionPolicy).order_by(RetentionPolicy.data_category)))
    return {"policies": [
        {"id": p.id, "data_category": p.data_category, "retention_days": p.retention_days,
         "action_on_expiry": p.action_on_expiry, "requires_approval": p.requires_approval,
         "legal_hold_override": p.legal_hold_override, "notes": p.notes}
        for p in policies
    ]}


class RetentionPolicyIn(BaseModel):
    data_category: str = Field(max_length=60)
    retention_days: int = Field(ge=1)
    action_on_expiry: Literal["archive", "purge", "review"] = "archive"
    requires_approval: bool = True
    notes: str | None = None


@router.post("/retention-policies")
def upsert_retention_policy(payload: RetentionPolicyIn, admin: Admin, db: Db):
    existing = db.scalar(
        select(RetentionPolicy).where(RetentionPolicy.data_category == payload.data_category)
    )
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
        policy = existing
    else:
        policy = RetentionPolicy(**payload.model_dump(), created_by_id=admin.id)
        db.add(policy)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.retention_policy_updated",
                    entity_type="retention_policy", entity_id=payload.data_category))
    db.commit()
    return {"id": policy.id, "data_category": policy.data_category}


# ── 44. Privacy Requests ──────────────────────────────────────────────────────

@router.get("/privacy-requests")
def list_privacy_requests(admin: Admin, db: Db, status: str = "pending"):
    reqs = list(db.scalars(
        select(PrivacyRequest).where(PrivacyRequest.status == status)
        .order_by(PrivacyRequest.created_at.desc()).limit(50)
    ))
    return {"count": len(reqs), "requests": [
        {"id": r.id, "request_type": r.request_type, "subject_email": r.subject_email,
         "status": r.status, "verification_completed": r.verification_completed,
         "due_at": r.due_at.isoformat() if r.due_at else None,
         "created_at": r.created_at.isoformat()}
        for r in reqs
    ]}


class PrivacyRequestIn(BaseModel):
    request_type: Literal["access", "correction", "portability", "deletion"]
    subject_email: str = Field(max_length=254)
    description: str | None = None
    organization_id: str | None = None


@router.post("/privacy-requests")
def create_privacy_request(payload: PrivacyRequestIn, admin: Admin, db: Db):
    req = PrivacyRequest(
        **payload.model_dump(),
        assigned_to_id=admin.id,
        due_at=_utcnow() + timedelta(days=30),
    )
    db.add(req)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.privacy_request_created",
                    entity_type="privacy_request", entity_id=req.id))
    db.commit()
    return {"id": req.id, "status": "pending"}


class PrivacyRequestUpdateIn(BaseModel):
    status: Literal["pending", "in_progress", "completed", "rejected"]
    verification_completed: bool = False
    evidence_url: str | None = None


@router.patch("/privacy-requests/{req_id}")
def update_privacy_request(req_id: str, payload: PrivacyRequestUpdateIn, admin: Admin, db: Db):
    req = db.get(PrivacyRequest, req_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = payload.status
    req.verification_completed = payload.verification_completed
    req.evidence_url = payload.evidence_url
    if payload.status == "completed":
        req.completed_at = _utcnow()
    db.add(AuditLog(actor_user_id=admin.id, action="platform.privacy_request_updated",
                    entity_type="privacy_request", entity_id=req_id,
                    metadata_json=json.dumps({"status": payload.status})))
    db.commit()
    return {"id": req_id, "status": payload.status}


# ── 46. AI Model Registry ─────────────────────────────────────────────────────

@router.get("/model-registry")
def list_model_registry(admin: Admin, db: Db, active_only: bool = True):
    q = select(ModelRegistryEntry)
    if active_only:
        q = q.where(ModelRegistryEntry.is_active.is_(True))
    entries = list(db.scalars(q.order_by(ModelRegistryEntry.feature)))
    return {"entries": [
        {"id": e.id, "feature": e.feature, "model_id": e.model_id,
         "prompt_version": e.prompt_version, "fallback_behavior": e.fallback_behavior,
         "is_active": e.is_active,
         "deployed_at": e.deployed_at.isoformat() if e.deployed_at else None,
         "deprecated_at": e.deprecated_at.isoformat() if e.deprecated_at else None}
        for e in entries
    ]}


class ModelRegistryIn(BaseModel):
    feature: str = Field(max_length=80)
    model_id: str = Field(max_length=100)
    prompt_version: str | None = None
    knowledge_source: str | None = None
    fallback_behavior: str | None = None
    notes: str | None = None


@router.post("/model-registry")
def register_model(payload: ModelRegistryIn, admin: Admin, db: Db):
    # Deactivate previous entry for same feature
    for old in db.scalars(
        select(ModelRegistryEntry).where(
            ModelRegistryEntry.feature == payload.feature, ModelRegistryEntry.is_active.is_(True)
        )
    ):
        old.is_active = False
        old.deprecated_at = _utcnow()
    entry = ModelRegistryEntry(
        **payload.model_dump(), deployed_at=_utcnow(), deployed_by_id=admin.id
    )
    db.add(entry)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.model_registered",
                    entity_type="model_registry", entity_id=entry.id,
                    metadata_json=json.dumps({"feature": payload.feature, "model": payload.model_id})))
    db.commit()
    return {"id": entry.id, "feature": entry.feature}


# ── 47. AI Cost Budgets ───────────────────────────────────────────────────────

@router.get("/ai-cost-budgets")
def list_ai_budgets(admin: Admin, db: Db):
    budgets = list(db.scalars(select(AiCostBudget).order_by(AiCostBudget.feature)))
    return {"budgets": [
        {"id": b.id, "org_id": b.organization_id, "feature": b.feature,
         "monthly_token_limit": b.monthly_token_limit,
         "monthly_cost_limit_bdt": _money(b.monthly_cost_limit_bdt) if b.monthly_cost_limit_bdt else None,
         "on_breach": b.on_breach}
        for b in budgets
    ]}


class AiBudgetIn(BaseModel):
    organization_id: str | None = None
    feature: str = Field(max_length=80)
    monthly_token_limit: int | None = None
    monthly_cost_limit_bdt: Decimal | None = None
    on_breach: Literal["downgrade", "manual_mode", "require_approval", "block"] = "downgrade"


@router.post("/ai-cost-budgets")
def set_ai_budget(payload: AiBudgetIn, admin: Admin, db: Db):
    existing = db.scalar(
        select(AiCostBudget).where(
            AiCostBudget.organization_id == payload.organization_id,
            AiCostBudget.feature == payload.feature,
        )
    )
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
        budget = existing
    else:
        budget = AiCostBudget(**payload.model_dump(), created_by_id=admin.id)
        db.add(budget)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.ai_budget_set",
                    entity_type="ai_cost_budget", entity_id=budget.id))
    db.commit()
    return {"id": budget.id, "status": "saved"}


# ── 49. Model Outcome Monitoring ──────────────────────────────────────────────

@router.get("/model-outcomes")
def list_model_outcomes(admin: Admin, db: Db, feature: str | None = None, vertical: str | None = None):
    q = select(ModelOutcomeRecord)
    if feature:
        q = q.where(ModelOutcomeRecord.feature == feature)
    if vertical:
        q = q.where(ModelOutcomeRecord.vertical == vertical)
    records = list(db.scalars(q.order_by(ModelOutcomeRecord.recorded_at.desc()).limit(100)))
    # Aggregate stats
    total = len(records)
    accepted = sum(1 for r in records if r.accepted)
    financial_impact = sum(float(r.financial_impact_bdt or 0) for r in records)
    return {
        "total": total,
        "accepted": accepted,
        "acceptance_rate": round(accepted / total * 100, 1) if total else 0,
        "total_financial_impact_bdt": round(financial_impact, 2),
        "records": [
            {"id": r.id, "feature": r.feature, "vertical": r.vertical,
             "outcome": r.outcome, "accepted": r.accepted,
             "financial_impact_bdt": _money(r.financial_impact_bdt) if r.financial_impact_bdt else None,
             "recorded_at": r.recorded_at.isoformat()}
            for r in records
        ],
    }


class ModelOutcomeIn(BaseModel):
    feature: str = Field(max_length=80)
    vertical: str = Field(max_length=40)
    organization_id: str | None = None
    recommendation_id: str | None = None
    outcome: Literal["correct", "incorrect", "partial", "unknown"]
    accepted: bool | None = None
    financial_impact_bdt: Decimal | None = None
    notes: str | None = None


@router.post("/model-outcomes")
def record_model_outcome(payload: ModelOutcomeIn, admin: Admin, db: Db):
    record = ModelOutcomeRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    return {"id": record.id, "status": "recorded"}


# ── 50. AI Kill Switch ────────────────────────────────────────────────────────

@router.get("/ai-kill-switches")
def list_kill_switches(admin: Admin, db: Db):
    switches = list(db.scalars(select(AiKillSwitch).order_by(AiKillSwitch.feature)))
    return {"switches": [
        {"id": s.id, "feature": s.feature, "disabled": s.disabled,
         "reason": s.reason,
         "requires_human_approval_above_risk": _money(s.requires_human_approval_above_risk)
         if s.requires_human_approval_above_risk else None,
         "disabled_at": s.disabled_at.isoformat() if s.disabled_at else None}
        for s in switches
    ]}


class KillSwitchIn(BaseModel):
    feature: str = Field(max_length=80)
    disabled: bool
    reason: str | None = None
    requires_human_approval_above_risk: Decimal | None = None


@router.post("/ai-kill-switches")
def set_kill_switch(payload: KillSwitchIn, admin: Admin, db: Db):
    existing = db.scalar(
        select(AiKillSwitch).where(AiKillSwitch.feature == payload.feature)
    )
    if existing:
        existing.disabled = payload.disabled
        existing.reason = payload.reason
        existing.requires_human_approval_above_risk = payload.requires_human_approval_above_risk
        if payload.disabled:
            existing.disabled_at = _utcnow()
            existing.disabled_by_id = admin.id
        switch = existing
    else:
        switch = AiKillSwitch(
            **payload.model_dump(),
            disabled_by_id=admin.id if payload.disabled else None,
            disabled_at=_utcnow() if payload.disabled else None,
        )
        db.add(switch)
    db.add(AuditLog(
        actor_user_id=admin.id,
        action="platform.ai_kill_switch_activated" if payload.disabled else "platform.ai_kill_switch_deactivated",
        entity_type="ai_kill_switch", entity_id=switch.id,
        metadata_json=json.dumps({"feature": payload.feature}),
    ))
    db.commit()
    return {"id": switch.id, "feature": switch.feature, "disabled": switch.disabled}


# ── Admin overview summary ────────────────────────────────────────────────────

@router.get("/overview")
def admin_overview(admin: Admin, db: Db):
    """Single-call summary for the admin command center dashboard."""
    now = _utcnow()
    return {
        "generated_at": now.isoformat(),
        "mission_queue": {
            "open": db.scalar(select(func.count(AdminMissionItem.id)).where(AdminMissionItem.status == "open")) or 0,
        },
        "support": {
            "open_cases": db.scalar(select(func.count(SupportCase.id)).where(SupportCase.status.in_(("open", "pending")))) or 0,
        },
        "incidents": {
            "open": db.scalar(select(func.count(IncidentRecord.id)).where(IncidentRecord.status == "open")) or 0,
        },
        "security": {
            "open_alerts": db.scalar(select(func.count(SecurityAlert.id)).where(SecurityAlert.status == "open")) or 0,
        },
        "churn_risk": {
            "high": db.scalar(select(func.count(ChurnRiskScore.id)).where(ChurnRiskScore.risk_level == "high")) or 0,
        },
        "jit_access": {
            "active": db.scalar(
                select(func.count(JitAccessGrant.id)).where(
                    JitAccessGrant.revoked_at.is_(None), JitAccessGrant.expires_at > now
                )
            ) or 0,
        },
        "ai_kill_switches": {
            "disabled_count": db.scalar(select(func.count(AiKillSwitch.id)).where(AiKillSwitch.disabled.is_(True))) or 0,
        },
        "jobs": {
            "failed": db.scalar(select(func.count(JobRecord.id)).where(JobRecord.status == "failed")) or 0,
        },
        "privacy_requests": {
            "pending": db.scalar(select(func.count(PrivacyRequest.id)).where(PrivacyRequest.status == "pending")) or 0,
        },
    }
