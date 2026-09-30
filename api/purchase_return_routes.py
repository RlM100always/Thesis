"""Purchase return, supplier claim, and credit-note workflow.

The three events deliberately post at different times:
* submit: evidence and requested quantities only;
* dispatch: physical stock leaves and becomes a supplier-claim asset;
* credit note: the accepted claim reduces Accounts Payable.

Every mutation is tenant scoped and committed once, so stock, subledger,
journal, and audit cannot be partially applied.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .accounting import Line, post_journal
from .app_schemas import (
    PurchaseReturnCreate, PurchaseReturnCreditNote, PurchaseReturnDispatch,
    PurchaseReturnLineView, PurchaseReturnReject, PurchaseReturnView,
)
from .audit import record_audit
from .auth import CurrentMembership
from .batches import remove_from_batch
from .database import get_db
from .domain_models import (
    Batch, BatchStock, InventoryBalance, LedgerEntry, Product, PurchaseOrder,
    PurchaseOrderItem, PurchaseReturn, PurchaseReturnItem, StockMovement,
    Supplier,
)
from .permissions import require_permission

router = APIRouter(prefix="/api/app", tags=["purchase returns"])
Db = Annotated[Session, Depends(get_db)]
MONEY = Decimal("0.01")
ZERO = Decimal("0")


def _return_view(db: Session, claim: PurchaseReturn) -> PurchaseReturnView:
    order = db.get(PurchaseOrder, claim.purchase_order_id)
    supplier = db.get(Supplier, claim.supplier_id)
    rows = db.execute(
        select(PurchaseReturnItem, Product, Batch)
        .join(Product, Product.id == PurchaseReturnItem.product_id)
        .outerjoin(Batch, Batch.id == PurchaseReturnItem.batch_id)
        .where(PurchaseReturnItem.purchase_return_id == claim.id)
        .order_by(PurchaseReturnItem.created_at)
    ).all()
    return PurchaseReturnView(
        id=claim.id, purchase_order_id=claim.purchase_order_id,
        purchase_order_number=order.order_number, supplier_id=claim.supplier_id,
        supplier_name=supplier.name, branch_id=claim.branch_id,
        return_number=claim.return_number, claim_type=claim.claim_type,
        reason=claim.reason, status=claim.status, total=claim.total,
        submitted_at=claim.submitted_at, dispatched_at=claim.dispatched_at,
        settled_at=claim.settled_at, credit_note_number=claim.credit_note_number,
        supplier_note=claim.supplier_note,
        items=[PurchaseReturnLineView(
            id=item.id, purchase_order_item_id=item.purchase_order_item_id,
            product_id=item.product_id, product_name=product.name, sku=product.sku,
            batch_id=item.batch_id, batch_no=batch.batch_no if batch else None,
            quantity=item.quantity, unit_cost=item.unit_cost, amount=item.amount,
        ) for item, product, batch in rows],
    )


def _get_claim(db: Session, org_id: str, claim_id: str, *, lock: bool = False) -> PurchaseReturn:
    statement = select(PurchaseReturn).where(
        PurchaseReturn.id == claim_id, PurchaseReturn.organization_id == org_id,
    )
    if lock:
        statement = statement.with_for_update()
    claim = db.scalar(statement)
    if claim is None:
        raise HTTPException(status_code=404, detail="Purchase return was not found")
    return claim


@router.get("/purchase-returns", response_model=list[PurchaseReturnView])
def list_purchase_returns(
    membership: CurrentMembership, db: Db,
    status: str | None = None, limit: int = Query(default=100, ge=1, le=500),
):
    require_permission(membership, "purchase_returns:read")
    statement = select(PurchaseReturn).where(
        PurchaseReturn.organization_id == membership.organization_id
    )
    if status:
        statement = statement.where(PurchaseReturn.status == status)
    claims = db.scalars(statement.order_by(PurchaseReturn.submitted_at.desc()).limit(limit)).all()
    return [_return_view(db, claim) for claim in claims]


@router.post("/purchase-returns", response_model=PurchaseReturnView)
def create_purchase_return(payload: PurchaseReturnCreate, membership: CurrentMembership, db: Db):
    require_permission(membership, "purchase_returns:create")
    org_id = membership.organization_id
    order = db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == payload.purchase_order_id,
        PurchaseOrder.organization_id == org_id,
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Purchase order was not found")

    line_ids = {row.purchase_order_item_id for row in payload.items}
    lines = {line.id: line for line in db.scalars(select(PurchaseOrderItem).where(
        PurchaseOrderItem.organization_id == org_id,
        PurchaseOrderItem.purchase_order_id == order.id,
        PurchaseOrderItem.id.in_(line_ids),
    ))}
    if len(lines) != len(line_ids):
        raise HTTPException(status_code=404, detail="One or more purchase lines were not found")
    products = {product.id: product for product in db.scalars(select(Product).where(
        Product.organization_id == org_id,
        Product.id.in_({line.product_id for line in lines.values()}),
    ))}

    requested_by_line: dict[str, Decimal] = {}
    seen_allocations: set[tuple[str, str | None]] = set()
    batches: dict[str, Batch] = {}
    for row in payload.items:
        allocation = (row.purchase_order_item_id, row.batch_id)
        if allocation in seen_allocations:
            raise HTTPException(status_code=422, detail="A purchase line and batch may appear only once")
        seen_allocations.add(allocation)
        line = lines[row.purchase_order_item_id]
        product = products[line.product_id]
        requested_by_line[line.id] = requested_by_line.get(line.id, ZERO) + row.quantity
        if product.track_expiry:
            if row.batch_id is None:
                raise HTTPException(status_code=422, detail=f"Batch is required for {product.sku}")
            batch = db.scalar(select(Batch).where(
                Batch.id == row.batch_id, Batch.organization_id == org_id,
                Batch.product_id == product.id, Batch.supplier_id == order.supplier_id,
            ))
            if batch is None:
                raise HTTPException(status_code=404, detail=f"A valid received batch was not found for {product.sku}")
            was_received = db.scalar(select(StockMovement.id).where(
                StockMovement.organization_id == org_id,
                StockMovement.reference_type == "purchase_order",
                StockMovement.reference_id == order.id,
                StockMovement.product_id == product.id,
                StockMovement.batch_id == batch.id,
                StockMovement.movement_type == "purchase_receipt",
            ))
            if was_received is None:
                raise HTTPException(status_code=409, detail=f"Batch {batch.batch_no} was not received on this purchase")
            batches[batch.id] = batch
        elif row.batch_id is not None:
            raise HTTPException(status_code=422, detail=f"{product.sku} is not batch tracked")

    for line_id, quantity in requested_by_line.items():
        already_claimed = db.scalar(
            select(func.coalesce(func.sum(PurchaseReturnItem.quantity), 0))
            .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnItem.purchase_return_id)
            .where(
                PurchaseReturnItem.organization_id == org_id,
                PurchaseReturnItem.purchase_order_item_id == line_id,
                PurchaseReturn.status != "rejected",
            )
        )
        if Decimal(already_claimed) + quantity > lines[line_id].received_quantity:
            raise HTTPException(status_code=409, detail="Claim quantity exceeds the quantity received")

    total = sum(
        (row.quantity * lines[row.purchase_order_item_id].unit_cost for row in payload.items), ZERO
    ).quantize(MONEY, rounding=ROUND_HALF_UP)
    claim = PurchaseReturn(
        organization_id=org_id, branch_id=order.branch_id,
        purchase_order_id=order.id, supplier_id=order.supplier_id,
        return_number=payload.return_number, claim_type=payload.claim_type,
        reason=payload.reason, status="submitted", total=total,
        submitted_at=payload.submitted_at,
    )
    db.add(claim)
    db.flush()
    for row in payload.items:
        line = lines[row.purchase_order_item_id]
        amount = (row.quantity * line.unit_cost).quantize(MONEY, rounding=ROUND_HALF_UP)
        db.add(PurchaseReturnItem(
            organization_id=org_id, purchase_return_id=claim.id,
            purchase_order_item_id=line.id, product_id=line.product_id,
            batch_id=row.batch_id, quantity=row.quantity, unit_cost=line.unit_cost,
            amount=amount,
        ))
    record_audit(db, membership, "purchase_return.submitted", "purchase_return", claim.id,
                 return_number=claim.return_number, total=claim.total)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Purchase return number already exists") from exc
    return _return_view(db, claim)


@router.post("/purchase-returns/{claim_id}/dispatch", response_model=PurchaseReturnView)
def dispatch_purchase_return(
    claim_id: str, payload: PurchaseReturnDispatch,
    membership: CurrentMembership, db: Db,
):
    require_permission(membership, "purchase_returns:dispatch")
    org_id = membership.organization_id
    claim = _get_claim(db, org_id, claim_id, lock=True)
    if claim.status != "submitted":
        raise HTTPException(status_code=409, detail="Only a submitted claim can be dispatched")
    items = list(db.scalars(select(PurchaseReturnItem).where(
        PurchaseReturnItem.purchase_return_id == claim.id,
        PurchaseReturnItem.organization_id == org_id,
    )))
    batches = {batch.id: batch for batch in db.scalars(select(Batch).where(
        Batch.organization_id == org_id,
        Batch.id.in_({item.batch_id for item in items if item.batch_id}),
    ))}

    # Validate every allocation before applying any of them. The enclosing DB
    # transaction is still the final safety net for concurrent dispatches.
    for item in items:
        balance = db.scalar(select(InventoryBalance).where(
            InventoryBalance.organization_id == org_id,
            InventoryBalance.branch_id == claim.branch_id,
            InventoryBalance.product_id == item.product_id,
        ).with_for_update())
        if balance is None or balance.quantity < item.quantity:
            raise HTTPException(status_code=409, detail="Current stock is lower than the return quantity")
        if item.batch_id:
            stock = db.scalar(select(BatchStock).where(
                BatchStock.organization_id == org_id,
                BatchStock.branch_id == claim.branch_id,
                BatchStock.batch_id == item.batch_id,
            ).with_for_update())
            if stock is None or stock.quantity < item.quantity:
                raise HTTPException(status_code=409, detail="The selected batch has insufficient stock")

    for item in items:
        if item.batch_id:
            remove_from_batch(db, org_id, claim.branch_id, batches[item.batch_id], item.quantity)
        else:
            balance = db.scalar(select(InventoryBalance).where(
                InventoryBalance.organization_id == org_id,
                InventoryBalance.branch_id == claim.branch_id,
                InventoryBalance.product_id == item.product_id,
            ).with_for_update())
            balance.quantity -= item.quantity
        db.add(StockMovement(
            organization_id=org_id, branch_id=claim.branch_id,
            product_id=item.product_id, batch_id=item.batch_id,
            movement_type="purchase_return", quantity_delta=-item.quantity,
            unit_cost=item.unit_cost, reference_type="purchase_return",
            reference_id=claim.id, occurred_at=payload.dispatched_at,
        ))

    if claim.total > 0:
        post_journal(db, org_id, claim.branch_id, payload.dispatched_at,
                     "purchase_return_dispatch", claim.id, [
            Line("1250", claim.total, ZERO, "supplier", claim.supplier_id),
            Line("1200", ZERO, claim.total),
        ], memo=f"Supplier claim dispatched: {claim.return_number}")
    claim.status = "dispatched"
    claim.dispatched_at = payload.dispatched_at
    record_audit(db, membership, "purchase_return.dispatched", "purchase_return", claim.id,
                 return_number=claim.return_number, total=claim.total)
    db.commit()
    return _return_view(db, claim)


@router.post("/purchase-returns/{claim_id}/credit-note", response_model=PurchaseReturnView)
def accept_credit_note(
    claim_id: str, payload: PurchaseReturnCreditNote,
    membership: CurrentMembership, db: Db,
):
    require_permission(membership, "purchase_returns:settle")
    org_id = membership.organization_id
    claim = _get_claim(db, org_id, claim_id, lock=True)
    if claim.status != "dispatched":
        raise HTTPException(status_code=409, detail="Only a dispatched claim can receive a credit note")
    duplicate = db.scalar(select(PurchaseReturn.id).where(
        PurchaseReturn.organization_id == org_id,
        PurchaseReturn.supplier_id == claim.supplier_id,
        PurchaseReturn.credit_note_number == payload.credit_note_number,
        PurchaseReturn.id != claim.id,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="This supplier credit note is already recorded")
    if claim.total > 0:
        db.add(LedgerEntry(
            organization_id=org_id, branch_id=claim.branch_id,
            ledger_type="payable", party_type="supplier", party_id=claim.supplier_id,
            amount_delta=-claim.total, reference_type="supplier_credit_note",
            reference_id=claim.id, note=payload.supplier_note,
            occurred_at=payload.accepted_at,
        ))
        post_journal(db, org_id, claim.branch_id, payload.accepted_at,
                     "supplier_credit_note", claim.id, [
            Line("2000", claim.total, ZERO, "supplier", claim.supplier_id),
            Line("1250", ZERO, claim.total, "supplier", claim.supplier_id),
        ], memo=f"Supplier credit note {payload.credit_note_number}")
    claim.status = "settled"
    claim.settled_at = payload.accepted_at
    claim.credit_note_number = payload.credit_note_number
    claim.supplier_note = payload.supplier_note
    record_audit(db, membership, "purchase_return.credit_note", "purchase_return", claim.id,
                 credit_note_number=payload.credit_note_number, total=claim.total)
    db.commit()
    return _return_view(db, claim)


@router.post("/purchase-returns/{claim_id}/reject", response_model=PurchaseReturnView)
def reject_purchase_return(
    claim_id: str, payload: PurchaseReturnReject,
    membership: CurrentMembership, db: Db,
):
    require_permission(membership, "purchase_returns:settle")
    claim = _get_claim(db, membership.organization_id, claim_id, lock=True)
    if claim.status != "submitted":
        raise HTTPException(status_code=409, detail="A dispatched or completed claim cannot be rejected")
    claim.status = "rejected"
    claim.supplier_note = payload.reason
    record_audit(db, membership, "purchase_return.rejected", "purchase_return", claim.id,
                 reason=payload.reason)
    db.commit()
    return _return_view(db, claim)
