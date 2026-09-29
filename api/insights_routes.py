"""Owner-facing insight: the morning brief, alerts, the daily cash count, and
customer / supplier detail. Everything here is computed from the shop's own
records; no model, no guessing."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import CurrentMembership
from .batches import state_of
from .database import get_db
from .domain_models import (
    Batch, BatchStock, Branch, CashClose, Customer, Expense, InventoryBalance, LedgerEntry, Payment,
    Product, PurchaseOrder, PurchaseOrderItem, Recommendation, Refund, SalesOrder, SalesOrderItem,
    SalesReturn, StockMovement, Supplier,
)
from .permissions import has_permission, require_permission
from .timeutil import day_bounds, dhaka_today

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
ZERO = Decimal("0")
_dhaka_today = dhaka_today
_day_bounds = day_bounds


def _balances(db: Session, org_id: str, ledger_type: str) -> dict[str, Decimal]:
    rows = db.execute(
        select(LedgerEntry.party_id, func.sum(LedgerEntry.amount_delta))
        .where(LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == ledger_type)
        .group_by(LedgerEntry.party_id)
    ).all()
    return {party: Decimal(total) for party, total in rows if party and Decimal(total) > 0}


# ── morning brief and alerts ─────────────────────────────────────────────────

@router.get("/brief", tags=["insight"])
def morning_brief(membership: CurrentMembership, db: Db):
    """The five things an owner wants at 9 a.m.: yesterday, what to buy, what expires,
    who owes, and what is waiting. Sections the caller's role cannot see are left out."""
    require_permission(membership, "dashboard:read")
    org_id, role = membership.organization_id, membership.role
    today = _dhaka_today()
    y_start, y_end = _day_bounds(today - timedelta(days=1))
    w_start, _ = _day_bounds(today - timedelta(days=8))
    brief: dict = {"date": today.isoformat()}

    sold = db.execute(select(func.coalesce(func.sum(SalesOrder.total), 0), func.count(SalesOrder.id)).where(
        SalesOrder.organization_id == org_id, SalesOrder.sold_at >= y_start, SalesOrder.sold_at < y_end)).one()
    week = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.sold_at >= w_start, SalesOrder.sold_at < y_start))
    brief["yesterday"] = {"sales": sold[0], "orders": sold[1], "usual_daily_sales": Decimal(week or 0) / 7}

    if has_permission(role, "inventory:read"):
        rows = db.execute(
            select(Product, func.coalesce(func.sum(InventoryBalance.quantity), 0))
            .outerjoin(InventoryBalance, InventoryBalance.product_id == Product.id)
            .where(Product.organization_id == org_id, Product.active.is_(True))
            .group_by(Product.id)
        ).all()
        low = sorted(((p, Decimal(q)) for p, q in rows if Decimal(q) <= p.reorder_level), key=lambda x: x[1])
        brief["low_stock"] = {
            "count": len(low),
            "items": [{"product_id": p.id, "name": p.name, "quantity": q, "reorder_level": p.reorder_level} for p, q in low[:5]],
        }
        expiring = {"expired_units": ZERO, "within_30_units": ZERO, "at_risk_value": ZERO}
        shelf = db.execute(
            select(Batch, func.sum(BatchStock.quantity)).join(BatchStock, BatchStock.batch_id == Batch.id)
            .where(Batch.organization_id == org_id, BatchStock.quantity > 0, Batch.expiry_date.is_not(None))
            .group_by(Batch.id)
        ).all()
        for batch, qty in shelf:
            days = (batch.expiry_date - today).days
            if days < 0:
                expiring["expired_units"] += Decimal(qty)
            elif days <= 30:
                expiring["within_30_units"] += Decimal(qty)
            if days <= 90 and batch.unit_cost is not None:
                expiring["at_risk_value"] += Decimal(qty) * batch.unit_cost
        brief["expiry"] = expiring if shelf else None

    if has_permission(role, "ledger:read"):
        owed = _balances(db, org_id, "receivable")
        names = {c.id: (c.display_name or c.code) for c in db.scalars(select(Customer).where(
            Customer.organization_id == org_id, Customer.id.in_(list(owed) or [""])))}
        top = sorted(owed.items(), key=lambda x: -x[1])[:5]
        brief["dues"] = {
            "total": sum(owed.values(), ZERO), "customers": len(owed),
            "top": [{"customer_id": cid, "name": names.get(cid, "—"), "balance": amount} for cid, amount in top],
        }
        brief["we_owe"] = sum(_balances(db, org_id, "payable").values(), ZERO)

    if has_permission(role, "purchases:read"):
        brief["pending_purchases"] = db.scalar(select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.organization_id == org_id, PurchaseOrder.status.in_(["ordered", "partial"])))
    if has_permission(role, "bsmart:read"):
        decided = select(Recommendation.id).where(Recommendation.organization_id == org_id).join(
            Recommendation.decisions, isouter=False)
        brief["pending_recommendations"] = db.scalar(select(func.count(Recommendation.id)).where(
            Recommendation.organization_id == org_id, Recommendation.id.not_in(decided)))
    return brief


