"""Advanced, still-arithmetic insight: the Cash-Locked Meter, ABC-XYZ product
classification with a dead-stock flag, and a supplier price-watch.

Nothing here is a model. Every number is computed from the shop's own ledger,
sales and purchase history, with an explicit "not enough data" instead of a
guess wherever the arithmetic would otherwise be unstable (few purchases, a
brand-new product, a product that has never sold).
"""

from __future__ import annotations

import statistics
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .batches import state_of
from .database import get_db
from .domain_models import (
    Batch, BatchStock, InventoryBalance, LedgerEntry, Product, PurchaseOrder, PurchaseOrderItem,
    SalesOrder, SalesOrderItem, Supplier,
)
from .permissions import require_permission
from .receivables_routes import age_debts
from .timeutil import dhaka_today

router = APIRouter(prefix="/api/app/insights")
Db = Annotated[Session, Depends(get_db)]
ZERO = Decimal("0")
DEAD_STOCK_DAYS = 60          # no sale in this long, with stock on hand, counts as dead
OVERDUE_DAYS = 60             # baki older than this is "locked", not just ordinary credit


def _last_sale_dates(db: Session, org_id: str) -> dict[str, str]:
    rows = db.execute(
        select(SalesOrderItem.product_id, func.max(SalesOrder.sold_at))
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(SalesOrderItem.organization_id == org_id)
        .group_by(SalesOrderItem.product_id)
    ).all()
    return {pid: last for pid, last in rows}


def _on_hand(db: Session, org_id: str) -> dict[str, Decimal]:
    return dict(db.execute(
        select(InventoryBalance.product_id, func.sum(InventoryBalance.quantity))
        .where(InventoryBalance.organization_id == org_id).group_by(InventoryBalance.product_id)
    ).all())


@router.get("/cash-locked", tags=["insight"])
def cash_locked(membership: CurrentMembership, db: Db):
    """One BDT number for money that is not working for the shop right now:
    stock that has not sold in a while, stock at risk of expiring, and baki
    that has gone well past a normal credit period."""
    require_permission(membership, "inventory:read")
    require_permission(membership, "ledger:read")
    org_id = membership.organization_id
    today = dhaka_today()
    cutoff = today - timedelta(days=DEAD_STOCK_DAYS)

    last_sale = _last_sale_dates(db, org_id)
    on_hand = _on_hand(db, org_id)
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.active.is_(True)))}

    dead_value, dead_items = ZERO, []
    for product_id, qty in on_hand.items():
        product = products.get(product_id)
        qty = Decimal(qty or 0)
        if product is None or qty <= 0:
            continue
        last = last_sale.get(product_id)
        stale = last is None or last.date() < cutoff
        # A never-sold product only counts once it has existed long enough to judge —
        # a new arrival is not "dead", it just hasn't had a chance yet.
        if last is None and product.created_at.date() >= cutoff:
            stale = False
        if not stale:
            continue
        value = qty * product.cost_price
        dead_value += value
        dead_items.append({
            "product_id": product_id, "sku": product.sku, "name": product.name,
            "quantity": qty, "value": value,
            "days_since_sale": (today - last.date()).days if last else None,
        })
    dead_items.sort(key=lambda i: -i["value"])

    expiry_value, expired_value, expiry_units = ZERO, ZERO, ZERO
    for batch, qty in db.execute(
        select(Batch, func.sum(BatchStock.quantity)).join(BatchStock, BatchStock.batch_id == Batch.id)
        .where(Batch.organization_id == org_id, BatchStock.quantity > 0, Batch.expiry_date.is_not(None))
        .group_by(Batch.id)
    ).all():
        qty = Decimal(qty or 0)
        state = state_of(batch, today)
        if state not in ("expired", "near_expiry") or qty <= 0:
            continue
        product = products.get(batch.product_id)
        cost = batch.unit_cost if batch.unit_cost is not None else (product.cost_price if product else ZERO)
        value = qty * cost
        expiry_value += value
        expiry_units += qty
        if state == "expired":
            expired_value += value

    entries: dict[str, list] = {}
    for party_id, moment, delta in db.execute(
        select(LedgerEntry.party_id, LedgerEntry.occurred_at, LedgerEntry.amount_delta).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
            LedgerEntry.party_type == "customer", LedgerEntry.party_id.is_not(None))
    ).all():
        entries.setdefault(party_id, []).append((moment, delta))
    overdue_baki, overdue_customers = ZERO, 0
    for customer_entries in entries.values():
        buckets, _oldest = age_debts(customer_entries, today)
        stuck = sum((v for name, v in buckets.items() if name != "d0_30"), ZERO)
        if stuck > 0:
            overdue_baki += stuck
            overdue_customers += 1

    total = dead_value + expiry_value + overdue_baki
    return {
        "as_of": today, "total": total,
        "dead_stock": {"value": dead_value, "products": len(dead_items), "top": dead_items[:10]},
        "near_expiry": {"value": expiry_value, "expired_value": expired_value, "units": expiry_units},
        "overdue_baki": {"value": overdue_baki, "customers": overdue_customers, "over_days": OVERDUE_DAYS},
    }


