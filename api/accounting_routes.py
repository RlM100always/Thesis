"""Read-only accounting reports: chart of accounts, journal, trial balance,
profit & loss and balance sheet. Nothing here posts anything — every entry was
already posted by the route that caused it (see `api/accounting.py`)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounting import balance_sheet, period_month_of, profit_and_loss, trial_balance
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import Account, FiscalPeriod, JournalEntry, JournalLine
from .permissions import require_permission
from .timeutil import DHAKA, dhaka_today

router = APIRouter(prefix="/api/app/accounting")
Db = Annotated[Session, Depends(get_db)]


def _day_end(day) -> datetime:
    return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=DHAKA).astimezone(timezone.utc)


def _day_start(day) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=DHAKA).astimezone(timezone.utc)


@router.get("/accounts", tags=["accounting"])
def chart_of_accounts(membership: CurrentMembership, db: Db):
    require_permission(membership, "ledger:read")
    rows = db.scalars(select(Account).where(
        Account.organization_id == membership.organization_id, Account.active.is_(True)
    ).order_by(Account.code))
    return [{"code": a.code, "name": a.name, "type": a.type, "is_system": a.is_system} for a in rows]


@router.get("/trial-balance", tags=["accounting"])
def trial_balance_report(membership: CurrentMembership, db: Db, as_of: str | None = Query(default=None)):
    require_permission(membership, "ledger:read")
    day = dhaka_today() if as_of is None else datetime.fromisoformat(as_of).date()
    rows = trial_balance(db, membership.organization_id, _day_end(day))
    total_debit = sum((r["debit"] for r in rows), 0)
    total_credit = sum((r["credit"] for r in rows), 0)
    return {"as_of": day, "accounts": rows, "total_debit": total_debit, "total_credit": total_credit,
            "balanced": round(float(total_debit), 2) == round(float(total_credit), 2)}


@router.get("/profit-and-loss", tags=["accounting"])
def profit_and_loss_report(membership: CurrentMembership, db: Db, date_from: str, date_to: str):
    require_permission(membership, "ledger:read")
    start = datetime.fromisoformat(date_from).date()
    end = datetime.fromisoformat(date_to).date()
    return profit_and_loss(db, membership.organization_id, _day_start(start), _day_end(end))


@router.get("/balance-sheet", tags=["accounting"])
def balance_sheet_report(membership: CurrentMembership, db: Db, as_of: str | None = Query(default=None)):
    require_permission(membership, "ledger:read")
    day = dhaka_today() if as_of is None else datetime.fromisoformat(as_of).date()
    return balance_sheet(db, membership.organization_id, _day_end(day))


@router.get("/journal", tags=["accounting"])
def journal(
    membership: CurrentMembership, db: Db, limit: int = Query(default=100, ge=1, le=500),
    reference_type: str | None = None, account_code: str | None = None,
):
    """The full audit trail behind the reports above: every posted entry, its lines
    and which account each touched — the "explain this number" drill-down."""
    require_permission(membership, "ledger:read")
    org_id = membership.organization_id
    statement = select(JournalEntry).where(JournalEntry.organization_id == org_id)
    if reference_type:
        statement = statement.where(JournalEntry.reference_type == reference_type)
    if account_code:
        statement = statement.join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id).join(
            Account, Account.id == JournalLine.account_id).where(Account.code == account_code)
    entries = list(db.scalars(statement.order_by(JournalEntry.occurred_at.desc()).limit(limit)))
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.organization_id == org_id))}
    result = []
    for entry in entries:
        lines = db.scalars(select(JournalLine).where(JournalLine.journal_entry_id == entry.id))
        result.append({
            "id": entry.id, "occurred_at": entry.occurred_at, "memo": entry.memo,
            "reference_type": entry.reference_type, "reference_id": entry.reference_id,
            "lines": [{
                "account_code": accounts[line.account_id].code, "account_name": accounts[line.account_id].name,
                "debit": line.debit, "credit": line.credit,
            } for line in lines],
        })
    return result


class PeriodCloseIn(BaseModel):
    period_month: date  # any date in the target month; normalized to the 1st


class PeriodReopenIn(BaseModel):
    reason: str = Field(min_length=2, max_length=300)


@router.get("/periods", tags=["accounting"])
def list_periods(membership: CurrentMembership, db: Db):
    require_permission(membership, "ledger:read")
    rows = db.scalars(
        select(FiscalPeriod).where(FiscalPeriod.organization_id == membership.organization_id)
        .order_by(FiscalPeriod.period_month.desc())
    )
    return [{
        "id": p.id, "period_month": p.period_month, "status": p.status,
        "closed_at": p.closed_at, "reopened_at": p.reopened_at, "reopen_reason": p.reopen_reason,
    } for p in rows]


@router.post("/periods/close", tags=["accounting"])
def close_period(payload: PeriodCloseIn, membership: CurrentMembership, user: CurrentUser, db: Db):
    """Lock a calendar month: no journal entry may post into it afterwards (SRD F09)."""
    require_permission(membership, "period:close")
    org_id = membership.organization_id
    month = period_month_of(datetime(payload.period_month.year, payload.period_month.month, 1, tzinfo=timezone.utc))
    existing = db.scalar(select(FiscalPeriod).where(
        FiscalPeriod.organization_id == org_id, FiscalPeriod.period_month == month))
    if existing is not None and existing.status == "closed":
        raise HTTPException(status_code=409, detail="This period is already closed")
    if existing is not None:
        existing.status = "closed"
        existing.closed_by_user_id = user.id
        existing.closed_at = datetime.now(timezone.utc)
        period = existing
    else:
        period = FiscalPeriod(
            organization_id=org_id, period_month=month, status="closed",
            closed_by_user_id=user.id, closed_at=datetime.now(timezone.utc),
        )
        db.add(period)
    db.flush()
    record_audit(db, membership, "accounting.period_closed", "fiscal_period", period.id, period_month=str(month))
    db.commit()
    return {"period_month": month, "status": "closed"}


@router.post("/periods/{period_id}/reopen", tags=["accounting"])
def reopen_period(period_id: str, payload: PeriodReopenIn, membership: CurrentMembership, user: CurrentUser, db: Db):
    """Owner-only, reasoned, audited -- never implicit (SRD F09)."""
    require_permission(membership, "period:close")
    period = db.scalar(select(FiscalPeriod).where(
        FiscalPeriod.id == period_id, FiscalPeriod.organization_id == membership.organization_id))
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "closed":
        raise HTTPException(status_code=409, detail="This period is not closed")
    period.status = "reopened"
    period.reopened_by_user_id = user.id
    period.reopened_at = datetime.now(timezone.utc)
    period.reopen_reason = payload.reason
    record_audit(db, membership, "accounting.period_reopened", "fiscal_period", period.id, reason=payload.reason)
    db.commit()
    return {"period_month": period.period_month, "status": "reopened"}