@router.get("/alerts", tags=["insight"])
def alerts(membership: CurrentMembership, db: Db):
    """What needs attention now, most urgent first. Only what the caller's role may see."""
    org_id, role = membership.organization_id, membership.role
    today = _dhaka_today()
    found: list[dict] = []

    def add(kind, severity, title, href, count=None):
        found.append({"kind": kind, "severity": severity, "title": title, "href": href, "count": count})

    if has_permission(role, "inventory:read"):
        rows = db.execute(
            select(Product, func.coalesce(func.sum(InventoryBalance.quantity), 0))
            .outerjoin(InventoryBalance, InventoryBalance.product_id == Product.id)
            .where(Product.organization_id == org_id, Product.active.is_(True)).group_by(Product.id)
        ).all()
        out = sum(1 for p, q in rows if Decimal(q) <= 0)
        low = sum(1 for p, q in rows if 0 < Decimal(q) <= p.reorder_level)
        if out:
            add("out_of_stock", "danger", f"{out}টি পণ্যের স্টক শেষ", "#/inventory", out)
        if low:
            add("low_stock", "warn", f"{low}টি পণ্যের স্টক কম", "#/inventory", low)
        expired = near = 0
        for batch, qty in db.execute(
            select(Batch, func.sum(BatchStock.quantity)).join(BatchStock, BatchStock.batch_id == Batch.id)
            .where(Batch.organization_id == org_id, BatchStock.quantity > 0).group_by(Batch.id)
        ).all():
            state = state_of(batch, today, 30)
            expired += state == "expired"
            near += state == "near_expiry"
        if expired:
            add("expired", "danger", f"{expired}টি ব্যাচের মেয়াদ শেষ — বিক্রি হবে না", "#/expiry", expired)
        if near:
            add("near_expiry", "warn", f"{near}টি ব্যাচের মেয়াদ ৩০ দিনের মধ্যে শেষ", "#/expiry", near)
    if has_permission(role, "ledger:read"):
        owed = _balances(db, org_id, "receivable")
        if owed:
            add("baki", "info", f"{len(owed)} জনের কাছে বাকি পাওনা আছে", "#/directory", len(owed))
    if has_permission(role, "purchases:read"):
        late = db.scalar(select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.organization_id == org_id, PurchaseOrder.status.in_(["ordered", "partial"]),
            PurchaseOrder.expected_at.is_not(None), PurchaseOrder.expected_at < datetime.now(timezone.utc)))
        if late:
            add("late_delivery", "warn", f"{late}টি অর্ডারের মাল আসার কথা ছিল, এখনো আসেনি", "#/purchases", late)
    order = {"danger": 0, "warn": 1, "info": 2}
    found.sort(key=lambda a: order[a["severity"]])
    return {"count": len(found), "alerts": found}


# ── daily cash count ─────────────────────────────────────────────────────────

def _cash_day(db: Session, org_id: str, branch_id: str, day: date) -> dict[str, Decimal]:
    start, end = _day_bounds(day)
    cash_sales = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(
        SalesOrder, SalesOrder.id == Payment.order_id).where(
        Payment.organization_id == org_id, Payment.method == "cash", Payment.status == "completed",
        SalesOrder.branch_id == branch_id, SalesOrder.sold_at >= start, SalesOrder.sold_at < end))
    baki_in = db.scalar(select(func.coalesce(func.sum(-LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
        LedgerEntry.reference_type == "customer_payment", LedgerEntry.payment_method == "cash",
        LedgerEntry.occurred_at >= start, LedgerEntry.occurred_at < end))
    expenses = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.organization_id == org_id, Expense.payment_method == "cash",
        (Expense.branch_id == branch_id) | Expense.branch_id.is_(None),
        Expense.incurred_at >= start, Expense.incurred_at < end))
    suppliers = db.scalar(select(func.coalesce(func.sum(-LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "payable",
        LedgerEntry.reference_type == "supplier_payment", LedgerEntry.payment_method == "cash",
        LedgerEntry.occurred_at >= start, LedgerEntry.occurred_at < end))
    refunds = db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).join(
        SalesReturn, SalesReturn.id == Refund.sales_return_id).where(
        Refund.organization_id == org_id, Refund.method == "cash", SalesReturn.branch_id == branch_id,
        Refund.refunded_at >= start, Refund.refunded_at < end))
    return {
        "cash_sales": Decimal(cash_sales), "baki_collected": Decimal(baki_in), "expenses": Decimal(expenses),
        "supplier_payments": Decimal(suppliers), "refunds": Decimal(refunds),
    }


