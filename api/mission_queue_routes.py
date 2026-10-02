"""Today Mission Queue (product plan Idea 1): one priority-ordered list of
what actually needs this person's attention right now, pulled live from the
same tables every other panel already reads -- never a separate task store
that could drift from reality.

Priority is explainable: each item carries the raw fact (age, amount, count)
its score came from, not just a number.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import (
    ApprovalRequest, InventoryBalance, LeaveRequest, Product, SupportTicket,
)
from .permissions import has_permission
from .receivables_routes import age_debts
from .domain_models import Customer, LedgerEntry

router = APIRouter(prefix="/api/app/mission-queue", tags=["insights"])
Db = Annotated[Session, Depends(get_db)]


def _age_days(moment: datetime) -> int:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - moment).days)


def _approval_items(db: Session, org_id: str) -> list[dict]:
    rows = db.scalars(select(ApprovalRequest).where(
        ApprovalRequest.organization_id == org_id, ApprovalRequest.status == "pending",
    )).all()
    items = []
    for r in rows:
        age = _age_days(r.created_at)
        items.append({
            "type": "approval", "title": f"{r.kind.replace('_', ' ').title()} needs approval ({r.amount} BDT)",
            "priority": min(100, 40 + age * 10), "age_days": age,
            "link_type": "approval_request", "link_id": r.id,
        })
    return items


def _ticket_items(db: Session, org_id: str) -> list[dict]:
    rows = db.scalars(select(SupportTicket).where(
        SupportTicket.organization_id == org_id, SupportTicket.status.in_(("open", "pending")),
        SupportTicket.priority.in_(("high", "urgent")),
    )).all()
    items = []
    for t in rows:
        age = _age_days(t.created_at)
        base = 70 if t.priority == "urgent" else 50
        items.append({
            "type": "ticket", "title": f"{t.priority.title()} ticket: {t.subject}",
            "priority": min(100, base + age * 5), "age_days": age,
            "link_type": "support_ticket", "link_id": t.id,
        })
    return items


def _leave_items(db: Session, org_id: str) -> list[dict]:
    rows = db.scalars(select(LeaveRequest).where(
        LeaveRequest.organization_id == org_id, LeaveRequest.status == "pending",
    )).all()
    items = []
    for leave in rows:
        age = _age_days(leave.created_at)
        items.append({
            "type": "leave", "title": f"Leave request {leave.start_date} to {leave.end_date} awaiting decision",
            "priority": min(100, 30 + age * 8), "age_days": age,
            "link_type": "leave_request", "link_id": leave.id,
        })
    return items


def _low_stock_items(db: Session, org_id: str, limit: int) -> list[dict]:
    products = db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.active.is_(True))).all()
    balances = dict(db.execute(
        select(InventoryBalance.product_id, InventoryBalance.quantity).where(
            InventoryBalance.organization_id == org_id)
    ).all())
    items = []
    for p in products:
        qty = balances.get(p.id, Decimal("0"))
        if qty <= p.reorder_level:
            deficit = p.reorder_level - qty
            items.append({
                "type": "low_stock", "title": f"{p.name} ({p.sku}) is at or below reorder level",
                "priority": min(100, 40 + float(deficit)), "age_days": None,
                "link_type": "product", "link_id": p.id,
            })
    items.sort(key=lambda i: i["priority"], reverse=True)
    return items[:limit]


def _overdue_receivable_items(db: Session, org_id: str, limit: int) -> list[dict]:
    from .timeutil import dhaka_today
    today = dhaka_today()
    per_customer: dict[str, list] = {}
    for party_id, moment, delta in db.execute(
        select(LedgerEntry.party_id, LedgerEntry.occurred_at, LedgerEntry.amount_delta).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
            LedgerEntry.party_type == "customer", LedgerEntry.party_id.is_not(None))
    ).all():
        per_customer.setdefault(party_id, []).append((moment, delta))
    customers = {c.id: c for c in db.scalars(select(Customer).where(
        Customer.organization_id == org_id, Customer.id.in_(list(per_customer))))}

    items = []
    for customer_id, entries in per_customer.items():
        balance = sum((d for _, d in entries), Decimal("0"))
        if balance <= 0 or customer_id not in customers:
            continue
        buckets, oldest = age_debts(entries, today)
        if oldest is not None and oldest >= 30:
            items.append({
                "type": "overdue_receivable",
                "title": f"{customers[customer_id].display_name or customers[customer_id].code} owes {balance} BDT ({oldest} days)",
                "priority": min(100, 30 + oldest), "age_days": oldest,
                "link_type": "customer", "link_id": customer_id,
            })
    items.sort(key=lambda i: i["priority"], reverse=True)
    return items[:limit]


@router.get("")
def mission_queue(membership: CurrentMembership, user: CurrentUser, db: Db, limit: int = Query(default=20, ge=1, le=100)):
    """Permission-aware: an item only appears if the caller's role could act on
    the thing it points to -- a cashier never sees a purchase approval."""
    org_id = membership.organization_id
    role = membership.role
    items: list[dict] = []

    if has_permission(role, "approvals:decide"):
        items += _approval_items(db, org_id)
    if has_permission(role, "tickets:read"):
        items += _ticket_items(db, org_id)
    if has_permission(role, "leave:decide"):
        items += _leave_items(db, org_id)
    if has_permission(role, "inventory:read"):
        items += _low_stock_items(db, org_id, limit)
    if has_permission(role, "ledger:read"):
        items += _overdue_receivable_items(db, org_id, limit)

    items.sort(key=lambda i: i["priority"], reverse=True)
    return {"as_of": datetime.now(timezone.utc).isoformat(), "items": items[:limit], "total_before_limit": len(items)}
