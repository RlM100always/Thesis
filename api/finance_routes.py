"""Purchasing, receiving, returns, refunds, expenses, and subledgers."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import (
    ExpenseCreate, ExpenseView, LedgerBalanceView, PurchaseCreate, PurchaseDetailView,
    PurchaseLineView, PurchaseReceive, PurchaseView, ReturnCreate, ReturnHistoryView,
    ReturnView, SettlementCreate,
)
from .auth import CurrentMembership, CurrentUser
from .commerce_routes import require_role
from .database import get_db
from .domain_models import (
    AuditLog, Branch, Customer, Expense, InventoryBalance, LedgerEntry, Payment, Product, PurchaseOrder,
    PurchaseOrderItem, Refund, SalesOrder, SalesOrderItem, SalesReturn,
    SalesReturnItem, StockMovement, Supplier,
)

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
MONEY = Decimal("0.01")


@router.post("/purchases", response_model=PurchaseView, tags=["purchases"])
def create_purchase(payload: PurchaseCreate, membership: CurrentMembership, db: Db):
    require_role(membership, "owner", "manager", "accountant")
    org_id = membership.organization_id
    if db.scalar(select(Branch.id).where(Branch.id == payload.branch_id, Branch.organization_id == org_id)) is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    if db.scalar(select(Supplier.id).where(Supplier.id == payload.supplier_id, Supplier.organization_id == org_id)) is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    ids = [item.product_id for item in payload.items]
    products = set(db.scalars(select(Product.id).where(Product.organization_id == org_id, Product.id.in_(ids))))
    if len(products) != len(set(ids)):
        raise HTTPException(status_code=404, detail="One or more products were not found")
    total = sum((i.quantity * i.unit_cost for i in payload.items), Decimal("0")).quantize(MONEY)
    order = PurchaseOrder(
        organization_id=org_id, branch_id=payload.branch_id, supplier_id=payload.supplier_id,
        order_number=payload.order_number, ordered_at=payload.ordered_at,
        expected_at=payload.expected_at, total=total,
    )
    db.add(order)
    try:
        db.flush()
        for item in payload.items:
            db.add(PurchaseOrderItem(
                organization_id=org_id, purchase_order_id=order.id, **item.model_dump()
            ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Purchase order number already exists") from exc
    return order


@router.get("/purchases", response_model=list[PurchaseDetailView], tags=["purchases"])
def list_purchases(
    membership: CurrentMembership, db: Db,
    status: str | None = None, limit: int = Query(default=100, ge=1, le=500),
):
    org_id = membership.organization_id
    statement = select(PurchaseOrder, Supplier).join(
        Supplier, Supplier.id == PurchaseOrder.supplier_id
    ).where(PurchaseOrder.organization_id == org_id)
    if status:
        statement = statement.where(PurchaseOrder.status == status)
    orders = db.execute(statement.order_by(PurchaseOrder.ordered_at.desc()).limit(limit)).all()
    result = []
    for order, supplier in orders:
        lines = db.execute(
            select(PurchaseOrderItem, Product)
            .join(Product, Product.id == PurchaseOrderItem.product_id)
            .where(PurchaseOrderItem.purchase_order_id == order.id,
                   PurchaseOrderItem.organization_id == org_id)
        ).all()
        result.append(PurchaseDetailView(
            id=order.id, order_number=order.order_number, status=order.status,
            total=order.total, branch_id=order.branch_id, supplier_id=order.supplier_id,
            supplier_name=supplier.name, ordered_at=order.ordered_at,
            expected_at=order.expected_at,
            items=[PurchaseLineView(
                id=line.id, product_id=product.id, sku=product.sku,
                product_name=product.name, quantity=line.quantity,
                received_quantity=line.received_quantity, unit_cost=line.unit_cost,
            ) for line, product in lines],
        ))
    return result


@router.post("/purchases/{purchase_id}/receive", response_model=PurchaseView, tags=["purchases"])
def receive_purchase(
    purchase_id: str, payload: PurchaseReceive, membership: CurrentMembership,
    actor: CurrentUser, db: Db,
):
    require_role(membership, "owner", "manager")
    org_id = membership.organization_id
    order = db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == purchase_id, PurchaseOrder.organization_id == org_id
    ).with_for_update())
    if order is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    item_ids = [r.purchase_order_item_id for r in payload.items]
    items = {i.id: i for i in db.scalars(select(PurchaseOrderItem).where(
        PurchaseOrderItem.organization_id == org_id,
        PurchaseOrderItem.purchase_order_id == order.id,
        PurchaseOrderItem.id.in_(item_ids),
    ).with_for_update())}
    if len(items) != len(set(item_ids)):
        raise HTTPException(status_code=404, detail="One or more purchase lines were not found")
    received_value = Decimal("0")
    for received in payload.items:
        item = items[received.purchase_order_item_id]
        if item.received_quantity + received.quantity > item.quantity:
            raise HTTPException(status_code=409, detail="Received quantity exceeds ordered quantity")
        balance = db.scalar(select(InventoryBalance).where(
            InventoryBalance.organization_id == org_id,
            InventoryBalance.branch_id == order.branch_id,
            InventoryBalance.product_id == item.product_id,
        ).with_for_update())
        if balance is None:
            balance = InventoryBalance(
                organization_id=org_id, branch_id=order.branch_id,
                product_id=item.product_id, quantity=0,
            )
            db.add(balance)
        balance.quantity += received.quantity
        item.received_quantity += received.quantity
        received_value += received.quantity * item.unit_cost
        db.add(StockMovement(
            organization_id=org_id, branch_id=order.branch_id, product_id=item.product_id,
            movement_type="purchase_receipt", quantity_delta=received.quantity,
            unit_cost=item.unit_cost, reference_type="purchase_order",
            reference_id=order.id, occurred_at=payload.received_at,
        ))
    all_items = list(db.scalars(select(PurchaseOrderItem).where(
        PurchaseOrderItem.purchase_order_id == order.id
    )))
    order.status = "received" if all(i.received_quantity == i.quantity for i in all_items) else "partial"
    received_value = received_value.quantize(MONEY, rounding=ROUND_HALF_UP)
    db.add_all([
        LedgerEntry(
            organization_id=org_id, branch_id=order.branch_id, ledger_type="payable",
            party_type="supplier", party_id=order.supplier_id, amount_delta=received_value,
            reference_type="purchase_receipt", reference_id=order.id,
            occurred_at=payload.received_at,
        ),
        AuditLog(
            organization_id=org_id, actor_user_id=actor.id, action="purchase.received",
            entity_type="purchase_order", entity_id=order.id,
        ),
    ])
    db.commit()
    return order


@router.post("/suppliers/{supplier_id}/payments", tags=["ledger"])
def pay_supplier(
    supplier_id: str, payload: SettlementCreate, membership: CurrentMembership, db: Db,
):
    require_role(membership, "owner", "accountant")
    org_id = membership.organization_id
    if db.scalar(select(Supplier.id).where(Supplier.id == supplier_id, Supplier.organization_id == org_id)) is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    current = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "payable",
        LedgerEntry.party_id == supplier_id,
    ))
    if payload.amount > current:
        raise HTTPException(status_code=409, detail="Payment exceeds supplier payable")
    entry = LedgerEntry(
        organization_id=org_id, ledger_type="payable", party_type="supplier",
        party_id=supplier_id, amount_delta=-payload.amount,
        payment_method=payload.payment_method, reference_type="supplier_payment",
        reference_id=supplier_id, note=payload.note, occurred_at=payload.occurred_at,
    )
    db.add(entry)
    db.commit()
    return {"balance": current - payload.amount}


@router.post("/customers/{customer_id}/payments", tags=["ledger"])
def receive_customer_payment(
    customer_id: str, payload: SettlementCreate, membership: CurrentMembership, db: Db,
):
    require_role(membership, "owner", "manager", "accountant", "cashier")
    org_id = membership.organization_id
    if db.scalar(select(Customer.id).where(
        Customer.id == customer_id, Customer.organization_id == org_id
    )) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    current = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
        LedgerEntry.party_id == customer_id,
    ))
    if payload.amount > current:
        raise HTTPException(status_code=409, detail="Payment exceeds customer receivable")
    db.add(LedgerEntry(
        organization_id=org_id, ledger_type="receivable", party_type="customer",
        party_id=customer_id, amount_delta=-payload.amount,
        payment_method=payload.payment_method, reference_type="customer_payment",
        reference_id=customer_id, note=payload.note, occurred_at=payload.occurred_at,
    ))
    db.commit()
    return {"balance": current - payload.amount}


@router.post("/sales/{sale_id}/returns", response_model=ReturnView, tags=["returns"])
def create_return(
    sale_id: str, payload: ReturnCreate, membership: CurrentMembership,
    actor: CurrentUser, db: Db,
):
    require_role(membership, "owner", "manager", "cashier")
    org_id = membership.organization_id
    sale = db.scalar(select(SalesOrder).where(
        SalesOrder.id == sale_id, SalesOrder.organization_id == org_id
    ).with_for_update())
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    ids = [r.sales_order_item_id for r in payload.items]
    lines = {line.id: line for line in db.scalars(select(SalesOrderItem).where(
        SalesOrderItem.organization_id == org_id, SalesOrderItem.order_id == sale.id,
        SalesOrderItem.id.in_(ids),
    ).with_for_update())}
    if len(lines) != len(set(ids)):
        raise HTTPException(status_code=404, detail="One or more sale lines were not found")
    calculated = []
    total = Decimal("0")
    for returned in payload.items:
        line = lines[returned.sales_order_item_id]
        if line.returned_quantity + returned.quantity > line.quantity:
            raise HTTPException(status_code=409, detail="Return exceeds sold quantity")
        unit_net = line.line_total / line.quantity
        amount = (unit_net * returned.quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
        total += amount
        calculated.append((returned, line, amount))
    return_doc = SalesReturn(
        organization_id=org_id, branch_id=sale.branch_id, sales_order_id=sale.id,
        return_number=payload.return_number, reason=payload.reason,
        returned_at=payload.returned_at, total=total,
    )
    db.add(return_doc)
    try:
        db.flush()
        for returned, line, amount in calculated:
            line.returned_quantity += returned.quantity
            db.add(SalesReturnItem(
                organization_id=org_id, sales_return_id=return_doc.id,
                sales_order_item_id=line.id, product_id=line.product_id,
                quantity=returned.quantity, amount=amount, restock=returned.restock,
            ))
            if returned.restock:
                balance = db.scalar(select(InventoryBalance).where(
                    InventoryBalance.organization_id == org_id,
                    InventoryBalance.branch_id == sale.branch_id,
                    InventoryBalance.product_id == line.product_id,
                ).with_for_update())
                if balance is None:
                    balance = InventoryBalance(
                        organization_id=org_id, branch_id=sale.branch_id,
                        product_id=line.product_id, quantity=0,
                    )
                    db.add(balance)
                balance.quantity += returned.quantity
                db.add(StockMovement(
                    organization_id=org_id, branch_id=sale.branch_id,
                    product_id=line.product_id, movement_type="sale_return",
                    quantity_delta=returned.quantity, reference_type="sales_return",
                    reference_id=return_doc.id, occurred_at=payload.returned_at,
                ))
        paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.organization_id == org_id, Payment.order_id == sale.id,
            Payment.status == "completed",
        ))
        prior_returns = db.scalar(select(func.coalesce(func.sum(SalesReturn.total), 0)).where(
            SalesReturn.organization_id == org_id, SalesReturn.sales_order_id == sale.id,
            SalesReturn.id != return_doc.id,
        ))
        outstanding_before = max(Decimal("0"), sale.total - paid - prior_returns)
        due_reduction = min(total, outstanding_before) if sale.customer_id else Decimal("0")
        if total > due_reduction and not payload.refund_method:
            raise HTTPException(
                status_code=422,
                detail="A refund method is required for the already-paid return amount",
            )
        if due_reduction:
            db.add(LedgerEntry(
                organization_id=org_id, branch_id=sale.branch_id, ledger_type="receivable",
                party_type="customer", party_id=sale.customer_id, amount_delta=-due_reduction,
                reference_type="sales_return", reference_id=return_doc.id,
                occurred_at=payload.returned_at,
            ))
        refund_amount = (total - due_reduction) if payload.refund_method else Decimal("0")
        if refund_amount:
            db.add(Refund(
                organization_id=org_id, sales_return_id=return_doc.id,
                method=payload.refund_method, amount=refund_amount,
                refunded_at=payload.returned_at,
            ))
        db.add(AuditLog(
            organization_id=org_id, actor_user_id=actor.id, action="sale.returned",
            entity_type="sales_return", entity_id=return_doc.id,
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Return number already exists exists") from exc
    return ReturnView(
        id=return_doc.id, return_number=return_doc.return_number,
        total=total, refund_amount=refund_amount,
    )


@router.get("/returns", response_model=list[ReturnHistoryView], tags=["returns"])
def list_returns(
    membership: CurrentMembership, db: Db,
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = db.execute(
        select(SalesReturn, SalesOrder.invoice_number)
        .join(SalesOrder, SalesOrder.id == SalesReturn.sales_order_id)
        .where(SalesReturn.organization_id == membership.organization_id)
        .order_by(SalesReturn.returned_at.desc()).limit(limit)
    ).all()
    return [ReturnHistoryView(
        id=item.id, return_number=item.return_number, invoice_number=invoice,
        reason=item.reason, returned_at=item.returned_at, total=item.total,
    ) for item, invoice in rows]


@router.post("/expenses", response_model=ExpenseView, tags=["ledger"])
def create_expense(payload: ExpenseCreate, membership: CurrentMembership, db: Db):
    require_role(membership, "owner", "manager", "accountant")
    org_id = membership.organization_id
    if payload.branch_id and db.scalar(select(Branch.id).where(
        Branch.id == payload.branch_id, Branch.organization_id == org_id
    )) is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    expense = Expense(organization_id=org_id, **payload.model_dump())
    db.add(expense)
    db.flush()
    db.add(LedgerEntry(
        organization_id=org_id, branch_id=payload.branch_id, ledger_type="expense",
        category=payload.category, amount_delta=payload.amount,
        payment_method=payload.payment_method, reference_type="expense",
        reference_id=expense.id, note=payload.note, occurred_at=payload.incurred_at,
    ))
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/expenses", response_model=list[ExpenseView], tags=["ledger"])
def list_expenses(
    membership: CurrentMembership, db: Db,
    limit: int = Query(default=100, ge=1, le=500),
):
    return list(db.scalars(select(Expense).where(
        Expense.organization_id == membership.organization_id
    ).order_by(Expense.incurred_at.desc()).limit(limit)))


@router.get("/ledger/{ledger_type}", response_model=list[LedgerBalanceView], tags=["ledger"])
def ledger_balances(ledger_type: str, membership: CurrentMembership, db: Db):
    if ledger_type not in {"payable", "receivable", "expense"}:
        raise HTTPException(status_code=404, detail="Unknown ledger type")
    rows = db.execute(select(
        LedgerEntry.party_id, func.sum(LedgerEntry.amount_delta)
    ).where(
        LedgerEntry.organization_id == membership.organization_id,
        LedgerEntry.ledger_type == ledger_type,
    ).group_by(LedgerEntry.party_id)).all()
    return [LedgerBalanceView(party_id=party, balance=balance) for party, balance in rows]
