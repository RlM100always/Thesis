"""Batch and expiry stock: FEFO allocation and the rules that keep it honest.

Invariant for a product with ``track_expiry`` at a branch:

    InventoryBalance.quantity == sum(BatchStock.quantity of its batches)

Every function here moves the two together, so callers never update one and
forget the other. Rules the module enforces:

* Sell **first-expiry-first-out**. A batch with no expiry date is sold last.
* Never sell an expired batch or a blocked one (recall, quarantine, damaged).
* A batch number is unique per product; the same batch arriving again must carry
  the same expiry, or the receipt is refused rather than silently relabelled.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain_models import Batch, BatchStock, InventoryBalance, Product, SaleItemBatch

ZERO = Decimal("0")
NEAR_EXPIRY_DAYS = 90


class InsufficientSellableStock(Exception):
    """Not enough sellable units; ``unsellable`` counts expired or blocked units held."""

    def __init__(self, available: Decimal, unsellable: Decimal):
        self.available, self.unsellable = available, unsellable
        super().__init__(f"available={available} unsellable={unsellable}")


def stock_row(db: Session, org_id: str, branch_id: str, batch_id: str, create: bool = False) -> BatchStock | None:
    row = db.scalar(select(BatchStock).where(
        BatchStock.organization_id == org_id, BatchStock.branch_id == branch_id,
        BatchStock.batch_id == batch_id,
    ).with_for_update())
    if row is None and create:
        row = BatchStock(organization_id=org_id, branch_id=branch_id, batch_id=batch_id, quantity=ZERO)
        db.add(row)
        db.flush()
    return row


def balance_row(db: Session, org_id: str, branch_id: str, product_id: str) -> InventoryBalance:
    row = db.scalar(select(InventoryBalance).where(
        InventoryBalance.organization_id == org_id, InventoryBalance.branch_id == branch_id,
        InventoryBalance.product_id == product_id,
    ).with_for_update())
    if row is None:
        row = InventoryBalance(
            organization_id=org_id, branch_id=branch_id, product_id=product_id, quantity=ZERO)
        db.add(row)
        db.flush()
    return row


def get_or_create_batch(
    db: Session, org_id: str, product: Product, batch_no: str, expiry_date: date | None,
    unit_cost: Decimal | None, supplier_id: str | None, received_at: datetime, source: str,
) -> Batch:
    """Find the batch by number or create it. A different expiry for a known batch is refused."""
    batch_no = batch_no.strip()
    batch = db.scalar(select(Batch).where(
        Batch.organization_id == org_id, Batch.product_id == product.id, Batch.batch_no == batch_no,
    ))
    if batch is None:
        batch = Batch(
            organization_id=org_id, product_id=product.id, batch_no=batch_no,
            expiry_date=expiry_date, unit_cost=unit_cost, supplier_id=supplier_id,
            received_at=received_at, source=source,
        )
        db.add(batch)
        db.flush()
        return batch
    if expiry_date is not None and batch.expiry_date is not None and batch.expiry_date != expiry_date:
        raise HTTPException(
            status_code=409,
            detail=f"Batch {batch_no} of {product.sku} already exists with a different expiry date",
        )
    if batch.expiry_date is None and expiry_date is not None:
        batch.expiry_date = expiry_date  # learn the expiry the first time it is known
    return batch


def add_to_batch(
    db: Session, org_id: str, branch_id: str, batch: Batch, quantity: Decimal,
) -> None:
    """Add units to a batch at a branch and to the branch's product balance."""
    row = stock_row(db, org_id, branch_id, batch.id, create=True)
    row.quantity += quantity
    balance_row(db, org_id, branch_id, batch.product_id).quantity += quantity


def remove_from_batch(
    db: Session, org_id: str, branch_id: str, batch: Batch, quantity: Decimal,
) -> None:
    row = stock_row(db, org_id, branch_id, batch.id)
    if row is None or row.quantity < quantity:
        raise HTTPException(status_code=409, detail="The batch does not hold that many units")
    row.quantity -= quantity
    balance_row(db, org_id, branch_id, batch.product_id).quantity -= quantity


