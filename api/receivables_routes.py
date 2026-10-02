"""Baki ageing: who owes how much, and for how long.

The receivable ledger is a running account, not a list of invoices, so age is worked
out the way a shopkeeper would: payments clear the *oldest* debts first (first in,
first out), and whatever is left is aged from the day it was created. Nothing here is
predicted; it is arithmetic on the ledger.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .database import get_db
from .domain_models import Customer, LedgerEntry, Supplier
from .permissions import require_permission
from .timeutil import DHAKA, dhaka_today

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
ZERO = Decimal("0")
BUCKETS = (("d0_30", 30), ("d31_60", 60), ("d61_90", 90), ("d90_plus", None))


def _day(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)  # stored as UTC
    return moment.astimezone(DHAKA).date()


def age_debts(entries: list[tuple[datetime, Decimal]], today: date) -> tuple[dict[str, Decimal], int | None]:
    """FIFO: credits (negative deltas) clear the oldest debts first; what is left is bucketed by age.

    Returns the bucket totals and the age in days of the oldest debt still unpaid
    (``None`` if nothing is left owing), computed in one pass over the same ordering.
    """
    ordered = sorted(entries, key=lambda e: e[0])
    credit = -sum((d for _, d in ordered if d < 0), ZERO)
    buckets = {name: ZERO for name, _ in BUCKETS}
    oldest_days = None
    for moment, delta in ordered:
        if delta <= 0:
            continue
        cleared = min(credit, delta)
        credit -= cleared
        left = delta - cleared
        if left <= 0:
            continue
        days = max(0, (today - _day(moment)).days)
        if oldest_days is None:
            oldest_days = days
        for name, limit in BUCKETS:
            if limit is None or days <= limit:
                buckets[name] += left
                break
    return buckets, oldest_days


@router.get("/receivables/ageing", tags=["ledger"])
def receivables_ageing(membership: CurrentMembership, db: Db):
    require_permission(membership, "ledger:read")
    org_id = membership.organization_id
    today = dhaka_today()
    per_customer: dict[str, list[tuple[datetime, Decimal]]] = {}
    for party_id, moment, delta in db.execute(
        select(LedgerEntry.party_id, LedgerEntry.occurred_at, LedgerEntry.amount_delta).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
            LedgerEntry.party_type == "customer", LedgerEntry.party_id.is_not(None))
    ).all():
        per_customer.setdefault(party_id, []).append((moment, delta))
    customers = {c.id: c for c in db.scalars(select(Customer).where(
        Customer.organization_id == org_id, Customer.id.in_(list(per_customer))))}

    rows, totals = [], {name: ZERO for name, _ in BUCKETS}
    for customer_id, entries in per_customer.items():
        balance = sum((d for _, d in entries), ZERO)
        if balance <= 0 or customer_id not in customers:
            continue
        buckets, oldest = age_debts(entries, today)
        customer = customers[customer_id]
        limit = customer.credit_limit
        rows.append({
            "customer_id": customer_id, "code": customer.code, "name": customer.display_name,
            "balance": balance, "credit_limit": limit,
            "over_limit": limit is not None and balance > limit,
            "oldest_days": oldest, **buckets,
        })
        for name in totals:
            totals[name] += buckets[name]
    rows.sort(key=lambda r: (r["oldest_days"] or 0, r["balance"]), reverse=True)
    return {"as_of": today, "total": sum((r["balance"] for r in rows), ZERO), "buckets": totals, "customers": rows}


@router.get("/payables/ageing", tags=["ledger"])
def payables_ageing(membership: CurrentMembership, db: Db):
    """Supplier Payable (SRD Panel P08): the mirror of receivables ageing, on the money we owe."""
    require_permission(membership, "ledger:read")
    org_id = membership.organization_id
    today = dhaka_today()
    per_supplier: dict[str, list[tuple[datetime, Decimal]]] = {}
    for party_id, moment, delta in db.execute(
        select(LedgerEntry.party_id, LedgerEntry.occurred_at, LedgerEntry.amount_delta).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "payable",
            LedgerEntry.party_type == "supplier", LedgerEntry.party_id.is_not(None))
    ).all():
        per_supplier.setdefault(party_id, []).append((moment, delta))
    suppliers = {s.id: s for s in db.scalars(select(Supplier).where(
        Supplier.organization_id == org_id, Supplier.id.in_(list(per_supplier))))}

    rows, totals = [], {name: ZERO for name, _ in BUCKETS}
    for supplier_id, entries in per_supplier.items():
        balance = sum((d for _, d in entries), ZERO)
        if balance <= 0 or supplier_id not in suppliers:
            continue
        buckets, oldest = age_debts(entries, today)
        supplier = suppliers[supplier_id]
        rows.append({
            "supplier_id": supplier_id, "code": supplier.code, "name": supplier.name,
            "balance": balance, "oldest_days": oldest, **buckets,
        })
        for name in totals:
            totals[name] += buckets[name]
    rows.sort(key=lambda r: (r["oldest_days"] or 0, r["balance"]), reverse=True)
    return {"as_of": today, "total": sum((r["balance"] for r in rows), ZERO), "buckets": totals, "suppliers": rows}
