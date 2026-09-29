"""B-SMART Algorithm 1: serve R_t, record the owner's decision, log the outcome.

This closes layers 5, 9 and 10 of `docs/BSMART_ARCHITECTURE.md`. Before this
module the engine produced a ranked recommendation and nothing captured what
the pharmacist did with it, so the feedback loop the architecture describes was
open and no business-outcome claim could be evidenced.

Two sources of recommendations are deliberately kept apart:

* ``/api/research/bsmart/latest`` reads the thesis run's artifact
  (``output/bsmart_recommendations.json``) read-only. It is evidence from the
  research dataset and is never written to, so a dashboard visit cannot drift
  a reported thesis number.
* ``/api/app/bsmart/*`` operates on a tenant's own persisted recommendations
  and records real owner decisions and outcomes against them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .database import get_db
from .domain_models import (
    Recommendation, RecommendationDecision, RecommendationOutcome, new_id,
)
from .audit import record_audit
from .permissions import require_permission

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]

ARTIFACT = Path("output/bsmart_recommendations.json")
RUN_SUMMARY = Path("output/bsmart_run_summary.json")


# ─────────────────────────────────────────────────────────────────────────────
# Layer 5 — the research run's R_t, read-only
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/api/research/bsmart/latest", tags=["research"])
def bsmart_latest():
    """The most recent B-SMART Algorithm 1 run from the thesis dataset.

    Returns R_t, the declared assumptions and the funnel counts exactly as the
    engine wrote them. Nothing is recomputed here: the numbers a reader sees
    are the numbers in the artifact, which is what makes them citable.
    """
    if not ARTIFACT.is_file():
        raise HTTPException(
            status_code=404,
            detail="No B-SMART run found. Run: python 13_bsmart_recommendation_engine.py",
        )
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    summary = (
        json.loads(RUN_SUMMARY.read_text(encoding="utf-8"))
        if RUN_SUMMARY.is_file() else {}
    )
    return {
        "cutoff": payload.get("cutoff"),
        "assumptions": payload.get("assumptions", {}),
        "recommendations": payload.get("R_t", []),
        "summary": summary,
        "evidence_tier": "Tier 3 — real medicine catalogue, synthetic transactions",
        "source": str(ARTIFACT),
    }


@router.post("/api/app/bsmart/import-run", tags=["bsmart"])
def import_run(membership: CurrentMembership, db: Db):
    """Persist the latest engine run into this organization's own records.

    Layer 5 writes a JSON artifact; layers 9-10 need rows the owner can act on.
    This is the bridge. It is explicit rather than automatic so that importing
    a research-dataset run into a tenant's workspace is always a deliberate
    act — the evidence tier of the source is carried through on every row.

    Re-importing the same cutoff is a no-op rather than a duplicate, so the
    button is safe to press twice.
    """
    require_permission(membership, "bsmart:import")
    if not ARTIFACT.is_file():
        raise HTTPException(
            status_code=404,
            detail="No B-SMART run found. Run: python 13_bsmart_recommendation_engine.py",
        )
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cutoff = payload.get("cutoff")
    actions = payload.get("R_t", [])

    existing = db.scalars(
        select(Recommendation).where(
            Recommendation.organization_id == membership.organization_id,
            Recommendation.cutoff_date == cutoff,
        )
    ).all()
    if existing:
        return {
            "status": "already_imported",
            "cutoff": cutoff,
            "recommendations": len(existing),
        }

    run_id = new_id()
    for rank, a in enumerate(actions, start=1):
        db.add(Recommendation(
            id=new_id(),
            organization_id=membership.organization_id,
            run_id=run_id,
            cutoff_date=cutoff,
            rank_in_rt=rank,
            action_type=a["type"],
            target_sku=a.get("sku"),
            target_customer_id=a.get("customer_id"),
            division=a.get("division"),
            quantity=a.get("reorder_qty") or a.get("units_at_risk"),
            benefit_bdt=a.get("benefit_bdt", 0),
            action_cost_bdt=a.get("action_cost_bdt", 0),
            risk_bdt=a.get("risk_bdt", 0),
            utility_bdt=a.get("utility_bdt", 0),
            confidence=a.get("confidence", "baseline"),
            feasible=True,
            reason=a.get("reason"),
            explanation_json=json.dumps(a.get("explanation")) if a.get("explanation") else None,
            model_version=f"13_bsmart_recommendation_engine@{cutoff}",
        ))
    record_audit(db, membership, "bsmart.imported", "recommendation_run", run_id,
                 cutoff=cutoff, recommendations=len(actions))
    db.commit()
    return {"status": "imported", "cutoff": cutoff, "run_id": run_id,
            "recommendations": len(actions)}


# ─────────────────────────────────────────────────────────────────────────────
# Layer 9 — owner decision
# ─────────────────────────────────────────────────────────────────────────────
class DecisionIn(BaseModel):
    decision: Literal["accept", "reject", "modify", "defer"]
    modified_quantity: int | None = Field(
        default=None, ge=0,
        description="Required for 'modify': the quantity the owner actually chose.")
    defer_until: str | None = Field(default=None, description="YYYY-MM-DD, for 'defer'.")
    note: str | None = None


@router.get("/api/app/bsmart/recommendations", tags=["bsmart"])
def list_recommendations(membership: CurrentMembership, db: Db, cutoff: str | None = None):
    """This organization's persisted recommendations, newest run first."""
    require_permission(membership, "bsmart:read")
    stmt = select(Recommendation).where(
        Recommendation.organization_id == membership.organization_id)
    if cutoff:
        stmt = stmt.where(Recommendation.cutoff_date == cutoff)
    rows = db.scalars(stmt.order_by(
        Recommendation.cutoff_date.desc(), Recommendation.rank_in_rt)).all()

    out = []
    for r in rows:
        latest_decision = sorted(r.decisions, key=lambda d: d.created_at)[-1] if r.decisions else None
        out.append({
            "id": r.id,
            "run_id": r.run_id,
            "cutoff": r.cutoff_date,
            "rank": r.rank_in_rt,
            "action_type": r.action_type,
            "sku": r.target_sku,
            "customer_id": r.target_customer_id,
            "division": r.division,
            "quantity": r.quantity,
            "benefit_bdt": float(r.benefit_bdt),
            "action_cost_bdt": float(r.action_cost_bdt),
            "risk_bdt": float(r.risk_bdt),
            "utility_bdt": float(r.utility_bdt),
            "confidence": r.confidence,
            "reason": r.reason,
            "explanation": json.loads(r.explanation_json) if r.explanation_json else None,
            "decision": latest_decision.decision if latest_decision else None,
            "decided_at": latest_decision.created_at.isoformat() if latest_decision else None,
            "outcome_logged": bool(r.outcomes),
        })
    return {"count": len(out), "recommendations": out}