def is_sellable(batch: Batch, on_date: date) -> bool:
    return batch.status == "active" and (batch.expiry_date is None or batch.expiry_date >= on_date)


def allocate_fefo(
    db: Session, org_id: str, branch_id: str, product_id: str, quantity: Decimal, on_date: date,
) -> list[tuple[Batch, BatchStock, Decimal]]:
    """Reserve ``quantity`` from sellable batches, earliest expiry first.

    Returns ``(batch, stock_row, take)`` triples and has *not* changed any stock:
    the caller applies them, so a later failure leaves nothing half-moved.
    Raises ``InsufficientSellableStock`` if the sellable units are not enough.
    """
    rows = db.execute(
        select(Batch, BatchStock)
        .join(BatchStock, BatchStock.batch_id == Batch.id)
        .where(
            Batch.organization_id == org_id, Batch.product_id == product_id,
            BatchStock.branch_id == branch_id, BatchStock.quantity > 0,
        )
        .order_by(Batch.expiry_date.is_(None), Batch.expiry_date, Batch.received_at, Batch.id)
        .with_for_update(of=BatchStock)
    ).all()
    remaining = quantity
    plan: list[tuple[Batch, BatchStock, Decimal]] = []
    sellable = unsellable = ZERO
    for batch, stock in rows:
        if stock.quantity <= 0:
            continue  # emptied earlier in this same transaction
        if not is_sellable(batch, on_date):
            unsellable += stock.quantity
            continue
        sellable += stock.quantity
        if remaining > 0:
            take = min(stock.quantity, remaining)
            plan.append((batch, stock, take))
            remaining -= take
    if remaining > 0:
        raise InsufficientSellableStock(sellable, unsellable)
    return plan


def blended_cost(plan: list[tuple[Batch, BatchStock, Decimal]], fallback: Decimal) -> Decimal:
    """Cost per unit of what was actually sold, from the batches' own costs.

    Falls back to the product's cost price if any batch has no recorded cost,
    rather than pricing part of the sale at zero.
    """
    total = sum((take for _, _, take in plan), ZERO)
    if total == 0 or any(batch.unit_cost is None for batch, _, _ in plan):
        return fallback
    return (sum((batch.unit_cost * take for batch, _, take in plan), ZERO) / total).quantize(Decimal("0.01"))


def state_of(batch: Batch, today: date, near_days: int = NEAR_EXPIRY_DAYS) -> str:
    """expired | near_expiry | ok | no_expiry."""
    if batch.expiry_date is None:
        return "no_expiry"
    if batch.expiry_date < today:
        return "expired"
    if (batch.expiry_date - today).days <= near_days:
        return "near_expiry"
    return "ok"


def restock_return(
    db: Session, org_id: str, branch_id: str, product: Product, sales_order_item_id: str,
    quantity: Decimal, returned_at: datetime,
) -> list[tuple[str, Decimal]]:
    """Put returned units back into the batches the sale line came from.

    Returns ``(batch_id, quantity)`` pairs. Units that cannot be traced to a batch
    (the line was sold before expiry tracking began) go to a ``RETURNED`` batch
    with no expiry date, so they stay visible and are sold last.
    """
    allocations = db.scalars(select(SaleItemBatch).where(
        SaleItemBatch.organization_id == org_id,
        SaleItemBatch.sales_order_item_id == sales_order_item_id,
        SaleItemBatch.returned_quantity < SaleItemBatch.quantity,
    ).order_by(SaleItemBatch.created_at.desc(), SaleItemBatch.id)).all()
    remaining, moved = quantity, []
    for allocation in allocations:
        if remaining <= 0:
            break
        take = min(allocation.quantity - allocation.returned_quantity, remaining)
        batch = db.get(Batch, allocation.batch_id)
        add_to_batch(db, org_id, branch_id, batch, take)
        allocation.returned_quantity += take
        moved.append((batch.id, take))
        remaining -= take
    if remaining > 0:
        batch = get_or_create_batch(db, org_id, product, "RETURNED", None, None, None, returned_at, "return")
        add_to_batch(db, org_id, branch_id, batch, remaining)
        moved.append((batch.id, remaining))
    return moved
