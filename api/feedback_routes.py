"""Customer feedback / NPS (SRD Panel C08).

A score of 6 or below (NPS "detractor" territory) opens a support ticket
automatically, so a bad experience always reaches a human queue -- nothing
here decides it was resolved, that is the ticket workflow's job.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import FeedbackCreate, FeedbackView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import Customer, Feedback, SalesOrder, SupportTicket
from .permissions import require_permission

router = APIRouter(prefix="/api/app/feedback", tags=["feedback"])
Db = Annotated[Session, Depends(get_db)]

DETRACTOR_THRESHOLD = 6


@router.post("", response_model=FeedbackView)
def submit_feedback(payload: FeedbackCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "feedback:write")
    if payload.customer_id is not None:
        customer = db.scalar(select(Customer).where(
            Customer.id == payload.customer_id, Customer.organization_id == membership.organization_id))
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
    if payload.sales_order_id is not None:
        order = db.scalar(select(SalesOrder).where(
            SalesOrder.id == payload.sales_order_id, SalesOrder.organization_id == membership.organization_id))
        if order is None:
            raise HTTPException(status_code=404, detail="Sales order not found")

    entry = Feedback(organization_id=membership.organization_id, **payload.model_dump())
    db.add(entry)
    db.flush()

    if entry.score <= DETRACTOR_THRESHOLD:
        ticket = SupportTicket(
            organization_id=membership.organization_id, created_by_user_id=user.id,
            customer_id=entry.customer_id, subject=f"Low feedback score ({entry.score}/10) follow-up",
            category="feedback", priority="high",
        )
        db.add(ticket)
        db.flush()
        entry.follow_up_ticket_id = ticket.id
        record_audit(db, membership, "ticket.created", "support_ticket", ticket.id, source="feedback")

    record_audit(db, membership, "feedback.submitted", "feedback", entry.id, score=entry.score)
    db.commit()
    return entry


@router.get("", response_model=list[FeedbackView])
def list_feedback(
    membership: CurrentMembership, db: Db,
    max_score: int | None = Query(default=None, ge=0, le=10),
    limit: int = Query(default=100, ge=1, le=500),
):
    require_permission(membership, "feedback:read")
    query = select(Feedback).where(Feedback.organization_id == membership.organization_id)
    if max_score is not None:
        query = query.where(Feedback.score <= max_score)
    return list(db.scalars(query.order_by(Feedback.created_at.desc()).limit(limit)))


@router.get("/summary")
def feedback_summary(membership: CurrentMembership, db: Db):
    """Average score and the promoter/passive/detractor split (classic NPS buckets)."""
    require_permission(membership, "feedback:read")
    scores = list(db.scalars(
        select(Feedback.score).where(Feedback.organization_id == membership.organization_id)
    ))
    if not scores:
        return {"count": 0, "average_score": None, "nps": None, "promoters": 0, "passives": 0, "detractors": 0}
    promoters = sum(1 for s in scores if s >= 9)
    detractors = sum(1 for s in scores if s <= 6)
    passives = len(scores) - promoters - detractors
    nps = round((promoters - detractors) / len(scores) * 100, 1)
    return {
        "count": len(scores), "average_score": round(sum(scores) / len(scores), 2),
        "nps": nps, "promoters": promoters, "passives": passives, "detractors": detractors,
    }
