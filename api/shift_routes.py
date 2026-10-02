"""Cashier shift: a cashier's own drawer accountability window.

Distinct from ``api/insights_routes.py``'s ``cash/close`` (the owner/
accountant's once-a-day book for the whole branch): several cashiers can each
open their own shift on the same branch on the same day, every cash sale or
refund made while a shift is open belongs to it (``Payment.shift_id``), and a
mid-shift cash drop/add is its own record rather than silently folded into
the count at close. Closing computes expected cash the same honest way
``cash/close`` does (``insights_routes.cash_window``), just over the shift's
own [opened_at, closed_at) window instead of a calendar day.

A shortage or overage past the ``cash_shortage`` approval rule's threshold
needs a qualifying manager/owner's own credentials at close time — the same
synchronous-override pattern as a POS discount or refund (``api/approvals.py``):
a cashier closing a drawer at the end of the day cannot wait for an async
inbox to get home.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .approvals import needs_approval, verify_override
from .audit import record_audit
from .auth import CurrentMembership
from .database import get_db
from .domain_models import Branch, CashMovement, CashierShift, User
from .insights_routes import cash_window, expected_cash
from .permissions import require_permission

router = APIRouter(prefix="/api/app/shifts")
Db = Annotated[Session, Depends(get_db)]
ZERO = Decimal("0")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _view(shift: CashierShift, cashier_name: str | None, movements: list[CashMovement] | None = None) -> dict:
    return {
        "id": shift.id, "branch_id": shift.branch_id, "user_id": shift.user_id, "cashier_name": cashier_name,
        "drawer_label": shift.drawer_label, "status": shift.status,
        "opening_cash": shift.opening_cash, "opened_at": shift.opened_at.isoformat(),
        "expected_cash": shift.expected_cash, "counted_cash": shift.counted_cash, "variance": shift.variance,
        "note": shift.note, "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "movements": None if movements is None else [{
            "id": m.id, "direction": m.direction, "amount": m.amount, "reason": m.reason,
            "created_at": m.created_at.isoformat(),
        } for m in movements],
    }


def _movement_net(movements: list[CashMovement]) -> Decimal:
    # A drop removes cash from the drawer (it should no longer be expected at
    # close); an add puts cash back in (it should be).
    net = ZERO
    for m in movements:
        net += -m.amount if m.direction == "drop" else m.amount
    return net


def _shift_expected(db: Session, org_id: str, shift: CashierShift, end: datetime) -> Decimal:
    parts = cash_window(db, org_id, shift.branch_id, shift.opened_at, end)
    movements = list(db.scalars(select(CashMovement).where(CashMovement.shift_id == shift.id)))
    return expected_cash(shift.opening_cash, parts) + _movement_net(movements)


@router.get("/current", tags=["cash"])
def current_shift(membership: CurrentMembership, db: Db, branch_id: str):
    """This cashier's own open shift on this branch, or ``None``."""
    require_permission(membership, "cash:read")
    shift = db.scalar(select(CashierShift).where(
        CashierShift.organization_id == membership.organization_id, CashierShift.branch_id == branch_id,
        CashierShift.user_id == membership.user_id, CashierShift.status == "open"))
    if shift is None:
        return None
    movements = list(db.scalars(select(CashMovement).where(CashMovement.shift_id == shift.id)))
    shift.expected_cash = _shift_expected(db, membership.organization_id, shift, _now())
    return _view(shift, None, movements)


class ShiftOpenIn(BaseModel):
    branch_id: str
    drawer_label: str | None = Field(default=None, max_length=60)
    opening_cash: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