@router.post("/api/app/bsmart/recommendations/{recommendation_id}/decision", tags=["bsmart"])
def record_decision(
    recommendation_id: str, body: DecisionIn, membership: CurrentMembership, db: Db,
):
    """Record accept / reject / modify / defer. The owner has final authority.

    Decisions are append-only: changing your mind adds a new row rather than
    editing the old one, so the decision history stays auditable.
    """
    require_permission(membership, "bsmart:decide")
    reco = db.get(Recommendation, recommendation_id)
    if reco is None or reco.organization_id != membership.organization_id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if body.decision == "modify" and body.modified_quantity is None:
        raise HTTPException(
            status_code=422,
            detail="modified_quantity is required when decision is 'modify'")

    row = RecommendationDecision(
        id=new_id(),
        organization_id=membership.organization_id,
        recommendation_id=reco.id,
        decided_by=membership.user_id,
        decision=body.decision,
        modified_quantity=body.modified_quantity,
        defer_until=body.defer_until,
        note=body.note,
    )
    db.add(row)
    record_audit(db, membership, "bsmart.decided", "recommendation", reco.id,
                 decision=body.decision, modified_quantity=body.modified_quantity,
                 action_type=reco.action_type)
    db.commit()
    return {"status": "recorded", "decision_id": row.id, "decision": row.decision}


