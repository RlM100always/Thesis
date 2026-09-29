"""Tenant-safe catalog, inventory, and point-of-sale endpoints."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .accounting import Line, account_for_method, post_journal
from .app_schemas import (
    InventoryView, ProductCreate, ProductUpdate, ProductView, SaleCreate, SaleDetailView,
    SaleLineView, SaleView, StockAdjustment,
)
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .batches import (
    InsufficientSellableStock, add_to_batch, allocate_fefo, balance_row, blended_cost,
    get_or_create_batch, remove_from_batch,
)
from .domain_models import (
    AuditLog, Batch, Branch, Customer, InventoryBalance, LedgerEntry, Payment, Product,
    SaleItemBatch, SalesOrder, SalesOrderItem, StockMovement, utcnow,
)
from .audit import record_audit
from .permissions import require_permission
from .timeutil import day_bounds

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]
MONEY = Decimal("0.01")
ZERO = Decimal("0")


def _adjust_tracked(db, org_id: str, branch, product, payload) -> Batch:
    """Adjust an expiry-tracked product: always against a named batch."""
    def find(batch_id: str) -> Batch:
        batch = db.scalar(select(Batch).where(
            Batch.id == batch_id, Batch.organization_id == org_id, Batch.product_id == product.id))
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        return batch

    if payload.quantity_delta < 0:
        if not payload.batch_id:
            raise HTTPException(status_code=422, detail="Choose the batch to take stock from")
        batch = find(payload.batch_id)
        remove_from_batch(db, org_id, branch.id, batch, -payload.quantity_delta)
        return batch
    if payload.batch_id:
        batch = find(payload.batch_id)
    elif payload.batch_no and payload.expiry_date:
        batch = get_or_create_batch(
            db, org_id, product, payload.batch_no, payload.expiry_date,
            product.cost_price if product.cost_price > 0 else None, None, utcnow(), "adjustment",
        )
    else:
        raise HTTPException(status_code=422, detail="Give the batch number and expiry date")
    add_to_batch(db, org_id, branch.id, batch, payload.quantity_delta)
    return batch


@router.post("/products", response_model=ProductView, tags=["catalog"])
def create_product(payload: ProductCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "catalog:write")
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


@router.patch("/products/{product_id}", response_model=ProductView, tags=["catalog"])
def update_product(product_id: str, payload: ProductUpdate, membership: CurrentMembership, db: Db):
    """Change price, name, reorder level and so on. Price changes are written to the audit trail."""
    require_permission(membership, "catalog:write")
    product = db.scalar(select(Product).where(
        Product.id == product_id, Product.organization_id == membership.organization_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    changes = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field not in ("wholesale_price", "barcode", "category"):
            continue  # a required field cannot be blanked
        if isinstance(value, str):
            value = value.strip() or None
        before = getattr(product, field)
        if before != value:
            changes[field] = {"from": str(before) if before is not None else None, "to": str(value) if value is not None else None}
            setattr(product, field, value)
    if changes:
        record_audit(db, membership, "product.updated", "product", product.id, sku=product.sku, changes=changes)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=list[ProductView], tags=["catalog"])
def list_products(
    membership: CurrentMembership, db: Db,
    q: str = Query(default="", max_length=100), limit: int = Query(default=100, ge=1, le=500),
):
    require_permission(membership, "catalog:read")
    statement = select(Product).where(
        Product.organization_id == membership.organization_id, Product.active.is_(True)
    )
    if q:
        statement = statement.where(Product.name.ilike(f"%{q}%"))
    return list(db.scalars(statement.order_by(Product.name).limit(limit)))


@router.post("/inventory/adjust", response_model=InventoryView, tags=["inventory"])
def adjust_stock(payload: StockAdjustment, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "inventory:adjust")
    branch = db.scalar(select(Branch).where(
        Branch.id == payload.branch_id, Branch.organization_id == membership.organization_id
    ))
    product = db.scalar(select(Product).where(
        Product.id == payload.product_id, Product.organization_id == membership.organization_id
    ))
    if branch is None or product is None:
        raise HTTPException(status_code=404, detail="Branch or product not found")
    batch = None
    if product.track_expiry:
        batch = _adjust_tracked(db, membership.organization_id, branch, product, payload)
        balance = balance_row(db, membership.organization_id, branch.id, product.id)
    else:
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
        reference_id=None, batch_id=batch.id if batch else None,
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
    require_permission(membership, "inventory:read")
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
    require_permission(membership, "sales:create")
    org_id = membership.organization_id
    branch = db.scalar(select(Branch).where(Branch.id == payload.branch_id, Branch.organization_id == org_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    customer = None
    if payload.customer_id:
        customer = db.scalar(select(Customer).where(
            Customer.id == payload.customer_id, Customer.organization_id == org_id))
        if customer is None:
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
        if item.unit_price is not None:
            unit_price = item.unit_price
        elif customer is not None and customer.price_tier == "wholesale" and product.wholesale_price is not None:
            unit_price = product.wholesale_price
        else:
            unit_price = product.selling_price
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
    if customer is not None and customer.credit_limit is not None and total > paid:
        owed = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
            LedgerEntry.party_type == "customer", LedgerEntry.party_id == customer.id))
        if owed + (total - paid) > customer.credit_limit:
            raise HTTPException(status_code=409, detail=(
                f"Credit limit exceeded: owes {owed}, this sale adds {total - paid}, limit {customer.credit_limit}"))

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
    # Check the *total* wanted per product: two lines of the same item must not
    # each pass on their own and together oversell.
    wanted: dict[str, Decimal] = {}
    for item, product, _, _ in line_values:
        wanted[product.id] = wanted.get(product.id, Decimal("0")) + item.quantity
    for product_id, quantity in wanted.items():
        if balances[product_id].quantity < quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {products[product_id].sku}")

    order = SalesOrder(
        organization_id=org_id, branch_id=branch.id, customer_id=payload.customer_id,
        invoice_number=payload.invoice_number, sold_at=payload.sold_at,
        channel=payload.channel, status="completed", subtotal=subtotal,
        discount_amount=discount_total, tax_amount=payload.tax_amount, total=total,
    )
    db.add(order)
    try:
        db.flush()
        sale_day = payload.sold_at.date()
        cogs_total = ZERO
        for item, product, unit_price, line_total in line_values:
            balances[product.id].quantity -= item.quantity
            unit_cost = product.cost_price
            plan = []
            if product.track_expiry:
                # First-expiry-first-out; expired and blocked batches are never sold.
                try:
                    plan = allocate_fefo(db, org_id, branch.id, product.id, item.quantity, sale_day)
                except InsufficientSellableStock as exc:
                    detail = f"Insufficient sellable stock for {product.sku}"
                    if exc.unsellable:
                        detail += f" ({exc.unsellable} units are expired or blocked)"
                    raise HTTPException(status_code=409, detail=detail) from exc
                unit_cost = blended_cost(plan, product.cost_price)
            cogs_total += unit_cost * item.quantity
            line = SalesOrderItem(
                organization_id=org_id, order_id=order.id, product_id=product.id,
                quantity=item.quantity, unit_price=unit_price,
                unit_cost_at_sale=unit_cost,
                discount_amount=item.discount_amount, line_total=line_total,
            )
            db.add(line)
            if not plan:
                db.add(StockMovement(
                    organization_id=org_id, branch_id=branch.id, product_id=product.id,
                    movement_type="sale", quantity_delta=-item.quantity,
                    unit_cost=unit_cost, reference_type="sales_order",
                    reference_id=order.id, occurred_at=payload.sold_at,
                ))
                continue
            db.flush()  # the line needs its id before batches can point at it
            for batch, stock, take in plan:
                stock.quantity -= take
                db.add_all([
                    SaleItemBatch(
                        organization_id=org_id, sales_order_item_id=line.id,
                        batch_id=batch.id, quantity=take,
                    ),
                    StockMovement(
                        organization_id=org_id, branch_id=branch.id, product_id=product.id,
                        movement_type="sale", quantity_delta=-take, batch_id=batch.id,
                        unit_cost=batch.unit_cost if batch.unit_cost is not None else product.cost_price,
                        reference_type="sales_order", reference_id=order.id,
                        occurred_at=payload.sold_at,
                    ),
                ])
            db.flush()  # later lines of the same product must see these units gone
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
        journal_lines = [
            Line(account_for_method(p.method), p.amount, ZERO) for p in payload.payments
        ]
        if total > paid:
            journal_lines.append(Line("1100", total - paid, ZERO, "customer", payload.customer_id))
        if subtotal - discount_total > 0:
            journal_lines.append(Line("4000", ZERO, subtotal - discount_total))
        if payload.tax_amount > 0:
            journal_lines.append(Line("2100", ZERO, payload.tax_amount))
        if cogs_total > 0:
            journal_lines += [Line("5000", cogs_total, ZERO), Line("1200", ZERO, cogs_total)]
        if journal_lines:
            post_journal(db, org_id, branch.id, payload.sold_at, "sales_order", order.id, journal_lines,
                         memo=f"Sale {order.invoice_number}")
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
    q: str | None = Query(default=None, max_length=80), customer_id: str | None = None,
    date_from: date | None = None, date_to: date | None = None,
):
    """Recent invoices with returnable line identifiers and payment state."""
    require_permission(membership, "sales:read")
    org_id = membership.organization_id
    statement = select(SalesOrder).where(SalesOrder.organization_id == org_id)
    if branch_id:
        statement = statement.where(SalesOrder.branch_id == branch_id)
    if customer_id:
        statement = statement.where(SalesOrder.customer_id == customer_id)
    if q:
        statement = statement.where(SalesOrder.invoice_number.ilike(f"%{q}%"))
    if date_from:
        statement = statement.where(SalesOrder.sold_at >= day_bounds(date_from)[0])
    if date_to:
        statement = statement.where(SalesOrder.sold_at < day_bounds(date_to)[1])
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
