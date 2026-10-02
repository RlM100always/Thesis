"""Leads / Pipeline (SRD Panel C06): lead -> qualified -> quoted -> won/lost.

Winning a lead creates a real ``Customer`` row; a lead itself never gets a
credit limit, loyalty balance or sales history -- converting is the one-way
handoff into the customer/CRM world those belong to.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import (
    CustomerView, LeadActivityCreate, LeadActivityView, LeadCreate, LeadUpdate, LeadView,
)
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .directory_routes import phone_hash
from .domain_models import Customer, Lead, LeadActivity, Membership, new_id
from .permissions import require_permission

router = APIRouter(prefix="/api/app/leads", tags=["leads"])
Db = Annotated[Session, Depends(get_db)]

CLOSED_STAGES = {"won", "lost"}


def _get_lead(db: Session, membership: Membership, lead_id: str) -> Lead:
    lead = db.scalar(select(Lead).where(
        Lead.id == lead_id, Lead.organization_id == membership.organization_id,
    ))
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("", response_model=LeadView)
def create_lead(payload: LeadCreate, membership: CurrentMembership, db: Db):
    require_permission(membership, "leads:write")
    data = payload.model_dump(exclude={"phone"})
    lead = Lead(
        organization_id=membership.organization_id,
        phone_hash=phone_hash(membership.organization_id, payload.phone),
        **data,
    )
    db.add(lead)
    db.flush()
    record_audit(db, membership, "lead.created", "lead", lead.id, source=lead.source)
    db.commit()
    return lead


@router.get("", response_model=list[LeadView])
def list_leads(
    membership: CurrentMembership, db: Db,
    stage: str | None = Query(default=None, pattern=r"^(new|qualified|quoted|won|lost)$"),
    owner_user_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    require_permission(membership, "leads:read")
    query = select(Lead).where(Lead.organization_id == membership.organization_id)
    if stage:
        query = query.where(Lead.stage == stage)
    if owner_user_id:
        query = query.where(Lead.owner_user_id == owner_user_id)
    return list(db.scalars(query.order_by(Lead.created_at.desc()).limit(limit)))


@router.get("/{lead_id}", response_model=LeadView)
def get_lead(lead_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "leads:read")
    return _get_lead(db, membership, lead_id)


@router.patch("/{lead_id}", response_model=LeadView)
def update_lead(lead_id: str, payload: LeadUpdate, membership: CurrentMembership, db: Db):
    """Move a lead through the pipeline. Use ``/convert`` to win it into a customer."""
    require_permission(membership, "leads:write")
    lead = _get_lead(db, membership, lead_id)
    if lead.stage in CLOSED_STAGES:
        raise HTTPException(status_code=409, detail="This lead is already closed")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to change")
    if changes.get("stage") == "won":
        raise HTTPException(status_code=422, detail="Use POST /leads/{id}/convert to win a lead")
    if changes.get("stage") == "lost" and not changes.get("lost_reason") and not lead.lost_reason:
        raise HTTPException(status_code=422, detail="A lost lead needs a reason")
    before = {field: getattr(lead, field) for field in changes}
    for field, value in changes.items():
        setattr(lead, field, value)
    if changes.get("stage") == "lost":
        lead.closed_at = datetime.now(timezone.utc)
    record_audit(db, membership, "lead.updated", "lead", lead.id, before=before, after=changes)
    db.commit()
    return lead


@router.post("/{lead_id}/convert", response_model=CustomerView)
def convert_lead(lead_id: str, membership: CurrentMembership, db: Db):
    """Win the lead: create its Customer record exactly once."""
    require_permission(membership, "leads:write")
    lead = _get_lead(db, membership, lead_id)
    if lead.stage in CLOSED_STAGES:
        raise HTTPException(status_code=409, detail="This lead is already closed")
    customer = Customer(
        organization_id=membership.organization_id, code=f"LEAD-{new_id()[:8]}",
        display_name=lead.name, phone_hash=lead.phone_hash,
    )
    db.add(customer)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create customer from this lead") from exc
    lead.stage = "won"
    lead.converted_customer_id = customer.id
    lead.closed_at = datetime.now(timezone.utc)
    record_audit(db, membership, "lead.converted", "lead", lead.id, customer_id=customer.id)
    db.commit()
    return customer


@router.post("/{lead_id}/activities", response_model=LeadActivityView)
def add_activity(lead_id: str, payload: LeadActivityCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "leads:write")
    lead = _get_lead(db, membership, lead_id)
    activity = LeadActivity(lead_id=lead.id, author_user_id=user.id, **payload.model_dump())
    db.add(activity)
    db.commit()
    return activity


@router.get("/{lead_id}/activities", response_model=list[LeadActivityView])
def list_activities(lead_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "leads:read")
    _get_lead(db, membership, lead_id)
    return list(db.scalars(
        select(LeadActivity).where(LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.created_at.asc())
    ))
