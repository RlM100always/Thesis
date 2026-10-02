"""Leave (SRD Panel H04): request -> approve/reject, or cancel while pending.
Self-service request/view needs no special permission -- it's your own leave.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import LeaveDecision, LeaveRequestCreate, LeaveRequestView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import LeaveRequest
from .notifications import notify_roles
from .permissions import require_permission

router = APIRouter(prefix="/api/app/leave", tags=["leave"])
Db = Annotated[Session, Depends(get_db)]


@router.post("", response_model=LeaveRequestView)
def request_leave(payload: LeaveRequestCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    leave = LeaveRequest(organization_id=membership.organization_id, user_id=user.id, **payload.model_dump())
    db.add(leave)
    db.flush()
    notify_roles(
        db, membership.organization_id, ("owner", "manager"), "staff",
        title=f"Leave request: {leave.start_date} to {leave.end_date}",
        link_type="leave_request", link_id=leave.id,
    )
    db.commit()
    return leave


@router.get("/me", response_model=list[LeaveRequestView])
def my_leave(membership: CurrentMembership, user: CurrentUser, db: Db):
    rows = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.organization_id == membership.organization_id, LeaveRequest.user_id == user.id,
        ).order_by(LeaveRequest.start_date.desc())
    )
    return list(rows)


@router.post("/{leave_id}/cancel", response_model=LeaveRequestView)
def cancel_leave(leave_id: str, membership: CurrentMembership, user: CurrentUser, db: Db):
    leave = db.scalar(select(LeaveRequest).where(
        LeaveRequest.id == leave_id, LeaveRequest.organization_id == membership.organization_id,
        LeaveRequest.user_id == user.id,
    ))
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != "pending":
        raise HTTPException(status_code=409, detail="Only a pending request can be cancelled")
    leave.status = "cancelled"
    db.commit()
    return leave


@router.get("", response_model=list[LeaveRequestView])
def list_leave(
    membership: CurrentMembership, db: Db,
    status: str | None = Query(default=None, pattern=r"^(pending|approved|rejected|cancelled)$"),
    user_id: str | None = Query(default=None),
):
    require_permission(membership, "leave:read")
    query = select(LeaveRequest).where(LeaveRequest.organization_id == membership.organization_id)
    if status:
        query = query.where(LeaveRequest.status == status)
    if user_id:
        query = query.where(LeaveRequest.user_id == user_id)
    return list(db.scalars(query.order_by(LeaveRequest.created_at.desc())))


@router.post("/{leave_id}/decide", response_model=LeaveRequestView)
def decide_leave(leave_id: str, payload: LeaveDecision, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "leave:decide")
    leave = db.scalar(select(LeaveRequest).where(
        LeaveRequest.id == leave_id, LeaveRequest.organization_id == membership.organization_id,
    ))
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.status != "pending":
        raise HTTPException(status_code=409, detail="This request was already decided")
    leave.status = payload.status
    leave.decided_by_user_id = user.id
    leave.decided_at = datetime.now(timezone.utc)
    leave.decision_reason = payload.reason
    record_audit(db, membership, "leave.decided", "leave_request", leave.id,
                 status=payload.status, requester=leave.user_id)
    db.commit()
    return leave
