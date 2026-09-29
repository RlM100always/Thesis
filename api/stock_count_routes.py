"""Stock take (cycle count): snapshot what the system thinks is on the shelf,
enter what is actually there, apply the difference as one reviewed batch of
adjustments instead of many silent one-off corrections.

Expiry-tracked products are out of scope (see `StockCount`'s docstring) — a
variance there needs a batch to attribute it to, which "মেয়াদ ও ব্যাচ" already
owns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounting import Line, post_journal
from .audit import record_audit
from .auth import CurrentMembership
from .batches import balance_row
from .database import get_db
from .domain_models import Branch, InventoryBalance, Product, StockCount, StockCountLine, StockMovement, User
from .permissions import require_permission

router = APIRouter(prefix="/api/app/inventory/stock-counts")
Db = Annotated[Session, Depends(get_db)]
ZERO = Decimal("0")


def _view(count: StockCount, lines: list[StockCountLine], products: dict[str, Product], starter: str | None) -> dict:
    return {
        "id": count.id, "branch_id": count.branch_id, "status": count.status, "note": count.note,
        "started_by": starter, "started_at": count.started_at, "completed_at": count.completed_at,
        "lines": [{
            "id": line.id, "product_id": line.product_id, "sku": products[line.product_id].sku,
            "name": products[line.product_id].name, "unit": products[line.product_id].unit,
            "system_qty": line.system_qty, "counted_qty": line.counted_qty,
            "variance": (line.counted_qty - line.system_qty) if line.counted_qty is not None else None,
        } for line in lines],
    }


@router.post("", tags=["inventory"])
def start_count(body: dict, membership: CurrentMembership, db: Db):
    require_permission(membership, "inventory:adjust")
    org_id = membership.organization_id
    branch_id = body.get("branch_id")
    branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    if db.scalar(select(StockCount.id).where(
        StockCount.organization_id == org_id, StockCount.branch_id == branch_id, StockCount.status == "open")):
        raise HTTPException(status_code=409, detail="This branch already has a stock count in progress")

    products = list(db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.active.is_(True), Product.track_expiry.is_(False))))
    if not products:
        raise HTTPException(status_code=422, detail="No non-expiry-tracked products to count")
    balances = dict(db.execute(select(InventoryBalance.product_id, InventoryBalance.quantity).where(
        InventoryBalance.organization_id == org_id, InventoryBalance.branch_id == branch_id)).all())

    count = StockCount(
        organization_id=org_id, branch_id=branch_id, note=(body.get("note") or None),
        started_by_user_id=membership.user_id, started_at=datetime.now(timezone.utc),
    )
    db.add(count)
    db.flush()
    lines = []
    for product in products:
        line = StockCountLine(
            organization_id=org_id, stock_count_id=count.id, product_id=product.id,
            system_qty=Decimal(balances.get(product.id, 0) or 0),
        )
        db.add(line)
        lines.append(line)
    record_audit(db, membership, "stock_count.started", "stock_count", count.id, branch_id=branch_id, products=len(lines))
    db.commit()
    starter = db.get(User, membership.user_id)
    return _view(count, lines, {p.id: p for p in products}, starter.display_name if starter else None)


@router.get("", tags=["inventory"])
def list_counts(
    membership: CurrentMembership, db: Db, branch_id: str | None = None,
    status: str | None = None, limit: int = Query(default=50, ge=1, le=200),
):
    require_permission(membership, "inventory:read")
    org_id = membership.organization_id
    statement = select(StockCount).where(StockCount.organization_id == org_id)
    if branch_id:
        statement = statement.where(StockCount.branch_id == branch_id)
    if status:
        statement = statement.where(StockCount.status == status)
    counts = list(db.scalars(statement.order_by(StockCount.started_at.desc()).limit(limit)))
    starters = {u.id: u.display_name for u in db.scalars(select(User).where(
        User.id.in_({c.started_by_user_id for c in counts} or {""})))}
    result = []
    for count in counts:
        line_rows = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == count.id)))
        counted = [ln for ln in line_rows if ln.counted_qty is not None]
        varied = [ln for ln in counted if ln.counted_qty != ln.system_qty]
        result.append({
            "id": count.id, "branch_id": count.branch_id, "status": count.status, "note": count.note,
            "started_by": starters.get(count.started_by_user_id), "started_at": count.started_at,
            "completed_at": count.completed_at, "products": len(line_rows),
            "counted": len(counted), "with_variance": len(varied),
        })
    return result


@router.get("/{count_id}", tags=["inventory"])
def get_count(count_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "inventory:read")
    org_id = membership.organization_id
    count = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.organization_id == org_id))
    if count is None:
        raise HTTPException(status_code=404, detail="Stock count not found")
    lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == count.id)))
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.id.in_({ln.product_id for ln in lines})))}
    starter = db.get(User, count.started_by_user_id)
    return _view(count, lines, products, starter.display_name if starter else None)


class CountEntry(BaseModel):
    counted_qty: Decimal = Field(ge=0, max_digits=14, decimal_places=3)


@router.patch("/{count_id}/lines/{line_id}", tags=["inventory"])
def enter_count(count_id: str, line_id: str, body: CountEntry, membership: CurrentMembership, db: Db):
    require_permission(membership, "inventory:adjust")
    org_id = membership.organization_id
    count = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.organization_id == org_id))
    if count is None:
        raise HTTPException(status_code=404, detail="Stock count not found")
    if count.status != "open":
        raise HTTPException(status_code=409, detail="This stock count is already completed")
    line = db.scalar(select(StockCountLine).where(StockCountLine.id == line_id, StockCountLine.stock_count_id == count.id))
    if line is None:
        raise HTTPException(status_code=404, detail="Line not found")
    line.counted_qty = body.counted_qty
    line.counted_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": line.id, "counted_qty": line.counted_qty, "variance": line.counted_qty - line.system_qty}


@router.post("/{count_id}/complete", tags=["inventory"])
def complete_count(count_id: str, membership: CurrentMembership, db: Db):
    """Apply every counted line's variance as one stock movement each, in one
    audited batch, and post the net shrinkage/gain to the books."""
    require_permission(membership, "inventory:adjust")
    org_id = membership.organization_id
    count = db.scalar(select(StockCount).where(
        StockCount.id == count_id, StockCount.organization_id == org_id).with_for_update())
    if count is None:
        raise HTTPException(status_code=404, detail="Stock count not found")
    if count.status != "open":
        raise HTTPException(status_code=409, detail="This stock count is already completed")
    lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == count.id)))
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.id.in_({ln.product_id for ln in lines})))}

    now = datetime.now(timezone.utc)
    adjusted = 0
    shrinkage_value = gain_value = ZERO
    for line in lines:
        if line.counted_qty is None:
            continue
        delta = line.counted_qty - line.system_qty
        if delta == 0:
            continue
        product = products[line.product_id]
        balance = balance_row(db, org_id, count.branch_id, product.id)
        balance.quantity += delta
        db.add(StockMovement(
            organization_id=org_id, branch_id=count.branch_id, product_id=product.id,
            movement_type="stock_count", quantity_delta=delta, unit_cost=product.cost_price,
            reference_type="stock_count", reference_id=count.id, occurred_at=now,
        ))
        adjusted += 1
        value = abs(delta) * product.cost_price
        if delta < 0:
            shrinkage_value += value
        else:
            gain_value += value

    count.status = "completed"
    count.completed_at = now
    record_audit(db, membership, "stock_count.completed", "stock_count", count.id,
                 adjusted_lines=adjusted, shrinkage_value=shrinkage_value, gain_value=gain_value)
    journal_lines = []
    if gain_value > 0:
        journal_lines += [Line("1200", gain_value, ZERO), Line("5910", ZERO, gain_value)]
    if shrinkage_value > 0:
        journal_lines += [Line("5910", shrinkage_value, ZERO), Line("1200", ZERO, shrinkage_value)]
    if journal_lines:
        post_journal(db, org_id, count.branch_id, now, "stock_count", count.id, journal_lines,
                     memo=f"Stock count {count.id[:8]}")
    db.commit()
    return {
        "id": count.id, "status": "completed", "adjusted_lines": adjusted,
        "shrinkage_value": shrinkage_value, "gain_value": gain_value,
    }
