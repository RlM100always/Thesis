"""Read-only accounting reports: chart of accounts, journal, trial balance,
profit & loss and balance sheet. Nothing here posts anything — every entry was
already posted by the route that caused it (see `api/accounting.py`)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounting import balance_sheet, profit_and_loss, trial_balance
from .auth import CurrentMembership
from .database import get_db
from .domain_models import Account, JournalEntry, JournalLine
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
