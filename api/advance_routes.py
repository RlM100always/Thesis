"""Staff advances (SRD Panel H06): issue, repay, settle. Standalone ledger --
there is no payroll run yet to deduct it from automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .app_schemas import StaffAdvanceCreate, StaffAdvanceRepay, StaffAdvanceView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import StaffAdvance, StaffAdvanceRepayment
from .permissions import require_permission

router = APIRouter(prefix="/api/app/advances", tags=["advances"])
Db = Annotated[Session, Depends(get_db)]


def _repaid_total(db: Session, org_id: str, advance_id: str) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(StaffAdvanceRepayment.amount), 0)).where(
        StaffAdvanceRepayment.organization_id == org_id, StaffAdvanceRepayment.advance_id == advance_id))
    return Decimal(total)


def _view(advance: StaffAdvance, repaid: Decimal) -> dict:
    return {
        **StaffAdvanceView.model_validate(advance).model_dump(),
        "repaid_amount": repaid,
        "outstanding_amount": advance.amount - repaid,
    }


@router.post("")
def issue_advance(payload: StaffAdvanceCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "advances:write")
    advance = StaffAdvance(
        organization_id=membership.organization_id, created_by_user_id=user.id,
        issued_at=datetime.now(timezone.utc), **payload.model_dump(),
    )
    db.add(advance)
    db.flush()
    record_audit(db, membership, "advance.issued", "staff_advance", advance.id,
                 user_id=payload.user_id, amount=payload.amount)
    db.commit()
    return _view(advance, Decimal("0"))


@router.get("/me")
def my_advances(membership: CurrentMembership, user: CurrentUser, db: Db):
    rows = db.scalars(
        select(StaffAdvance).where(
            StaffAdvance.organization_id == membership.organization_id, StaffAdvance.user_id == user.id,
        ).order_by(StaffAdvance.issued_at.desc())
    ).all()
    return [_view(a, _repaid_total(db, membership.organization_id, a.id)) for a in rows]


@router.get("")
def list_advances(membership: CurrentMembership, db: Db,
                  status: str | None = Query(default=None, pattern=r"^(outstanding|settled)$")):
    require_permission(membership, "advances:read")
    query = select(StaffAdvance).where(StaffAdvance.organization_id == membership.organization_id)
    if status:
        query = query.where(StaffAdvance.status == status)
    rows = db.scalars(query.order_by(StaffAdvance.issued_at.desc())).all()
    return [_view(a, _repaid_total(db, membership.organization_id, a.id)) for a in rows]


@router.post("/{advance_id}/repay")
def repay_advance(advance_id: str, payload: StaffAdvanceRepay, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "advances:write")
    advance = db.scalar(select(StaffAdvance).where(
        StaffAdvance.id == advance_id, StaffAdvance.organization_id == membership.organization_id))
    if advance is None:
        raise HTTPException(status_code=404, detail="Advance not found")
    if advance.status == "settled":
        raise HTTPException(status_code=409, detail="This advance is already settled")
    repaid_so_far = _repaid_total(db, membership.organization_id, advance_id)
    if payload.amount > advance.amount - repaid_so_far:
        raise HTTPException(status_code=422, detail="Repayment exceeds the outstanding balance")
    db.add(StaffAdvanceRepayment(
        organization_id=membership.organization_id, advance_id=advance_id, amount=payload.amount,
        occurred_at=datetime.now(timezone.utc), recorded_by_user_id=user.id,
    ))
    new_total = repaid_so_far + payload.amount
    if new_total >= advance.amount:
        advance.status = "settled"
    record_audit(db, membership, "advance.repaid", "staff_advance", advance.id, amount=payload.amount)
    db.commit()
    return _view(advance, new_total)
