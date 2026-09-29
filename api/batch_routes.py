"""Batches and expiry: what is on the shelf, what is about to expire, and whether the books agree."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import CurrentMembership
from .batches import (
    InsufficientSellableStock, add_to_batch, allocate_fefo, balance_row, get_or_create_batch, state_of,
)
from .database import get_db
from .domain_models import (
    Batch, BatchStock, Branch, InventoryBalance, Product, StockMovement, new_id, utcnow,
)
from .permissions import require_permission
from .timeutil import dhaka_today

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
ZERO = Decimal("0")

StateFilter = Literal["all", "expired", "near_expiry", "ok", "no_expiry", "blocked"]


def _today() -> date:
    return datetime.now(timezone.utc).astimezone().date()


def _branch(db: Session, org_id: str, branch_id: str) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


def _shelf(db: Session, org_id: str, branch_id: str, product_id: str | None = None):
    """Batches with stock at a branch, earliest expiry first (unknown expiry last)."""
    statement = (
        select(Batch, BatchStock, Product)
        .join(BatchStock, BatchStock.batch_id == Batch.id)
        .join(Product, Product.id == Batch.product_id)
        .where(
            Batch.organization_id == org_id, BatchStock.branch_id == branch_id,
            BatchStock.quantity > 0,
        )
        .order_by(Batch.expiry_date.is_(None), Batch.expiry_date, Product.name, Batch.batch_no)
    )
    if product_id:
        statement = statement.where(Batch.product_id == product_id)
    return db.execute(statement).all()


def _value(quantity: Decimal, unit_cost: Decimal | None) -> Decimal | None:
    """Stock value at cost. ``None`` when the cost is unknown: never a made-up zero."""
    return None if unit_cost is None else (quantity * unit_cost).quantize(Decimal("0.01"))


@router.post("/products/{product_id}/track-expiry", tags=["inventory"])
def enable_expiry_tracking(product_id: str, membership: CurrentMembership, db: Db):
    """Start tracking batches for a product that already has stock.

    Existing units go into one ``OPENING`` batch per product with no expiry date
    (unknown), sold last, until the real batches are entered.
    """
    require_permission(membership, "inventory:adjust")
    org_id = membership.organization_id
    product = db.scalar(select(Product).where(Product.id == product_id, Product.organization_id == org_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.track_expiry:
        raise HTTPException(status_code=409, detail="Expiry tracking is already on for this product")
    balances = list(db.scalars(select(InventoryBalance).where(
        InventoryBalance.organization_id == org_id, InventoryBalance.product_id == product.id,
        InventoryBalance.quantity > 0,
    )))
    opening_units = sum((b.quantity for b in balances), ZERO)
    if balances:
        batch = get_or_create_batch(
            db, org_id, product, "OPENING", None,
            product.cost_price if product.cost_price > 0 else None, None, utcnow(), "opening",
        )
        for balance in balances:
            db.add(BatchStock(
                organization_id=org_id, branch_id=balance.branch_id,
                batch_id=batch.id, quantity=balance.quantity,
            ))
    product.track_expiry = True
    record_audit(db, membership, "product.expiry_tracking_enabled", "product", product.id,
                 opening_units=opening_units)
    db.commit()
    return {"product_id": product.id, "track_expiry": True, "opening_units": opening_units}


@router.get("/inventory/batches", tags=["inventory"])
def list_batches(
    membership: CurrentMembership, db: Db, branch_id: str,
    state: StateFilter = "all", days: int = Query(default=90, ge=1, le=365),
    product_id: str | None = None, limit: int = Query(default=300, ge=1, le=1000),
):
    require_permission(membership, "inventory:read")
    _branch(db, membership.organization_id, branch_id)
    today = _today()
    items = []
    for batch, stock, product in _shelf(db, membership.organization_id, branch_id, product_id):
        current = state_of(batch, today, days)
        blocked = batch.status == "blocked"
        if state == "blocked" and not blocked:
            continue
        if state not in ("all", "blocked") and current != state:
            continue
        items.append({
            "batch_id": batch.id, "product_id": product.id, "sku": product.sku,
            "product_name": product.name, "batch_no": batch.batch_no,
            "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
            "days_to_expiry": (batch.expiry_date - today).days if batch.expiry_date else None,
            "state": current, "blocked": blocked, "status_reason": batch.status_reason,
            "quantity": stock.quantity, "unit_cost": batch.unit_cost,
            "value": _value(stock.quantity, batch.unit_cost),
        })
    return items[:limit]


@router.get("/inventory/expiry-summary", tags=["inventory"])
def expiry_summary(membership: CurrentMembership, db: Db, branch_id: str):
    """How much stock, and how much money at cost, sits in each expiry window."""
    require_permission(membership, "inventory:read")
    _branch(db, membership.organization_id, branch_id)
    today = _today()

    def empty():
        return {"batches": 0, "units": ZERO, "value": ZERO, "unknown_cost_units": ZERO}

    buckets = {name: empty() for name in ("expired", "d30", "d60", "d90", "later", "no_expiry")}
    blocked = empty()

    def add(bucket, stock, batch):
        bucket["batches"] += 1
        bucket["units"] += stock.quantity
        value = _value(stock.quantity, batch.unit_cost)
        if value is None:
            bucket["unknown_cost_units"] += stock.quantity
        else:
            bucket["value"] += value

    for batch, stock, _ in _shelf(db, membership.organization_id, branch_id):
        if batch.expiry_date is None:
            name = "no_expiry"
        else:
            days = (batch.expiry_date - today).days
            name = ("expired" if days < 0 else "d30" if days <= 30 else "d60" if days <= 60
                    else "d90" if days <= 90 else "later")
        add(buckets[name], stock, batch)
        if batch.status == "blocked":
            add(blocked, stock, batch)

    at_risk = [buckets[n] for n in ("expired", "d30", "d60", "d90")]
    return {
        "today": today.isoformat(),
        "buckets": buckets,
        "blocked": blocked,
        # Money sitting in stock that is expired or expires within 90 days.
        "at_risk_value": sum((b["value"] for b in at_risk), ZERO),
        "at_risk_unknown_cost_units": sum((b["unknown_cost_units"] for b in at_risk), ZERO),
    }


class BatchStatusIn(BaseModel):
    status: Literal["active", "blocked"]
    reason: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def reason_when_blocking(self):
        if self.status == "blocked" and not (self.reason and len(self.reason.strip()) >= 2):
            raise ValueError("A reason is required when blocking a batch")
        return self


@router.post("/inventory/batches/{batch_id}/status", tags=["inventory"])
def set_batch_status(batch_id: str, body: BatchStatusIn, membership: CurrentMembership, db: Db):
    """Block a batch (recall, quarantine, damaged) so it can never be sold, or release it."""
    require_permission(membership, "inventory:adjust")
    batch = db.scalar(select(Batch).where(
        Batch.id == batch_id, Batch.organization_id == membership.organization_id))
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    batch.status = body.status
    batch.status_reason = body.reason.strip() if body.status == "blocked" and body.reason else None
    record_audit(
        db, membership, "batch.blocked" if body.status == "blocked" else "batch.released",
        "batch", batch.id, batch_no=batch.batch_no, product_id=batch.product_id,
        reason=batch.status_reason,
    )
    db.commit()
    return {"batch_id": batch.id, "status": batch.status, "status_reason": batch.status_reason}


@router.get("/inventory/reconciliation", tags=["inventory"])
def reconciliation(membership: CurrentMembership, db: Db, branch_id: str):
    """Do the books agree with themselves?

    For every product at the branch: the stock balance against the sum of its
    ledger movements, and (for expiry-tracked products) against the sum of its
    batches. A non-zero residual is reported, never quietly corrected.
    """
    require_permission(membership, "inventory:read")
    org_id = membership.organization_id
    _branch(db, org_id, branch_id)
    balances = dict(db.execute(select(InventoryBalance.product_id, InventoryBalance.quantity).where(
        InventoryBalance.organization_id == org_id, InventoryBalance.branch_id == branch_id)).all())
    ledger = dict(db.execute(
        select(StockMovement.product_id, func.coalesce(func.sum(StockMovement.quantity_delta), 0))
        .where(StockMovement.organization_id == org_id, StockMovement.branch_id == branch_id)
        .group_by(StockMovement.product_id)).all())
    batched = dict(db.execute(
        select(Batch.product_id, func.coalesce(func.sum(BatchStock.quantity), 0))
        .join(BatchStock, BatchStock.batch_id == Batch.id)
        .where(Batch.organization_id == org_id, BatchStock.branch_id == branch_id)
        .group_by(Batch.product_id)).all())
    product_ids = set(balances) | set(ledger) | set(batched)
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.id.in_(product_ids)))} if product_ids else {}

    issues = []
    for product_id in sorted(product_ids, key=lambda i: products[i].name if i in products else ""):
        product = products.get(product_id)
        if product is None:
            continue
        balance = Decimal(balances.get(product_id, 0))
        ledger_sum = Decimal(ledger.get(product_id, 0))
        batch_sum = Decimal(batched.get(product_id, 0)) if product.track_expiry else None
        ledger_residual = balance - ledger_sum
        batch_residual = None if batch_sum is None else balance - batch_sum
        if ledger_residual != 0 or (batch_residual is not None and batch_residual != 0):
            issues.append({
                "product_id": product.id, "sku": product.sku, "product_name": product.name,
                "tracked": product.track_expiry, "balance": balance, "ledger_sum": ledger_sum,
                "ledger_residual": ledger_residual, "batch_sum": batch_sum,
                "batch_residual": batch_residual,
            })
    return {"checked": len(product_ids), "mismatched": len(issues), "items": issues}


class TransferIn(BaseModel):
    from_branch_id: str
    to_branch_id: str
    product_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


@router.post("/inventory/transfer", tags=["inventory"])
def transfer_stock(body: TransferIn, membership: CurrentMembership, db: Db):
    """Move stock between two branches of the same business, atomically.

    Expiry-tracked products travel batch by batch (earliest expiry first, expired and
    blocked batches stay behind), so the destination keeps the true expiry dates.
    """
    require_permission(membership, "inventory:transfer")
    org_id = membership.organization_id
    if body.from_branch_id == body.to_branch_id:
        raise HTTPException(status_code=422, detail="Choose two different branches")
    _branch(db, org_id, body.from_branch_id)
    _branch(db, org_id, body.to_branch_id)
    product = db.scalar(select(Product).where(Product.id == body.product_id, Product.organization_id == org_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    transfer_id, now = new_id(), utcnow()

    def movement(branch_id, delta, batch_id=None):
        db.add(StockMovement(
            organization_id=org_id, branch_id=branch_id, product_id=product.id,
            movement_type="transfer_out" if delta < 0 else "transfer_in", quantity_delta=delta,
            reference_type="transfer", reference_id=transfer_id, batch_id=batch_id, occurred_at=now,
            unit_cost=product.cost_price if product.cost_price > 0 else None,
        ))

    moved = []
    if product.track_expiry:
        try:
            plan = allocate_fefo(db, org_id, body.from_branch_id, product.id, body.quantity, dhaka_today())
        except InsufficientSellableStock as exc:
            raise HTTPException(status_code=409, detail="Not enough sellable stock in the source branch") from exc
        for batch, stock, take in plan:
            stock.quantity -= take
            balance_row(db, org_id, body.from_branch_id, product.id).quantity -= take
            add_to_batch(db, org_id, body.to_branch_id, batch, take)
            movement(body.from_branch_id, -take, batch.id)
            movement(body.to_branch_id, take, batch.id)
            moved.append({"batch_no": batch.batch_no, "quantity": take})
    else:
        source = balance_row(db, org_id, body.from_branch_id, product.id)
        if source.quantity < body.quantity:
            raise HTTPException(status_code=409, detail="Not enough stock in the source branch")
        source.quantity -= body.quantity
        balance_row(db, org_id, body.to_branch_id, product.id).quantity += body.quantity
        movement(body.from_branch_id, -body.quantity)
        movement(body.to_branch_id, body.quantity)
        moved.append({"batch_no": None, "quantity": body.quantity})
    record_audit(db, membership, "inventory.transferred", "product", product.id,
                 quantity=body.quantity, from_branch=body.from_branch_id, to_branch=body.to_branch_id)
    db.commit()
    return {"transfer_id": transfer_id, "product_id": product.id, "quantity": body.quantity, "moved": moved}
