"""Business Health Score (product plan Idea 2): five explainable 0-100 scores,
never a single vanity number. Each score states its formula, its data window,
and returns ``null`` -- not a guessed number -- when there isn't enough data
to compute it honestly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .database import get_db
from .domain_models import (
    ApprovalRequest, AuditLog, CashierShift, Customer, InventoryBalance, LedgerEntry, Product, SalesOrder,
)
from .permissions import require_permission

router = APIRouter(prefix="/api/app/health-score", tags=["insights"])
Db = Annotated[Session, Depends(get_db)]

WINDOW_DAYS = 30
RISK_ACTIONS = ("sale.discount_override", "refund.override", "sale.voided", "inventory.adjusted")


def _score(label: str, value: float | None, formula: str, window_days: int = WINDOW_DAYS) -> dict:
    return {
        "label": label,
        "score": None if value is None else round(max(0.0, min(100.0, value)), 1),
        "formula": formula,
        "window_days": window_days,
        "insufficient_data": value is None,
    }


def _cash_health(db: Session, org_id: str, since: datetime) -> dict:
    shifts = db.scalars(select(CashierShift).where(
        CashierShift.organization_id == org_id, CashierShift.status == "closed",
        CashierShift.closed_at >= since, CashierShift.variance.is_not(None),
    )).all()
    if not shifts:
        return _score("Cash Health", None, "100 - avg(|variance| / counted_cash) x 500, over closed shifts")
    ratios = [
        abs(s.variance) / s.counted_cash for s in shifts
        if s.counted_cash and s.counted_cash > 0
    ]
    if not ratios:
        return _score("Cash Health", None, "100 - avg(|variance| / counted_cash) x 500, over closed shifts")
    avg_ratio = sum(ratios) / len(ratios)
    return _score("Cash Health", 100 - float(avg_ratio) * 500,
                 "100 - avg(|variance| / counted_cash) x 500, over closed shifts")


def _stock_health(db: Session, org_id: str) -> dict:
    products = db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.active.is_(True))).all()
    if not products:
        return _score("Stock Health", None, "% of active products at or above their reorder level", window_days=0)
    balances = dict(db.execute(
        select(InventoryBalance.product_id, func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(InventoryBalance.organization_id == org_id)
        .group_by(InventoryBalance.product_id)
    ).all())
    healthy = sum(1 for p in products if balances.get(p.id, Decimal("0")) > p.reorder_level)
    return _score("Stock Health", healthy / len(products) * 100,
                 "% of active products at or above their reorder level", window_days=0)


def _sales_health(db: Session, org_id: str, since: datetime) -> dict:
    prior_since = since - timedelta(days=WINDOW_DAYS)
    this_period = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.sold_at >= since, SalesOrder.status != "voided"))
    prior_period = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.sold_at >= prior_since, SalesOrder.sold_at < since,
        SalesOrder.status != "voided"))
    this_period, prior_period = Decimal(this_period), Decimal(prior_period)
    if this_period == 0 and prior_period == 0:
        return _score("Sales Health", None, "100 + growth% vs the prior equal period, clamped 0-100")
    if prior_period == 0:
        return _score("Sales Health", 100.0, "100 + growth% vs the prior equal period, clamped 0-100")
    growth = float((this_period - prior_period) / prior_period)
    return _score("Sales Health", 100 + growth * 100, "100 + growth% vs the prior equal period, clamped 0-100")


def _customer_health(db: Session, org_id: str) -> dict:
    has_customers = db.scalar(select(Customer.id).where(Customer.organization_id == org_id).limit(1))
    if has_customers is None:
        return _score("Customer Health", None, "100 x (1 - overdue receivable / total receivable)", window_days=0)
    rows = db.execute(
        select(LedgerEntry.occurred_at, LedgerEntry.amount_delta).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
            LedgerEntry.party_type == "customer",
        )
    ).all()
    total = sum((d for _, d in rows), Decimal("0"))
    if total <= 0:
        return _score("Customer Health", 100.0, "100 x (1 - overdue receivable / total receivable)", window_days=0)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    def _aware(moment: datetime) -> datetime:
        return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)

    overdue = sum((d for moment, d in rows if d > 0 and _aware(moment) < cutoff), Decimal("0"))
    return _score("Customer Health", float(1 - min(Decimal("1"), overdue / total)) * 100,
                 "100 x (1 - overdue receivable / total receivable)", window_days=0)


def _control_health(db: Session, org_id: str, since: datetime) -> dict:
    exceptions = db.scalar(select(func.count(AuditLog.id)).where(
        AuditLog.organization_id == org_id, AuditLog.action.in_(RISK_ACTIONS), AuditLog.created_at >= since))
    pending_approvals = db.scalar(select(func.count(ApprovalRequest.id)).where(
        ApprovalRequest.organization_id == org_id, ApprovalRequest.status == "pending"))
    return _score("Control Health", 100 - (exceptions or 0) * 5 - (pending_approvals or 0) * 3,
                 "100 - (risk-flagged actions x 5) - (pending approvals x 3)")


@router.get("")
def health_score(membership: CurrentMembership, db: Db):
    require_permission(membership, "dashboard:read")
    org_id = membership.organization_id
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)

    scores = {
        "cash": _cash_health(db, org_id, since),
        "stock": _stock_health(db, org_id),
        "sales": _sales_health(db, org_id, since),
        "customer": _customer_health(db, org_id),
        "control": _control_health(db, org_id, since),
    }
    available = [s["score"] for s in scores.values() if s["score"] is not None]
    overall = round(sum(available) / len(available), 1) if available else None
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "overall_insufficient_data": overall is None,
        "scores": scores,
    }