def _expected(opening: Decimal, parts: dict[str, Decimal]) -> Decimal:
    return opening + parts["cash_sales"] + parts["baki_collected"] - parts["expenses"] - parts["supplier_payments"] - parts["refunds"]


def _branch(db: Session, org_id: str, branch_id: str) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


@router.get("/cash/day", tags=["cash"])
def cash_day(membership: CurrentMembership, db: Db, branch_id: str, day: date | None = None):
    """What the books say the drawer should hold at the end of ``day``, and whether it was closed."""
    require_permission(membership, "cash:read")
    org_id = membership.organization_id
    _branch(db, org_id, branch_id)
    day = day or _dhaka_today()
    parts = _cash_day(db, org_id, branch_id, day)
    closed = db.scalar(select(CashClose).where(
        CashClose.organization_id == org_id, CashClose.branch_id == branch_id, CashClose.business_date == day))
    previous = db.scalar(select(CashClose).where(
        CashClose.organization_id == org_id, CashClose.branch_id == branch_id, CashClose.business_date < day,
    ).order_by(CashClose.business_date.desc()))
    suggested_opening = previous.counted_cash if previous else ZERO
    opening = closed.opening_cash if closed else suggested_opening
    return {
        "date": day.isoformat(), "branch_id": branch_id, **parts,
        "opening_cash": opening, "suggested_opening": suggested_opening, "expected_cash": _expected(opening, parts),
        "closed": None if closed is None else {
            "id": closed.id, "counted_cash": closed.counted_cash, "variance": closed.variance,
            "note": closed.note, "closed_at": closed.created_at.isoformat(),
        },
    }


class CashCloseIn(BaseModel):
    branch_id: str
    business_date: date
    opening_cash: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    counted_cash: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    note: str | None = Field(default=None, max_length=300)


@router.post("/cash/close", tags=["cash"])
def cash_close(body: CashCloseIn, membership: CurrentMembership, db: Db):
    """Close the day: record the count next to what the books expected. One close per branch per day."""
    require_permission(membership, "cash:close")
    org_id = membership.organization_id
    _branch(db, org_id, body.branch_id)
    if body.business_date > _dhaka_today():
        raise HTTPException(status_code=422, detail="Cannot close a day in the future")
    parts = _cash_day(db, org_id, body.branch_id, body.business_date)
    expected = _expected(body.opening_cash, parts)
    variance = body.counted_cash - expected
    if variance != 0 and not (body.note and body.note.strip()):
        raise HTTPException(status_code=422, detail="A note is required when the count does not match the books")
    row = CashClose(
        organization_id=org_id, branch_id=body.branch_id, business_date=body.business_date,
        opening_cash=body.opening_cash, expected_cash=expected, counted_cash=body.counted_cash,
        variance=variance, note=body.note, closed_by=membership.user_id,
        breakdown_json=json.dumps({k: str(v) for k, v in parts.items()}),
    )
    db.add(row)
    try:
        db.flush()
        record_audit(db, membership, "cash.closed", "cash_close", row.id,
                     date=body.business_date.isoformat(), expected=expected, counted=body.counted_cash, variance=variance)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This day is already closed") from exc
    return {"id": row.id, "expected_cash": expected, "counted_cash": body.counted_cash, "variance": variance}


@router.get("/cash/closes", tags=["cash"])
def cash_closes(membership: CurrentMembership, db: Db, branch_id: str | None = None, limit: int = Query(default=30, ge=1, le=200)):
    require_permission(membership, "cash:read")
    statement = select(CashClose, Branch.name).join(Branch, Branch.id == CashClose.branch_id).where(
        CashClose.organization_id == membership.organization_id)
    if branch_id:
        statement = statement.where(CashClose.branch_id == branch_id)
    rows = db.execute(statement.order_by(CashClose.business_date.desc()).limit(limit)).all()
    return [{
        "id": c.id, "date": c.business_date.isoformat(), "branch": name, "opening_cash": c.opening_cash,
        "expected_cash": c.expected_cash, "counted_cash": c.counted_cash, "variance": c.variance, "note": c.note,
    } for c, name in rows]