@router.post("/open", tags=["cash"])
def open_shift(body: ShiftOpenIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "cash:close")
    org_id = membership.organization_id
    branch = db.scalar(select(Branch).where(Branch.id == body.branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    existing = db.scalar(select(CashierShift.id).where(
        CashierShift.organization_id == org_id, CashierShift.branch_id == body.branch_id,
        CashierShift.user_id == membership.user_id, CashierShift.status == "open"))
    if existing:
        raise HTTPException(status_code=409, detail="You already have an open shift on this branch")
    shift = CashierShift(
        organization_id=org_id, branch_id=body.branch_id, user_id=membership.user_id,
        drawer_label=body.drawer_label, opening_cash=body.opening_cash,
    )
    db.add(shift)
    db.flush()
    record_audit(db, membership, "shift.opened", "cashier_shift", shift.id,
                 branch_id=body.branch_id, opening_cash=body.opening_cash)
    db.commit()
    return _view(shift, None, [])


class MovementIn(BaseModel):
    direction: str = Field(pattern=r"^(drop|add)$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reason: str = Field(min_length=1, max_length=200)


@router.post("/{shift_id}/movements", tags=["cash"])
def add_movement(shift_id: str, body: MovementIn, membership: CurrentMembership, db: Db):
    """A cash drop (to the safe) or add (topping up change) mid-shift — not a
    sale, refund or expense, but it changes what should be left at close."""
    require_permission(membership, "cash:close")
    org_id = membership.organization_id
    shift = db.scalar(select(CashierShift).where(
        CashierShift.id == shift_id, CashierShift.organization_id == org_id))
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.status != "open":
        raise HTTPException(status_code=409, detail="This shift is already closed")
    if shift.user_id != membership.user_id and membership.role not in ("owner", "manager"):
        raise HTTPException(status_code=403, detail="Only the shift's own cashier or a manager can record this")
    movement = CashMovement(
        organization_id=org_id, shift_id=shift_id, direction=body.direction,
        amount=body.amount, reason=body.reason, created_by=membership.user_id,
    )
    db.add(movement)
    db.flush()
    record_audit(db, membership, "shift.cash_movement", "cashier_shift", shift_id,
                 direction=body.direction, amount=body.amount, reason=body.reason)
    db.commit()
    return {"id": movement.id, "direction": movement.direction, "amount": movement.amount, "reason": movement.reason}


class ShiftCloseIn(BaseModel):
    counted_cash: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    note: str | None = Field(default=None, max_length=300)
    override_email: str | None = None
    override_password: str | None = None


@router.post("/{shift_id}/close", tags=["cash"])
def close_shift(shift_id: str, body: ShiftCloseIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "cash:close")
    org_id = membership.organization_id
    shift = db.scalar(select(CashierShift).where(
        CashierShift.id == shift_id, CashierShift.organization_id == org_id))
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.status != "open":
        raise HTTPException(status_code=409, detail="This shift is already closed")
    if shift.user_id != membership.user_id and membership.role not in ("owner", "manager"):
        raise HTTPException(status_code=403, detail="Only the shift's own cashier or a manager can close it")

    closed_at = _now()
    expected = _shift_expected(db, org_id, shift, closed_at)
    variance = body.counted_cash - expected
    if variance != 0 and not (body.note and body.note.strip()):
        raise HTTPException(status_code=422, detail="A note is required when the count does not match the books")

    rule = needs_approval(db, org_id, "cash_shortage", abs(variance), membership.role)
    if rule is not None:
        if not verify_override(db, org_id, rule, body.override_email, body.override_password):
            raise HTTPException(status_code=403, detail={
                "code": "cash_shortage_override_required", "variance": float(variance),
                "threshold": float(rule.threshold), "needs_role": rule.approver_role,
            })

    shift.status = "closed"
    shift.closed_at = closed_at
    shift.closed_by = membership.user_id
    shift.expected_cash = expected
    shift.counted_cash = body.counted_cash
    shift.variance = variance
    shift.note = body.note
    db.flush()
    record_audit(db, membership, "shift.closed", "cashier_shift", shift.id,
                 expected=expected, counted=body.counted_cash, variance=variance)
    db.commit()
    return _view(shift, None, list(db.scalars(select(CashMovement).where(CashMovement.shift_id == shift.id))))


@router.get("/history", tags=["cash"])
def shift_history(membership: CurrentMembership, db: Db, branch_id: str | None = None, limit: int = 30):
    """Recent shifts on this branch (or all branches), any cashier — a
    manager's view, not just "my own shift"."""
    require_permission(membership, "cash:read")
    statement = select(CashierShift).where(CashierShift.organization_id == membership.organization_id)
    if branch_id:
        statement = statement.where(CashierShift.branch_id == branch_id)
    shifts = list(db.scalars(statement.order_by(CashierShift.opened_at.desc()).limit(limit)))
    names = {u.id: u.display_name for u in db.scalars(select(User).where(
        User.id.in_({s.user_id for s in shifts})))} if shifts else {}
    return [_view(s, names.get(s.user_id)) for s in shifts]
