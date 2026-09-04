"""Tenant-safe catalog, inventory, and point-of-sale endpoints."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import (
    InventoryView, ProductCreate, ProductView, SaleCreate, SaleDetailView,
    SaleLineView, SaleView, StockAdjustment,
)
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import (
    AuditLog, Branch, Customer, InventoryBalance, LedgerEntry, Payment, Product, SalesOrder,
    SalesOrderItem, StockMovement,
)

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
MONEY = Decimal("0.01")


def require_role(membership, *allowed: str) -> None:
    if membership.role not in allowed:
        raise HTTPException(status_code=403, detail="Your role cannot perform this action")


@router.post("/products", response_model=ProductView, tags=["catalog"])
def create_product(payload: ProductCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_role(membership, "owner", "manager")
    product = Product(organization_id=membership.organization_id, **payload.model_dump())
    db.add(product)
    try:
        db.flush()
        db.add(AuditLog(
            organization_id=membership.organization_id, actor_user_id=user.id,
            action="product.created", entity_type="product", entity_id=product.id,
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="SKU already exists") from exc
    db.refresh(product)
    return product


@router.get("/products", response_model=list[ProductView], tags=["catalog"])
def list_products(
    membership: CurrentMembership, db: Db,
    q: str = Query(default="", max_length=100), limit: int = Query(default=100, ge=1, le=500),
):
    statement = select(Product).where(
        Product.organization_id == membership.organization_id, Product.active.is_(True)
    )
    if q:
        statement = statement.where(Product.name.ilike(f"%{q}%"))
    return list(db.scalars(statement.order_by(Product.name).limit(limit)))


@router.post("/inventory/adjust", response_model=InventoryView, tags=["inventory"])
def adjust_stock(payload: StockAdjustment, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_role(membership, "owner", "manager")
    branch = db.scalar(select(Branch).where(
        Branch.id == payload.branch_id, Branch.organization_id == membership.organization_id
    ))
    product = db.scalar(select(Product).where(
        Product.id == payload.product_id, Product.organization_id == membership.organization_id
    ))
    if branch is None or product is None:
        raise HTTPException(status_code=404, detail="Branch or product not found")
    balance = db.scalar(select(InventoryBalance).where(
        InventoryBalance.organization_id == membership.organization_id,
        InventoryBalance.branch_id == branch.id,
        InventoryBalance.product_id == product.id,
    ).with_for_update())
    if balance is None:
        balance = InventoryBalance(
            organization_id=membership.organization_id, branch_id=branch.id,
            product_id=product.id, quantity=Decimal("0"),
        )
        db.add(balance)
    new_quantity = balance.quantity + payload.quantity_delta
    if new_quantity < 0:
        raise HTTPException(status_code=409, detail="Adjustment would make stock negative")
    balance.quantity = new_quantity
    movement = StockMovement(
        organization_id=membership.organization_id, branch_id=branch.id,
        product_id=product.id, movement_type="adjustment",
        quantity_delta=payload.quantity_delta, reference_type="reason",
        reference_id=None,
    )
    db.add_all([movement, AuditLog(
        organization_id=membership.organization_id, actor_user_id=user.id,
        action="inventory.adjusted", entity_type="product", entity_id=product.id,
        metadata_json=payload.model_dump_json(),
    )])
    db.commit()
    return InventoryView(
        branch_id=branch.id, product_id=product.id, sku=product.sku,
        product_name=product.name, quantity=balance.quantity,
        reorder_level=product.reorder_level, low_stock=balance.quantity <= product.reorder_level,
    )


@router.get("/inventory", response_model=list[InventoryView], tags=["inventory"])
def inventory(membership: CurrentMembership, db: Db, branch_id: str):
    branch = db.scalar(select(Branch).where(
        Branch.id == branch_id, Branch.organization_id == membership.organization_id
    ))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    rows = db.execute(
        select(Product, InventoryBalance.quantity)
        .outerjoin(InventoryBalance, (
            (InventoryBalance.product_id == Product.id)
            & (InventoryBalance.branch_id == branch_id)
            & (InventoryBalance.organization_id == membership.organization_id)
        ))
        .where(Product.organization_id == membership.organization_id, Product.active.is_(True))
        .order_by(Product.name)
    ).all()
    return [InventoryView(
        branch_id=branch_id, product_id=p.id, sku=p.sku, product_name=p.name,
        quantity=qty or Decimal("0"), reorder_level=p.reorder_level,
        low_stock=(qty or Decimal("0")) <= p.reorder_level,
    ) for p, qty in rows]


@router.post("/sales", response_model=SaleView, tags=["sales"])
def create_sale(payload: SaleCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_role(membership, "owner", "manager", "cashier")
    org_id = membership.organization_id
    branch = db.scalar(select(Branch).where(Branch.id == payload.branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    if payload.customer_id and db.scalar(select(Customer.id).where(
        Customer.id == payload.customer_id, Customer.organization_id == org_id
    )) is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    product_ids = [item.product_id for item in payload.items]
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.id.in_(product_ids), Product.active.is_(True)
    ))}
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="One or more products were not found")

    line_values = []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    for item in payload.items:
        product = products[item.product_id]
        unit_price = item.unit_price if item.unit_price is not None else product.selling_price
        gross = (unit_price * item.quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
        if item.discount_amount > gross:
            raise HTTPException(status_code=422, detail=f"Discount exceeds gross for {product.sku}")
        line_total = gross - item.discount_amount
        subtotal += gross
        discount_total += item.discount_amount
        line_values.append((item, product, unit_price, line_total))
    total = (subtotal - discount_total + payload.tax_amount).quantize(MONEY)
    paid = sum((p.amount for p in payload.payments), Decimal("0"))
    if paid > total:
        raise HTTPException(status_code=422, detail="Payments exceed sale total")

    balances = {}
    for product_id in product_ids:
        balance = db.scalar(select(InventoryBalance).where(
            InventoryBalance.organization_id == org_id,
            InventoryBalance.branch_id == branch.id,
            InventoryBalance.product_id == product_id,
        ).with_for_update())
        if balance is None:
            raise HTTPException(status_code=409, detail=f"No stock available for {products[product_id].sku}")
        balances[product_id] = balance
    for item, product, _, _ in line_values:
        if balances[product.id].quantity < item.quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.sku}")

    order = SalesOrder(
        organization_id=org_id, branch_id=branch.id, customer_id=payload.customer_id,
        invoice_number=payload.invoice_number, sold_at=payload.sold_at,
        channel=payload.channel, status="completed", subtotal=subtotal,
        discount_amount=discount_total, tax_amount=payload.tax_amount, total=total,
    )
    db.add(order)
    try:
        db.flush()
        for item, product, unit_price, line_total in line_values:
            balances[product.id].quantity -= item.quantity
            db.add_all([
                SalesOrderItem(
                    organization_id=org_id, order_id=order.id, product_id=product.id,
                    quantity=item.quantity, unit_price=unit_price,
                    unit_cost_at_sale=product.cost_price,
                    discount_amount=item.discount_amount, line_total=line_total,
                ),
                StockMovement(
                    organization_id=org_id, branch_id=branch.id, product_id=product.id,
                    movement_type="sale", quantity_delta=-item.quantity,
                    unit_cost=product.cost_price, reference_type="sales_order",
                    reference_id=order.id, occurred_at=payload.sold_at,
                ),
            ])
        for payment in payload.payments:
            db.add(Payment(organization_id=org_id, order_id=order.id, **payment.model_dump()))
        if total > paid:
            if not payload.customer_id:
                raise HTTPException(status_code=422, detail="A customer is required for a due sale")
            db.add(LedgerEntry(
                organization_id=org_id, branch_id=branch.id, ledger_type="receivable",
                party_type="customer", party_id=payload.customer_id,
                amount_delta=total-paid, reference_type="sales_order",
                reference_id=order.id, occurred_at=payload.sold_at,
            ))
        db.add(AuditLog(
            organization_id=org_id, actor_user_id=user.id, action="sale.created",
            entity_type="sales_order", entity_id=order.id,
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invoice number already exists") from exc
    return SaleView(
        id=order.id, invoice_number=order.invoice_number, subtotal=subtotal,
        discount_amount=discount_total, tax_amount=payload.tax_amount, total=total,
        paid=paid, due=total-paid, status=order.status,
    )


@router.get("/sales", response_model=list[SaleDetailView], tags=["sales"])
def list_sales(
    membership: CurrentMembership, db: Db,
    branch_id: str | None = None, limit: int = Query(default=100, ge=1, le=500),
):
    """Recent invoices with returnable line identifiers and payment state."""
    org_id = membership.organization_id
    statement = select(SalesOrder).where(SalesOrder.organization_id == org_id)
    if branch_id:
        statement = statement.where(SalesOrder.branch_id == branch_id)
    orders = list(db.scalars(statement.order_by(SalesOrder.sold_at.desc()).limit(limit)))
    result = []
    for order in orders:
        rows = db.execute(
            select(SalesOrderItem, Product)
            .join(Product, Product.id == SalesOrderItem.product_id)
            .where(SalesOrderItem.order_id == order.id, SalesOrderItem.organization_id == org_id)
        ).all()
        paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.organization_id == org_id, Payment.order_id == order.id,
            Payment.status == "completed",
        ))
        items = [SaleLineView(
            id=line.id, product_id=product.id, sku=product.sku,
            product_name=product.name, quantity=line.quantity,
            returned_quantity=line.returned_quantity, unit_price=line.unit_price,
            line_total=line.line_total,
        ) for line, product in rows]
        result.append(SaleDetailView(
            id=order.id, invoice_number=order.invoice_number, branch_id=order.branch_id,
            customer_id=order.customer_id, sold_at=order.sold_at, channel=order.channel,
            subtotal=order.subtotal, discount_amount=order.discount_amount,
            tax_amount=order.tax_amount, total=order.total, paid=paid,
            due=max(Decimal("0"), order.total-paid), status=order.status, items=items,
        ))
    return result
