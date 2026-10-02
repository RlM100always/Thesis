"""Payroll (SRD Panel H06): draft -> approve -> pay, maker-checker enforced by
permission (``payroll:write`` drafts, ``payroll:approve`` approves,
``payroll:pay`` pays -- no single role here has all three by default).

A draft's lines are computed from what already happened: `Membership.base_salary`
plus the period's `CommissionEntry` net. They freeze the moment the run is
approved; a correction after that is a new run, never a silent edit.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import MembershipSalaryUpdate, PayrollLineView, PayrollRunCreate, PayrollRunView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import CommissionEntry, Membership, PayrollLine, PayrollRun
from .permissions import require_permission

router = APIRouter(prefix="/api/app/payroll", tags=["payroll"])
Db = Annotated[Session, Depends(get_db)]


def _commission_for_period(db: Session, org_id: str, user_id: str, start: date, end: date) -> Decimal:
    from_ts = datetime.combine(start, time.min, tzinfo=timezone.utc)
    to_ts = datetime.combine(end, time.max, tzinfo=timezone.utc)
    total = db.scalar(select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
        CommissionEntry.organization_id == org_id, CommissionEntry.user_id == user_id,
        CommissionEntry.occurred_at >= from_ts, CommissionEntry.occurred_at <= to_ts,
    ))
    return Decimal(total)


@router.patch("/salary/{membership_id}")
def set_base_salary(membership_id: str, payload: MembershipSalaryUpdate, membership: CurrentMembership, db: Db):
    """Owner-only: a person's monthly base salary. Sensitive, so it's not on the
    general staff-edit endpoint."""
    require_permission(membership, "staff:manage")
    target = db.scalar(select(Membership).where(
        Membership.id == membership_id, Membership.organization_id == membership.organization_id))
    if target is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    target.base_salary = payload.base_salary
    record_audit(db, membership, "staff.salary_set", "membership", membership_id)
    db.commit()
    return {"membership_id": membership_id, "base_salary": target.base_salary}


@router.post("/runs", response_model=PayrollRunView)
def create_run(payload: PayrollRunCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "payroll:write")
    org_id = membership.organization_id
    run = PayrollRun(organization_id=org_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(run)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A payroll run for this exact period already exists") from exc

    members = db.scalars(select(Membership).where(
        Membership.organization_id == org_id, Membership.active.is_(True),
        Membership.base_salary.is_not(None),
    )).all()
    for member in members:
        commission = _commission_for_period(db, org_id, member.user_id, payload.period_start, payload.period_end)
        net_pay = member.base_salary + commission
        db.add(PayrollLine(
            organization_id=org_id, payroll_run_id=run.id, user_id=member.user_id,
            base_salary=member.base_salary, commission_amount=commission, net_pay=net_pay,
        ))
    record_audit(db, membership, "payroll.run_created", "payroll_run", run.id,
                 period_start=str(payload.period_start), period_end=str(payload.period_end), lines=len(members))
    db.commit()
    return run


@router.get("/runs", response_model=list[PayrollRunView])
def list_runs(membership: CurrentMembership, db: Db):
    require_permission(membership, "payroll:read")
    return list(db.scalars(
        select(PayrollRun).where(PayrollRun.organization_id == membership.organization_id)
        .order_by(PayrollRun.period_start.desc())
    ))


@router.get("/runs/{run_id}")
def get_run(run_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "payroll:read")
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == membership.organization_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    lines = db.scalars(select(PayrollLine).where(PayrollLine.payroll_run_id == run_id)).all()
    return {
        **PayrollRunView.model_validate(run).model_dump(),
        "lines": [PayrollLineView.model_validate(l) for l in lines],
        "total_net_pay": sum((l.net_pay for l in lines), Decimal("0")),
    }


@router.post("/runs/{run_id}/approve", response_model=PayrollRunView)
def approve_run(run_id: str, membership: CurrentMembership, user: CurrentUser, db: Db):
    """Separate from preparing it -- maker-checker (SRD H06)."""
    require_permission(membership, "payroll:approve")
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == membership.organization_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot approve from status {run.status!r}")
    if run.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail="The person who prepared this run cannot also approve it")
    run.status = "approved"
    run.approved_by_user_id = user.id
    run.approved_at = datetime.now(timezone.utc)
    record_audit(db, membership, "payroll.run_approved", "payroll_run", run.id)
    db.commit()
    return run


@router.post("/runs/{run_id}/pay", response_model=PayrollRunView)
def pay_run(run_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "payroll:pay")
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == membership.organization_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved run can be paid")
    run.status = "paid"
    run.paid_at = datetime.now(timezone.utc)
    record_audit(db, membership, "payroll.run_paid", "payroll_run", run.id)
    db.commit()
    return run


@router.get("/me")
def my_payslips(membership: CurrentMembership, user: CurrentUser, db: Db):
    """Only paid runs -- a draft/approved figure isn't a payslip yet."""
    rows = db.execute(
        select(PayrollLine, PayrollRun)
        .join(PayrollRun, PayrollRun.id == PayrollLine.payroll_run_id)
        .where(
            PayrollLine.organization_id == membership.organization_id, PayrollLine.user_id == user.id,
            PayrollRun.status == "paid",
        ).order_by(PayrollRun.period_start.desc())
    ).all()
    return [{
        "period_start": run.period_start, "period_end": run.period_end, "paid_at": run.paid_at,
        **PayrollLineView.model_validate(line).model_dump(),
    } for line, run in rows]
