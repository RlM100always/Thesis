"""Roster (SRD Panel H02): the shift plan. Separate from `attendance_routes.py`,
which records what actually happened -- the roster is intent, attendance is fact.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import RosterShiftCreate, RosterShiftView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import Branch, RosterShift
from .notifications import notify_user
from .permissions import require_permission

router = APIRouter(prefix="/api/app/roster", tags=["roster"])
Db = Annotated[Session, Depends(get_db)]


@router.post("", response_model=RosterShiftView)
def create_shift(payload: RosterShiftCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "roster:write")
    branch = db.scalar(select(Branch).where(
        Branch.id == payload.branch_id, Branch.organization_id == membership.organization_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    overlap = db.scalar(select(RosterShift).where(
        RosterShift.organization_id == membership.organization_id, RosterShift.user_id == payload.user_id,
        RosterShift.shift_date == payload.shift_date,
        RosterShift.start_time < payload.end_time, RosterShift.end_time > payload.start_time,
    ))
    if overlap is not None:
        raise HTTPException(status_code=409, detail="This person already has an overlapping shift that day")
    shift = RosterShift(
        organization_id=membership.organization_id, created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(shift)
    db.flush()
    notify_user(
        db, membership.organization_id, payload.user_id, "staff",
        title=f"New shift on {payload.shift_date}: {payload.start_time}-{payload.end_time}",
        link_type="roster_shift", link_id=shift.id,
    )
    record_audit(db, membership, "roster.shift_created", "roster_shift", shift.id, user_id=payload.user_id)
    db.commit()
    return shift


@router.get("/me", response_model=list[RosterShiftView])
def my_roster(membership: CurrentMembership, user: CurrentUser, db: Db,
             from_date: date | None = Query(default=None), to_date: date | None = Query(default=None)):
    query = select(RosterShift).where(
        RosterShift.organization_id == membership.organization_id, RosterShift.user_id == user.id,
    )
    if from_date:
        query = query.where(RosterShift.shift_date >= from_date)
    if to_date:
        query = query.where(RosterShift.shift_date <= to_date)
    return list(db.scalars(query.order_by(RosterShift.shift_date)))


@router.get("", response_model=list[RosterShiftView])
def list_roster(
    membership: CurrentMembership, db: Db,
    branch_id: str | None = Query(default=None),
    from_date: date | None = Query(default=None), to_date: date | None = Query(default=None),
):
    require_permission(membership, "staff:read")
    query = select(RosterShift).where(RosterShift.organization_id == membership.organization_id)
    if branch_id:
        query = query.where(RosterShift.branch_id == branch_id)
    if from_date:
        query = query.where(RosterShift.shift_date >= from_date)
    if to_date:
        query = query.where(RosterShift.shift_date <= to_date)
    return list(db.scalars(query.order_by(RosterShift.shift_date)))


@router.delete("/{shift_id}")
def delete_shift(shift_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "roster:write")
    shift = db.scalar(select(RosterShift).where(
        RosterShift.id == shift_id, RosterShift.organization_id == membership.organization_id))
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    db.delete(shift)
    record_audit(db, membership, "roster.shift_removed", "roster_shift", shift_id, user_id=shift.user_id)
    db.commit()
    return {"status": "removed"}
