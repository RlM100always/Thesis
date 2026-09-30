"""Quotation → order → delivery → invoice workflow for SME sales."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .app_schemas import SaleCreate, SalesDocumentCreate, SalesDocumentInvoice
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .commerce_routes import create_sale
from .database import get_db
from .domain_models import Branch, Customer, Product, SalesDocument, SalesDocumentLine
from .permissions import require_permission

router = APIRouter(prefix="/api/app/sales-documents")
Db = Annotated[Session, Depends(get_db)]
MONEY = Decimal("0.01")

QUOTE_TRANSITIONS = {"draft": {"sent", "accepted", "rejected"}, "sent": {"accepted", "rejected"}}
ORDER_TRANSITIONS = {
    "confirmed": {"ready", "cancelled"}, "ready": {"dispatched", "cancelled"},
    "dispatched": {"delivered"}, "delivered": set(),
}


def _view(document: SalesDocument, products: dict[str, Product], customer_name: str | None = None) -> dict:
    return {
        "id": document.id, "document_type": document.document_type,
        "document_number": document.document_number, "status": document.status,
        "branch_id": document.branch_id, "customer_id": document.customer_id,
        "customer_name": customer_name, "channel": document.channel,
        "issued_at": document.issued_at, "valid_until": document.valid_until,
        "expected_delivery_at": document.expected_delivery_at, "notes": document.notes,
        "subtotal": document.subtotal, "discount_amount": document.discount_amount,
        "tax_amount": document.tax_amount, "total": document.total,
        "invoice_id": document.invoice_id,
        "items": [{
            "id": line.id, "product_id": line.product_id,
            "product_name": products[line.product_id].name,
            "sku": products[line.product_id].sku, "quantity": line.quantity,
            "unit_price": line.unit_price, "discount_amount": line.discount_amount,
            "line_total": line.line_total,
        } for line in document.lines],
    }


def _load(db: Session, org_id: str, document_id: str) -> SalesDocument:
    row = db.scalar(select(SalesDocument).options(selectinload(SalesDocument.lines)).where(
        SalesDocument.id == document_id, SalesDocument.organization_id == org_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Sales document not found")
    return row


@router.get("", tags=["sales-documents"])
def list_documents(membership: CurrentMembership, db: Db, document_type: str | None = Query(default=None)):
    require_permission(membership, "orders:read")
    statement = select(SalesDocument).options(selectinload(SalesDocument.lines)).where(
        SalesDocument.organization_id == membership.organization_id)
    if document_type:
        statement = statement.where(SalesDocument.document_type == document_type)
    documents = list(db.scalars(statement.order_by(SalesDocument.issued_at.desc()).limit(300)))
    product_ids = {line.product_id for document in documents for line in document.lines}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids or {""})))}
    customer_ids = {d.customer_id for d in documents if d.customer_id}
    customers = {c.id: c.display_name or c.code for c in db.scalars(select(Customer).where(Customer.id.in_(customer_ids or {""})))}
    return [_view(d, products, customers.get(d.customer_id)) for d in documents]


@router.post("", tags=["sales-documents"])
def create_document(payload: SalesDocumentCreate, membership: CurrentMembership, db: Db):
    require_permission(membership, "orders:create")
    org_id = membership.organization_id
    if db.scalar(select(Branch.id).where(Branch.id == payload.branch_id, Branch.organization_id == org_id)) is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    customer = None
    if payload.customer_id:
        customer = db.scalar(select(Customer).where(Customer.id == payload.customer_id, Customer.organization_id == org_id))
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
    product_ids = [item.product_id for item in payload.items]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(status_code=422, detail="Duplicate product lines must be combined")
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == org_id, Product.id.in_(product_ids), Product.active.is_(True)))}
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="One or more products were not found")
    subtotal = Decimal("0"); discounts = Decimal("0"); lines = []
    for item in payload.items:
        product = products[item.product_id]
        price = item.unit_price if item.unit_price is not None else (
            product.wholesale_price if customer and customer.price_tier == "wholesale" and product.wholesale_price is not None else product.selling_price)
        gross = (price * item.quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
        if item.discount_amount > gross:
            raise HTTPException(status_code=422, detail=f"Discount exceeds gross for {product.sku}")
        subtotal += gross; discounts += item.discount_amount
        lines.append((item, price, gross - item.discount_amount))
    total = (subtotal - discounts + payload.tax_amount).quantize(MONEY)
    document = SalesDocument(
        organization_id=org_id, branch_id=payload.branch_id, customer_id=payload.customer_id,
        document_type=payload.document_type, document_number=payload.document_number,
        status="draft" if payload.document_type == "quotation" else "confirmed",
        channel=payload.channel, issued_at=payload.issued_at, valid_until=payload.valid_until,
        expected_delivery_at=payload.expected_delivery_at, notes=payload.notes,
        subtotal=subtotal, discount_amount=discounts, tax_amount=payload.tax_amount, total=total,
    )
    db.add(document)
    try:
        db.flush()
        for item, price, line_total in lines:
            db.add(SalesDocumentLine(
                organization_id=org_id, document_id=document.id, product_id=item.product_id,
                quantity=item.quantity, unit_price=price, discount_amount=item.discount_amount,
                line_total=line_total,
            ))
        record_audit(db, membership, f"{payload.document_type}.created", "sales_document", document.id,
                     number=document.document_number, total=total)
        db.commit(); db.refresh(document)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Document number already exists") from exc
    document = _load(db, org_id, document.id)
    return _view(document, products, customer.display_name if customer else None)


class StatusIn(BaseModel):
    status: str = Field(max_length=20)


@router.post("/{document_id}/status", tags=["sales-documents"])
def change_status(document_id: str, body: StatusIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "orders:fulfill")
    document = _load(db, membership.organization_id, document_id)
    transitions = QUOTE_TRANSITIONS if document.document_type == "quotation" else ORDER_TRANSITIONS
    if body.status not in transitions.get(document.status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot move {document.status} to {body.status}")
    previous = document.status; document.status = body.status
    record_audit(db, membership, f"{document.document_type}.status_changed", "sales_document", document.id,
                 before=previous, after=body.status)
    db.commit()
    return {"id": document.id, "status": document.status}


class ConvertQuoteIn(BaseModel):
    order_number: str = Field(min_length=1, max_length=80)
    expected_delivery_at: datetime | None = None


@router.post("/{document_id}/convert-to-order", tags=["sales-documents"])
def convert_quote(document_id: str, body: ConvertQuoteIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "orders:create")
    quote = _load(db, membership.organization_id, document_id)
    if quote.document_type != "quotation" or quote.status not in {"draft", "sent", "accepted"}:
        raise HTTPException(status_code=409, detail="Only an active quotation can become an order")
    payload = SalesDocumentCreate(
        document_type="order", document_number=body.order_number, branch_id=quote.branch_id,
        customer_id=quote.customer_id, channel=quote.channel, issued_at=datetime.now(quote.issued_at.tzinfo),
        expected_delivery_at=body.expected_delivery_at, notes=f"Quotation {quote.document_number}\n{quote.notes or ''}".strip(),
        tax_amount=quote.tax_amount,
        items=[{"product_id": l.product_id, "quantity": l.quantity, "unit_price": l.unit_price,
                "discount_amount": l.discount_amount} for l in quote.lines],
    )
    order = create_document(payload, membership, db)
    quote = _load(db, membership.organization_id, document_id)
    quote.status = "converted"; db.commit()
    return order


@router.post("/{document_id}/invoice", tags=["sales-documents"])
def invoice_order(document_id: str, body: SalesDocumentInvoice, membership: CurrentMembership,
                  user: CurrentUser, db: Db):
    require_permission(membership, "orders:fulfill")
    document = _load(db, membership.organization_id, document_id)
    if document.document_type != "order" or document.status in {"cancelled", "invoiced"}:
        raise HTTPException(status_code=409, detail="This order cannot be invoiced")
    sale = create_sale(SaleCreate(
        branch_id=document.branch_id, customer_id=document.customer_id,
        invoice_number=body.invoice_number, sold_at=body.sold_at, channel=document.channel,
        tax_amount=document.tax_amount,
        items=[{"product_id": l.product_id, "quantity": l.quantity, "unit_price": l.unit_price,
                "discount_amount": l.discount_amount} for l in document.lines], payments=body.payments,
    ), membership, user, db)
    document = _load(db, membership.organization_id, document_id)
    document.status = "invoiced"; document.invoice_id = sale.id
    record_audit(db, membership, "order.invoiced", "sales_document", document.id, invoice_id=sale.id)
    db.commit()
    return sale