@router.get("/abc-xyz", tags=["insight"])
def abc_xyz(membership: CurrentMembership, db: Db, days: int = Query(default=90, ge=28, le=365)):
    """ABC by revenue share (A = top 80% cumulative, B = next 15%, C = last 5%),
    XYZ by how steady weekly demand has been (X steady, Y variable, Z erratic),
    each product also flagged dead stock or not. A product with fewer than
    3 weeks of sales in the window gets no XYZ class — not enough to judge."""
    require_permission(membership, "inventory:read")
    require_permission(membership, "sales:read")
    org_id = membership.organization_id
    today = dhaka_today()
    since = today - timedelta(days=days)

    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.active.is_(True)))}
    on_hand = _on_hand(db, org_id)
    last_sale = _last_sale_dates(db, org_id)
    dead_cutoff = today - timedelta(days=DEAD_STOCK_DAYS)

    revenue = dict(db.execute(
        select(SalesOrderItem.product_id, func.sum(SalesOrderItem.line_total))
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(SalesOrderItem.organization_id == org_id, SalesOrder.sold_at >= since)
        .group_by(SalesOrderItem.product_id)
    ).all())
    weekly: dict[str, dict[int, Decimal]] = {}
    for product_id, sold_at, qty in db.execute(
        select(SalesOrderItem.product_id, SalesOrder.sold_at, SalesOrderItem.quantity)
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(SalesOrderItem.organization_id == org_id, SalesOrder.sold_at >= since)
    ).all():
        week = (sold_at.date() - since).days // 7
        weekly.setdefault(product_id, {})[week] = weekly.setdefault(product_id, {}).get(week, ZERO) + qty

    total_revenue = sum(revenue.values(), ZERO)
    ranked = sorted(revenue.items(), key=lambda x: -x[1])
    cumulative = ZERO
    abc_class: dict[str, str] = {}
    for product_id, value in ranked:
        # Classified by how much revenue ranked *above* it: the item that first crosses
        # a threshold still belongs to the band it crossed into, not the one after —
        # otherwise a single dominant seller would wrongly fall out of class A.
        share_before = float(cumulative / total_revenue) if total_revenue > 0 else 0
        abc_class[product_id] = "A" if share_before < 0.80 else ("B" if share_before < 0.95 else "C")
        cumulative += value

    rows = []
    for product_id, product in products.items():
        qty_on_hand = Decimal(on_hand.get(product_id, 0) or 0)
        last = last_sale.get(product_id)
        stale = (last is None or last.date() < dead_cutoff) and not (
            last is None and product.created_at.date() >= dead_cutoff)
        weeks = list(weekly.get(product_id, {}).values())
        xyz = None
        if len(weeks) >= 3:
            mean = statistics.fmean(float(w) for w in weeks)
            if mean > 0:
                cv = statistics.pstdev(float(w) for w in weeks) / mean
                xyz = "X" if cv <= 0.5 else ("Y" if cv <= 1.0 else "Z")
        rows.append({
            "product_id": product_id, "sku": product.sku, "name": product.name,
            "revenue": revenue.get(product_id, ZERO),
            "revenue_share": float(revenue.get(product_id, ZERO) / total_revenue) if total_revenue > 0 else 0,
            "abc": abc_class.get(product_id),   # None = no sales in the window at all
            "xyz": xyz,
            "on_hand": qty_on_hand, "stock_value": qty_on_hand * product.cost_price,
            "dead_stock": bool(stale and qty_on_hand > 0),
        })
    rows.sort(key=lambda r: -r["revenue"])
    return {"days": days, "as_of": today, "items": rows}


@router.get("/price-watch", tags=["insight"])
def price_watch(membership: CurrentMembership, db: Db, threshold: float = Query(default=0.05, ge=0, le=1)):
    """Products whose purchase price moved between the last two receipts from the
    same supplier, by at least ``threshold`` (default 5%). Needs at least two
    purchases from that supplier to say anything — one price is not a trend."""
    require_permission(membership, "purchases:read")
    org_id = membership.organization_id
    rows = db.execute(
        select(PurchaseOrderItem.product_id, PurchaseOrder.supplier_id, PurchaseOrder.ordered_at, PurchaseOrderItem.unit_cost)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(PurchaseOrder.organization_id == org_id)
        .order_by(PurchaseOrderItem.product_id, PurchaseOrder.supplier_id, PurchaseOrder.ordered_at)
    ).all()
    products = {p.id: p for p in db.scalars(select(Product).where(Product.organization_id == org_id))}
    suppliers = {s.id: s for s in db.scalars(select(Supplier).where(Supplier.organization_id == org_id))}

    history: dict[tuple[str, str], list] = {}
    for product_id, supplier_id, ordered_at, unit_cost in rows:
        history.setdefault((product_id, supplier_id), []).append((ordered_at, unit_cost))

    changes = []
    for (product_id, supplier_id), points in history.items():
        if len(points) < 2:
            continue
        previous, latest = points[-2][1], points[-1][1]
        if previous <= 0:
            continue
        change = float((latest - previous) / previous)
        if abs(change) < threshold:
            continue
        product, supplier = products.get(product_id), suppliers.get(supplier_id)
        if product is None or supplier is None:
            continue
        changes.append({
            "product_id": product_id, "sku": product.sku, "name": product.name,
            "supplier_id": supplier_id, "supplier_name": supplier.name,
            "previous_cost": previous, "latest_cost": latest, "change": change,
            "since": points[-1][0],
        })
    changes.sort(key=lambda c: -abs(c["change"]))
    return {"threshold": threshold, "items": changes}
