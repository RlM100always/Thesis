"""What to buy: a transparent reorder plan from the shop's own sales, and one-step ordering.

Every number is arithmetic on the shop's records, and every suggestion carries the
figures behind it, so the owner can see *why* and overrule it:

    suggested = ceil( daily_rate × (lead_days + cover_days) − sellable_stock − already_on_order )

``sellable_stock`` leaves out expired and blocked batches: units nobody may sell do not
count as cover. Products with no recent sales fall back to their reorder level.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import CurrentMembership
from .database import get_db
from .domain_models import (
    Batch, BatchStock, Branch, InventoryBalance, Product, PurchaseOrder, PurchaseOrderItem,
    SalesOrder, SalesOrderItem, Supplier, utcnow,
)
from .permissions import require_permission
from .timeutil import dhaka_today

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
DEFAULT_LEAD_DAYS = 7
ZERO = Decimal("0")


def _branch(db: Session, org_id: str, branch_id: str) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


@router.get("/reorder-plan", tags=["planning"])
def reorder_plan(
    membership: CurrentMembership, db: Db, branch_id: str,
    cover_days: int = Query(default=14, ge=1, le=90), history_days: int = Query(default=28, ge=7, le=180),
):
    require_permission(membership, "purchases:read")
    require_permission(membership, "inventory:read")
    org_id = membership.organization_id
    _branch(db, org_id, branch_id)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=history_days)
    today = dhaka_today()

    sold = dict(db.execute(
        select(SalesOrderItem.product_id, func.sum(SalesOrderItem.quantity - SalesOrderItem.returned_quantity))
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
        .where(SalesOrder.organization_id == org_id, SalesOrder.branch_id == branch_id, SalesOrder.sold_at >= since)
        .group_by(SalesOrderItem.product_id)).all())
    balance = dict(db.execute(select(InventoryBalance.product_id, InventoryBalance.quantity).where(
        InventoryBalance.organization_id == org_id, InventoryBalance.branch_id == branch_id)).all())
    incoming = dict(db.execute(
        select(PurchaseOrderItem.product_id, func.sum(PurchaseOrderItem.quantity - PurchaseOrderItem.received_quantity))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(PurchaseOrder.organization_id == org_id, PurchaseOrder.branch_id == branch_id,
               PurchaseOrder.status.in_(["ordered", "partial"])).group_by(PurchaseOrderItem.product_id)).all())
    unsellable: dict[str, Decimal] = {}
    for batch, stock in db.execute(
        select(Batch, BatchStock).join(BatchStock, BatchStock.batch_id == Batch.id)
        .where(Batch.organization_id == org_id, BatchStock.branch_id == branch_id, BatchStock.quantity > 0)
    ).all():
        if batch.status == "blocked" or (batch.expiry_date is not None and batch.expiry_date < today):
            unsellable[batch.product_id] = unsellable.get(batch.product_id, ZERO) + stock.quantity

    last_buy: dict[str, tuple] = {}
    for item, order in db.execute(
        select(PurchaseOrderItem, PurchaseOrder).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(PurchaseOrder.organization_id == org_id).order_by(PurchaseOrder.ordered_at)
    ).all():
        last_buy[item.product_id] = (order.supplier_id, item.unit_cost)  # later rows overwrite earlier ones
    suppliers = {s.id: s for s in db.scalars(select(Supplier).where(Supplier.organization_id == org_id))}

    items = []
    for product in db.scalars(select(Product).where(Product.organization_id == org_id, Product.active.is_(True))):
        on_hand = Decimal(balance.get(product.id, 0))
        sellable = max(ZERO, on_hand - unsellable.get(product.id, ZERO))
        coming = Decimal(incoming.get(product.id, 0) or 0)
        rate = Decimal(sold.get(product.id, 0) or 0) / history_days
        supplier_id, last_cost = last_buy.get(product.id, (None, None))
        supplier = suppliers.get(supplier_id)
        lead = supplier.typical_lead_days if supplier and supplier.typical_lead_days > 0 else DEFAULT_LEAD_DAYS
        if rate > 0:
            target = rate * (lead + cover_days)
            need = target - sellable - coming
            reason = "sales"
        else:
            target = product.reorder_level * 2
            need = target - sellable - coming if sellable <= product.reorder_level else ZERO
            reason = "reorder_level"
        if need <= 0:
            continue
        cover = float(sellable / rate) if rate > 0 else None
        items.append({
            "product_id": product.id, "sku": product.sku, "name": product.name, "track_expiry": product.track_expiry,
            "sellable": sellable, "unsellable": unsellable.get(product.id, ZERO), "incoming": coming,
            "daily_rate": round(rate, 3), "days_of_cover": None if cover is None else round(cover, 1),
            "lead_days": lead, "cover_days": cover_days, "target": round(target, 1),
            "suggested_qty": Decimal(math.ceil(need)), "reason": reason,
            "unit_cost": last_cost if last_cost is not None else (product.cost_price if product.cost_price > 0 else None),
            "supplier_id": supplier_id, "supplier_name": supplier.name if supplier else None,
            # Will run out before an order placed today could arrive.
            "urgent": cover is not None and cover < lead,
        })
    items.sort(key=lambda i: (not i["urgent"], i["days_of_cover"] if i["days_of_cover"] is not None else 9999, i["name"]))
    return {"history_days": history_days, "cover_days": cover_days, "items": items}


class PlannedItem(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class PlannedOrder(BaseModel):
    supplier_id: str
    items: list[PlannedItem] = Field(min_length=1, max_length=200)


class PlanOrders(BaseModel):
    branch_id: str
    orders: list[PlannedOrder] = Field(min_length=1, max_length=50)


@router.post("/reorder-plan/orders", tags=["planning"])
def create_orders(body: PlanOrders, membership: CurrentMembership, db: Db):
    """Turn the plan into one purchase order per supplier, in a single step."""
    require_permission(membership, "purchases:create")
    org_id = membership.organization_id
    _branch(db, org_id, body.branch_id)
    product_ids = {i.product_id for o in body.orders for i in o.items}
    known_products = set(db.scalars(select(Product.id).where(Product.organization_id == org_id, Product.id.in_(product_ids))))
    if known_products != product_ids:
        raise HTTPException(status_code=404, detail="One or more products were not found")
    created = []
    now = utcnow()
    for number, planned in enumerate(body.orders, start=1):
        supplier = db.scalar(select(Supplier).where(Supplier.id == planned.supplier_id, Supplier.organization_id == org_id))
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        merged: dict[str, PlannedItem] = {}
        for item in planned.items:  # the same product twice becomes one line
            merged[item.product_id] = item if item.product_id not in merged else PlannedItem(
                product_id=item.product_id, quantity=merged[item.product_id].quantity + item.quantity, unit_cost=item.unit_cost)
        total = sum((i.quantity * i.unit_cost for i in merged.values()), ZERO).quantize(Decimal("0.01"))
        order = PurchaseOrder(
            organization_id=org_id, branch_id=body.branch_id, supplier_id=supplier.id,
            order_number=f"PO-{now:%Y%m%d}-{now:%H%M%S}-{number}", ordered_at=now,
            expected_at=now + timedelta(days=supplier.typical_lead_days or DEFAULT_LEAD_DAYS), total=total,
        )
        db.add(order)
        db.flush()
        for item in merged.values():
            db.add(PurchaseOrderItem(organization_id=org_id, purchase_order_id=order.id,
                                     product_id=item.product_id, quantity=item.quantity, unit_cost=item.unit_cost))
        record_audit(db, membership, "purchase.created", "purchase_order", order.id,
                     order_number=order.order_number, total=total, source="reorder_plan")
        created.append({"id": order.id, "order_number": order.order_number, "supplier": supplier.name, "total": total, "lines": len(merged)})
    db.commit()
    return {"created": created}
