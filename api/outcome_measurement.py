"""Measure a B-SMART recommendation's outcome from the ledger itself, instead
of asking the owner to type numbers in by hand.

Only meaningful for a *live* recommendation (`api/bsmart_live.py`): its
`target_sku`/`division` are a real `Product.sku` and `Branch.name` in this
organization's own schema, so `StockMovement`/`SalesOrderItem`/`Batch` rows
actually exist to measure from. A research-imported recommendation's
`target_sku`/`division` are the thesis dataset's own product name and
geographic division -- they don't correspond to anything in this tenant's
database, so auto-measurement is refused for those rather than silently
producing nonsense numbers against the wrong branch/product.

Deliberately narrow: only the fields that can be computed honestly from
data this schema actually records.
  - stockout_days_before/after: replays the branch/product's own
    StockMovement ledger day by day and counts days the running balance was
    at or below zero, in the window before and after the decision.
  - realised_quantity: units of that SKU actually sold in the window after
    the decision (SalesOrderItem, real).
  - expired_value_bdt (expiry actions only): value of batches that reached
    their expiry date within the window and are still sitting in stock --
    real stock that was never sold before it expired, not an estimate.
  - customer_responded (retention actions only): did the customer make any
    purchase in the window after the decision.
Holding-cost change and a pre-decision predicted quantity are left
unmeasured (``None``) here -- this schema has no reliable way to reconstruct
historical holding cost, and inventing one would be exactly the kind of
fabricated number this codebase's own rules forbid.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .domain_models import Batch, BatchStock, Branch, Customer, Product, SalesOrder, SalesOrderItem, StockMovement


class CannotMeasure(Exception):
    """Raised with a human-readable reason when auto-measurement isn't possible."""


def _resolve_product_and_branch(db: Session, org_id: str, sku: str | None, division: str | None) -> tuple[str, str]:
    if not sku or not division:
        raise CannotMeasure("এই সুপারিশে পণ্য বা শাখার তথ্য নেই।")
    product_id = db.scalar(select(Product.id).where(Product.organization_id == org_id, Product.sku == sku))
    branch_id = db.scalar(select(Branch.id).where(Branch.organization_id == org_id, Branch.name == division))
    if not product_id or not branch_id:
        raise CannotMeasure("এই পণ্য বা শাখা আর এই ব্যবসায় খুঁজে পাওয়া যায়নি (হয়তো মুছে ফেলা হয়েছে)।")
    return product_id, branch_id


def _stockout_days(db: Session, org_id: str, branch_id: str, product_id: str, window_start: datetime, window_end: datetime) -> int:
    opening_balance = float(db.scalar(
        select(func.coalesce(func.sum(StockMovement.quantity_delta), 0)).where(
            StockMovement.organization_id == org_id, StockMovement.branch_id == branch_id,
            StockMovement.product_id == product_id, StockMovement.occurred_at < window_start,
        )
    ) or 0)

    rows = db.execute(
        select(StockMovement.occurred_at, StockMovement.quantity_delta).where(
            StockMovement.organization_id == org_id, StockMovement.branch_id == branch_id,
            StockMovement.product_id == product_id,
            StockMovement.occurred_at >= window_start, StockMovement.occurred_at < window_end,
        )
    ).all()
    by_day: dict[date, float] = {}
    for occurred_at, delta in rows:
        day = occurred_at.date()
        by_day[day] = by_day.get(day, 0.0) + float(delta)

    balance = opening_balance
    stockout_days = 0
    day = window_start.date()
    end_day = window_end.date()
    while day < end_day:
        balance += by_day.get(day, 0.0)
        if balance <= 0:
            stockout_days += 1
        day += timedelta(days=1)
    return stockout_days


def _realised_quantity(db: Session, org_id: str, branch_id: str, product_id: str, window_start: datetime, window_end: datetime) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(SalesOrderItem.quantity), 0))
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(
            SalesOrder.organization_id == org_id, SalesOrder.branch_id == branch_id,
            SalesOrderItem.product_id == product_id,
            SalesOrder.sold_at >= window_start, SalesOrder.sold_at < window_end,
        )
    )
    return int(total or 0)


def _expired_value(db: Session, org_id: str, product_id: str, window_start: datetime, window_end: datetime) -> Decimal:
    rows = db.execute(
        select(Batch, BatchStock).join(BatchStock, BatchStock.batch_id == Batch.id).where(
            Batch.organization_id == org_id, Batch.product_id == product_id,
            Batch.expiry_date.is_not(None),
            Batch.expiry_date >= window_start.date(), Batch.expiry_date < window_end.date(),
            BatchStock.quantity > 0,
        )
    ).all()
    total = Decimal("0")
    for batch, stock in rows:
        if batch.unit_cost is not None:
            total += stock.quantity * batch.unit_cost
    return total.quantize(Decimal("0.01"))


def _customer_responded(db: Session, org_id: str, customer_id: str, window_start: datetime, window_end: datetime) -> bool:
    hit = db.scalar(
        select(SalesOrder.id).where(
            SalesOrder.organization_id == org_id, SalesOrder.customer_id == customer_id,
            SalesOrder.sold_at >= window_start, SalesOrder.sold_at < window_end,
        ).limit(1)
    )
    return hit is not None


def measure(db: Session, org_id: str, reco, decided_at: datetime, window_days: int) -> dict:
    """Compute what can honestly be computed for one recommendation.

    Returns a dict shaped like ``OutcomeIn`` (bsmart_routes.py); any field
    this function cannot compute is left out entirely rather than guessed.
    """
    window_start = decided_at
    window_end = decided_at + timedelta(days=window_days)
    before_start = decided_at - timedelta(days=window_days)
    result: dict = {"observation_window_days": window_days}

    if reco.action_type == "reorder":
        product_id, branch_id = _resolve_product_and_branch(db, org_id, reco.target_sku, reco.division)
        result["stockout_days_before"] = _stockout_days(db, org_id, branch_id, product_id, before_start, window_start)
        result["stockout_days_after"] = _stockout_days(db, org_id, branch_id, product_id, window_start, window_end)
        result["realised_quantity"] = _realised_quantity(db, org_id, branch_id, product_id, window_start, window_end)
        result["predicted_quantity"] = reco.quantity
    elif reco.action_type == "expiry":
        product_id, _branch_id = _resolve_product_and_branch(db, org_id, reco.target_sku, reco.division)
        result["expired_value_bdt"] = float(_expired_value(db, org_id, product_id, window_start, window_end))
    elif reco.action_type == "retention":
        if not reco.target_customer_id:
            raise CannotMeasure("এই সুপারিশে কাস্টমারের তথ্য নেই।")
        customer_exists = db.scalar(select(Customer.id).where(
            Customer.id == reco.target_customer_id, Customer.organization_id == org_id))
        if not customer_exists:
            raise CannotMeasure("এই কাস্টমার আর এই ব্যবসায় খুঁজে পাওয়া যায়নি।")
        result["customer_responded"] = _customer_responded(db, org_id, reco.target_customer_id, window_start, window_end)
    else:
        raise CannotMeasure(f"অজানা ধরনের সুপারিশ: {reco.action_type}")

    return result