# ─────────────────────────────────────────────────────────────────────────────
# Layer 10 — outcome and monitoring
# ─────────────────────────────────────────────────────────────────────────────
class OutcomeIn(BaseModel):
    action_taken: bool | None = None
    observation_window_days: int = Field(default=30, ge=1, le=365)
    stockout_days_before: int | None = Field(default=None, ge=0)
    stockout_days_after: int | None = Field(default=None, ge=0)
    holding_cost_before_bdt: float | None = Field(default=None, ge=0)
    holding_cost_after_bdt: float | None = Field(default=None, ge=0)
    expired_value_bdt: float | None = Field(default=None, ge=0)
    customer_responded: bool | None = None
    predicted_quantity: int | None = Field(default=None, ge=0)
    realised_quantity: int | None = Field(default=None, ge=0)
    realised_benefit_bdt: float | None = None
    note: str | None = None


@router.post("/api/app/bsmart/recommendations/{recommendation_id}/outcome", tags=["bsmart"])
def record_outcome(
    recommendation_id: str, body: OutcomeIn, membership: CurrentMembership, db: Db,
):
    """Log what actually happened after the action (or after declining it)."""
    require_permission(membership, "bsmart:outcome")
    reco = db.get(Recommendation, recommendation_id)
    if reco is None or reco.organization_id != membership.organization_id:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    row = RecommendationOutcome(
        id=new_id(),
        organization_id=membership.organization_id,
        recommendation_id=reco.id,
        observed_at=datetime.now(timezone.utc),
        **body.model_dump(exclude_none=False),
    )
    db.add(row)
    record_audit(db, membership, "bsmart.outcome_recorded", "recommendation", reco.id)
    db.commit()
    return {"status": "recorded", "outcome_id": row.id}


@router.get("/api/app/bsmart/monitoring", tags=["bsmart"])
def monitoring(membership: CurrentMembership, db: Db):
    """Layer-10 summary: acceptance, realised effect and forecast error.

    Every figure is reported with the sample size it rests on, and a metric
    with no observations returns ``None`` rather than 0 — an unmeasured
    outcome must never read as a measured zero.
    """
    require_permission(membership, "monitoring:read")
    org = membership.organization_id
    recos = db.scalars(select(Recommendation).where(
        Recommendation.organization_id == org)).all()
    decisions = db.scalars(select(RecommendationDecision).where(
        RecommendationDecision.organization_id == org)).all()
    outcomes = db.scalars(select(RecommendationOutcome).where(
        RecommendationOutcome.organization_id == org)).all()

    by_decision: dict[str, int] = {}
    for d in decisions:
        by_decision[d.decision] = by_decision.get(d.decision, 0) + 1
    decided = sum(by_decision.values())

    def _mean(values):
        vals = [v for v in values if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    stockout_delta = _mean([
        (o.stockout_days_after - o.stockout_days_before)
        for o in outcomes
        if o.stockout_days_after is not None and o.stockout_days_before is not None
    ])
    holding_delta = _mean([
        float(o.holding_cost_after_bdt) - float(o.holding_cost_before_bdt)
        for o in outcomes
        if o.holding_cost_after_bdt is not None and o.holding_cost_before_bdt is not None
    ])
    forecast_abs_error = _mean([
        abs(o.realised_quantity - o.predicted_quantity)
        for o in outcomes
        if o.realised_quantity is not None and o.predicted_quantity is not None
    ])
    responded = [o.customer_responded for o in outcomes if o.customer_responded is not None]

    return {
        "recommendations_total": len(recos),
        "decisions_recorded": decided,
        "acceptance_rate": round(by_decision.get("accept", 0) / decided, 3) if decided else None,
        "decision_breakdown": by_decision,
        "outcomes_logged": len(outcomes),
        "mean_stockout_days_change": stockout_delta,
        "mean_holding_cost_change_bdt": holding_delta,
        "mean_forecast_abs_error_units": forecast_abs_error,
        "customer_response_rate": (
            round(sum(responded) / len(responded), 3) if responded else None),
        "drift_flags": sum(1 for o in outcomes if o.drift_flag),
        "note": (
            "Values are None where nothing has been observed yet. No business-outcome "
            "claim may be made from an empty or near-empty sample."
        ),
    }
