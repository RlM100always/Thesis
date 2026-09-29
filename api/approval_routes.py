"""The Approval Inbox: see what's held, and decide it.

Approving replays the original request through the same posting code the direct
route uses (see `finance_routes.post_expense`) — an approved expense is posted
exactly like one nobody needed to approve, not through a second, less-tested path.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import ExpenseCreate, ExpenseView, PurchaseCreate
from .audit import record_audit
from .auth import CurrentMembership
from .database import get_db
from .domain_models import ApprovalRequest, ApprovalRule, User, utcnow
from .permissions import require_permission

router = APIRouter(prefix="/api/app/approvals")
Db = Annotated[Session, Depends(get_db)]

# kind -> the Pydantic schema its stored payload was validated against, and the
# function that actually posts it once approved. Add an entry here when a new
# kind of request is wired up (see api/approvals.py's module docstring).
KIND_SCHEMA = {"expense_amount": ExpenseCreate, "purchase_amount": PurchaseCreate}


def _post(kind: str, db: Session, membership, payload) -> str:
    if kind == "expense_amount":
        from .finance_routes import post_expense
        return post_expense(db, membership, payload).id
    if kind == "purchase_amount":
        from .finance_routes import post_purchase
        return post_purchase(db, membership, payload).id
    raise HTTPException(status_code=500, detail=f"No poster wired for approval kind {kind!r}")


def _view(request: ApprovalRequest, requester_name: str | None, decider_name: str | None) -> dict:
    return {
        "id": request.id, "kind": request.kind, "amount": request.amount, "status": request.status,
        "payload": json.loads(request.payload), "requested_by": requester_name,
        "requested_at": request.created_at, "decided_by": decider_name, "decided_at": request.decided_at,
        "decision_reason": request.decision_reason, "result_reference_id": request.result_reference_id,
    }


@router.get("", tags=["approvals"])
def list_approvals(
    membership: CurrentMembership, db: Db, status: str = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=500),
):
    require_permission(membership, "approvals:read")
    org_id = membership.organization_id
    statement = select(ApprovalRequest).where(ApprovalRequest.organization_id == org_id)
    if status != "all":
        statement = statement.where(ApprovalRequest.status == status)
    rows = list(db.scalars(statement.order_by(ApprovalRequest.created_at.desc()).limit(limit)))
    user_ids = {r.requested_by_user_id for r in rows} | {r.decided_by_user_id for r in rows if r.decided_by_user_id}
    names = {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_(user_ids or {""})))}
    return [_view(r, names.get(r.requested_by_user_id), names.get(r.decided_by_user_id)) for r in rows]


class DecisionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/{request_id}/approve", tags=["approvals"])
def approve(request_id: str, body: DecisionIn, membership: CurrentMembership, db: Db):
    """Post the held action for real, exactly as it would have posted unheld."""
    require_permission(membership, "approvals:decide")
    org_id = membership.organization_id
    request = db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.id == request_id, ApprovalRequest.organization_id == org_id).with_for_update())
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request was already {request.status}")
    schema = KIND_SCHEMA.get(request.kind)
    if schema is None:
        raise HTTPException(status_code=500, detail=f"No schema registered for approval kind {request.kind!r}")
    payload = schema.model_validate_json(request.payload)
    result_id = _post(request.kind, db, membership, payload)
    request.status = "approved"
    request.decided_by_user_id = membership.user_id
    request.decided_at = utcnow()
    request.decision_reason = body.reason
    request.result_reference_id = result_id
    record_audit(db, membership, "approval.approved", "approval_request", request.id,
                 kind=request.kind, amount=request.amount, result_id=result_id)
    db.commit()
    return {"status": "approved", "result_reference_id": result_id}


@router.post("/{request_id}/reject", tags=["approvals"])
def reject(request_id: str, body: DecisionIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "approvals:decide")
    if body.reason is None or len(body.reason.strip()) < 2:
        raise HTTPException(status_code=422, detail="A reason is required to reject a request")
    org_id = membership.organization_id
    request = db.scalar(select(ApprovalRequest).where(
        ApprovalRequest.id == request_id, ApprovalRequest.organization_id == org_id).with_for_update())
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request was already {request.status}")
    request.status = "rejected"
    request.decided_by_user_id = membership.user_id
    request.decided_at = utcnow()
    request.decision_reason = body.reason
    record_audit(db, membership, "approval.rejected", "approval_request", request.id,
                 kind=request.kind, amount=request.amount, reason=body.reason)
    db.commit()
    return {"status": "rejected"}


@router.get("/rules", tags=["approvals"])
def list_rules(membership: CurrentMembership, db: Db):
    require_permission(membership, "approvals:read")
    rows = db.scalars(select(ApprovalRule).where(ApprovalRule.organization_id == membership.organization_id))
    return [{"kind": r.kind, "threshold": r.threshold, "approver_role": r.approver_role, "active": r.active} for r in rows]


class RuleUpdate(BaseModel):
    threshold: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    approver_role: str | None = Field(default=None, pattern=r"^(manager|owner)$")
    active: bool | None = None


@router.patch("/rules/{kind}", tags=["approvals"])
def update_rule(kind: str, body: RuleUpdate, membership: CurrentMembership, db: Db):
    """Owner-only: change the threshold, who must approve, or turn a rule off."""
    require_permission(membership, "settings:write")
    rule = db.scalar(select(ApprovalRule).where(
        ApprovalRule.organization_id == membership.organization_id, ApprovalRule.kind == kind))
    if rule is None:
        raise HTTPException(status_code=404, detail="Unknown approval rule")
    changes = {}
    if body.threshold is not None:
        rule.threshold = body.threshold
        changes["threshold"] = body.threshold
    if body.approver_role is not None:
        rule.approver_role = body.approver_role
        changes["approver_role"] = body.approver_role
    if body.active is not None:
        rule.active = body.active
        changes["active"] = body.active
    record_audit(db, membership, "approval_rule.updated", "approval_rule", rule.id, kind=kind, **changes)
    db.commit()
    return {"kind": rule.kind, "threshold": rule.threshold, "approver_role": rule.approver_role, "active": rule.active}