# ── customer and supplier detail ─────────────────────────────────────────────

@router.get("/customers/{customer_id}/summary", tags=["customers-app"])
def customer_summary(customer_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "customers:read")
    org_id = membership.organization_id
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == org_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders, spent, last = db.execute(select(
        func.count(SalesOrder.id), func.coalesce(func.sum(SalesOrder.total), 0), func.max(SalesOrder.sold_at)
    ).where(SalesOrder.organization_id == org_id, SalesOrder.customer_id == customer_id)).one()
    top = db.execute(
        select(Product.name, func.sum(SalesOrderItem.quantity).label("qty"))
        .join(SalesOrderItem, SalesOrderItem.product_id == Product.id)
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(SalesOrder.organization_id == org_id, SalesOrder.customer_id == customer_id)
        .group_by(Product.id).order_by(func.sum(SalesOrderItem.quantity).desc()).limit(5)
    ).all()
    recent = db.scalars(select(SalesOrder).where(
        SalesOrder.organization_id == org_id, SalesOrder.customer_id == customer_id,
    ).order_by(SalesOrder.sold_at.desc()).limit(8)).all()
    due = Decimal(db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable", LedgerEntry.party_id == customer_id)))
    days_since = (datetime.now(timezone.utc) - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))).days if last else None
    return {
        "customer_id": customer.id, "name": customer.display_name or customer.code, "code": customer.code,
        "marketing_consent": customer.marketing_consent, "orders": orders, "total_spent": spent,
        "average_order": (Decimal(spent) / orders) if orders else None, "last_purchase_at": last.isoformat() if last else None,
        "days_since_last_purchase": days_since, "due": max(due, ZERO),
        "top_products": [{"name": n, "quantity": q} for n, q in top],
        "recent": [{"invoice": o.invoice_number, "sold_at": o.sold_at.isoformat(), "total": o.total} for o in recent],
    }


@router.get("/suppliers/{supplier_id}/stats", tags=["suppliers"])
def supplier_stats(supplier_id: str, membership: CurrentMembership, db: Db):
    """How the supplier actually performs: delivery time, punctuality, and price movement."""
    require_permission(membership, "suppliers:read")
    org_id = membership.organization_id
    supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == org_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    orders = db.scalars(select(PurchaseOrder).where(
        PurchaseOrder.organization_id == org_id, PurchaseOrder.supplier_id == supplier_id
    ).order_by(PurchaseOrder.ordered_at)).all()
    first_receipt = dict(db.execute(
        select(StockMovement.reference_id, func.min(StockMovement.occurred_at)).where(
            StockMovement.organization_id == org_id, StockMovement.movement_type == "purchase_receipt",
            StockMovement.reference_id.in_([o.id for o in orders] or [""])).group_by(StockMovement.reference_id)).all())

    def aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    lead_days, on_time, with_promise = [], 0, 0
    for order in orders:
        got = first_receipt.get(order.id)
        if got is None:
            continue
        lead_days.append(max(0.0, (aware(got) - aware(order.ordered_at)).total_seconds() / 86400))
        if order.expected_at:
            with_promise += 1
            on_time += aware(got) <= aware(order.expected_at)
    prices: dict[str, list] = {}
    for order in orders:
        for item, product in db.execute(select(PurchaseOrderItem, Product).join(Product, Product.id == PurchaseOrderItem.product_id).where(
                PurchaseOrderItem.purchase_order_id == order.id)).all():
            prices.setdefault(product.name, []).append(item.unit_cost)
    movement = []
    for name, costs in prices.items():
        last, before = costs[-1], costs[-2] if len(costs) > 1 else None
        movement.append({
            "product": name, "last_cost": last, "previous_cost": before,
            "change_pct": float((last - before) / before * 100) if before else None,
        })
    movement.sort(key=lambda m: -abs(m["change_pct"] or 0))
    owe = Decimal(db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "payable", LedgerEntry.party_id == supplier_id)))
    return {
        "supplier_id": supplier.id, "name": supplier.name, "declared_lead_days": supplier.typical_lead_days,
        "orders": len(orders), "delivered_orders": len(lead_days),
        "average_lead_days": round(sum(lead_days) / len(lead_days), 1) if lead_days else None,
        "on_time_rate": round(on_time / with_promise, 3) if with_promise else None,
        "total_purchased": sum((o.total for o in orders), ZERO), "we_owe": max(owe, ZERO),
        "price_movement": movement[:8],
    }
