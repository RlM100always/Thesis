"""Quotation → order → delivery → invoice workflow for SME sales.

Also hosts the public online-storefront checkout (``public_router``): an
unauthenticated buyer places an order against ``SalesDocument`` the same way
a staff-created order does, just entering at ``status="placed"`` instead of
``"confirmed"`` so an owner has to look at it before it is treated as a real
commitment. It reuses the existing quotation/order/invoice machinery rather
than a parallel cart table, because an online order IS a sales document —
the only genuinely new thing it needs is a way for an anonymous buyer to
create one and check on it without a login.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .app_schemas import PublicOrderCreate, SaleCreate, SalesDocumentCreate, SalesDocumentInvoice
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .commerce_routes import create_sale
from .database import get_db
from .domain_models import Branch, Customer, InventoryBalance, Organization, Product, Reservation, SalesDocument, SalesDocumentLine, Store, StoreCustomer
from .domain_models import StoreCoupon
from .permissions import require_permission

router = APIRouter(prefix="/api/app/sales-documents")
public_router = APIRouter(prefix="/api/public/orders")
Db = Annotated[Session, Depends(get_db)]
MONEY = Decimal("0.01")

QUOTE_TRANSITIONS = {"draft": {"sent", "accepted", "rejected"}, "sent": {"accepted", "rejected"}}
# "placed" is the entry status for an order a customer placed themselves
# through the public storefront — it needs an owner/manager to look at it
# before it becomes "confirmed", unlike a staff-created order which starts
# life already confirmed (see ``create_document``). From "confirmed" on, an
# online order and a staff-created one follow the same lifecycle.
ORDER_TRANSITIONS = {
    "placed": {"confirmed", "cancelled"},
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
        "shipping_name": document.shipping_name, "shipping_phone": document.shipping_phone,
        "shipping_address": document.shipping_address,
        "is_online_order": document.access_token is not None,
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
def list_documents(membership: CurrentMembership, db: Db, document_type: str | None = Query(default=None),
                   channel: str | None = Query(default=None)):
    require_permission(membership, "orders:read")
    statement = select(SalesDocument).options(selectinload(SalesDocument.lines)).where(
        SalesDocument.organization_id == membership.organization_id)
    if document_type:
        statement = statement.where(SalesDocument.document_type == document_type)
    if channel:
        statement = statement.where(SalesDocument.channel == channel)
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
    if body.status == "cancelled":
        for reservation in db.scalars(select(Reservation).where(
            Reservation.sales_document_id == document.id, Reservation.status == "active",
        )):
            reservation.status = "released"
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
    # Release this order's own reservations first -- otherwise create_sale's
    # availability check would count them against the very sale meant to
    # consume them. On-hand stock is untouched either way; only the hold moves.
    active_reservations = db.scalars(select(Reservation).where(
        Reservation.sales_document_id == document.id, Reservation.status == "active",
    )).all()
    for reservation in active_reservations:
        reservation.status = "fulfilled"
    if active_reservations:
        db.commit()
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


# --------------------------------------------------------------------------
# Public online-storefront checkout. No membership, no X-Organization-ID — the
# organization is named in the URL and the buyer has no account. Only ever
# touches orders that already belong to ``organization_id``; this is the same
# unauthenticated-by-design trust boundary as ``/api/upload/{token}`` in
# ``api/routes.py``, not an oversight.
# --------------------------------------------------------------------------

def _public_view(document: SalesDocument, products: dict[str, Product]) -> dict:
    return {
        "id": document.id,
        "order_number": document.document_number,
        "access_token": document.access_token,
        "status": document.status,
        "payment_status": getattr(document, "payment_status", "pending"),
        "status_note": getattr(document, "status_note", None),
        "placed_at": document.issued_at,
        "shipping_name": document.shipping_name,
        "shipping_phone": document.shipping_phone,
        "shipping_address": document.shipping_address,
        "subtotal": document.subtotal, "tax_amount": document.tax_amount,
        "delivery_fee": getattr(document, "delivery_fee", Decimal("0")) or Decimal("0"),
        "discount_amount": getattr(document, "discount_amount", Decimal("0")) or Decimal("0"),
        "coupon_code": getattr(document, "coupon_code", None),
        "coupon_discount": float(getattr(document, "coupon_discount", 0) or 0),
        "total": document.total,
        "organization_id": document.organization_id,
        "items": [{
            "product_name": products[line.product_id].name,
            "quantity": line.quantity, "unit_price": line.unit_price, "line_total": line.line_total,
            "variant_label": getattr(line, "variant_label", None),
        } for line in document.lines],
    }


@public_router.get("/{organization_id}/products", tags=["public-orders"])
def public_catalog(organization_id: str, db: Db):
    """The minimal, honest product list a public storefront can show: id,
    name, SKU, unit and the current selling price. No stock-level claim is
    made here — this endpoint has no branch context, and a wrong "in stock"
    promise is worse than none; out-of-stock lines are instead caught at
    checkout when the order is confirmed against a specific branch."""
    if db.scalar(select(Organization.id).where(Organization.id == organization_id)) is None:
        raise HTTPException(status_code=404, detail="Store not found")
    products = db.scalars(select(Product).where(
        Product.organization_id == organization_id, Product.active.is_(True)).order_by(Product.name))
    return [{
        "id": p.id, "name": p.name, "sku": p.sku, "unit": p.unit, "selling_price": p.selling_price,
    } for p in products]


@public_router.post("/{organization_id}", tags=["public-orders"])
def place_public_order(organization_id: str, payload: PublicOrderCreate, db: Db):
    if db.scalar(select(Organization.id).where(Organization.id == organization_id)) is None:
        raise HTTPException(status_code=404, detail="Store not found")
    if payload.branch_id:
        branch = db.scalar(select(Branch).where(
            Branch.id == payload.branch_id, Branch.organization_id == organization_id, Branch.active.is_(True)))
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found")
    else:
        branch = db.scalar(select(Branch).where(
            Branch.organization_id == organization_id, Branch.active.is_(True)).order_by(Branch.code).limit(1))
        if branch is None:
            raise HTTPException(status_code=409, detail="This store has no active branch to deliver from")

    product_ids = [item.product_id for item in payload.items]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(status_code=422, detail="Duplicate product lines must be combined")
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.organization_id == organization_id, Product.id.in_(product_ids), Product.active.is_(True)))}
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="One or more products were not found")

    subtotal = Decimal("0"); lines = []
    for item in payload.items:
        product = products[item.product_id]
        # Use online_price or sale_price from StoreProduct if available
        from .domain_models import StoreProduct as _SP
        sp = db.scalar(select(_SP).join(Store, _SP.store_id == Store.id).where(
            Store.organization_id == organization_id, _SP.product_id == item.product_id
        ))
        from datetime import datetime as _dt, timezone as _tz
        base_price = product.selling_price
        if sp:
            if sp.online_price_bdt is not None:
                base_price = sp.online_price_bdt
            # Apply active flash sale price
            if sp.sale_price is not None:
                _now = _dt.now(_tz.utc).isoformat()
                _start_ok = (not sp.sale_start) or sp.sale_start <= _now
                _end_ok   = (not sp.sale_end)   or sp.sale_end   >= _now
                if _start_ok and _end_ok:
                    base_price = sp.sale_price
        gross = (base_price * item.quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
        subtotal += gross
        lines.append((item, base_price, gross))

    # Stock validation
    for item in payload.items:
        balance = db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.organization_id == organization_id,
                InventoryBalance.product_id == item.product_id,
            )
        ) or Decimal("0")
        if Decimal(str(balance)) < Decimal(str(item.quantity)):
            product_name = products[item.product_id].name
            raise HTTPException(status_code=422, detail=f"দুঃখিত, '{product_name}' এর পর্যাপ্ত স্টক নেই")

    # Delivery fee calculation
    store = db.scalar(select(Store).where(Store.organization_id == organization_id))
    delivery_fee = Decimal("0")
    if store:
        division = getattr(payload, "delivery_division", None)
        if store.allow_zone_restriction and store.allowed_divisions and division:
            allowed = [d.strip() for d in store.allowed_divisions.split(",")]
            if division not in allowed:
                raise HTTPException(status_code=422, detail="দুঃখিত, এই এলাকায় ডেলিভারি দেওয়া সম্ভব নয়")
        if store.delivery_free_above and subtotal >= store.delivery_free_above:
            delivery_fee = Decimal("0")
        elif division and "ঢাকা" in division:
            delivery_fee = Decimal(str(store.delivery_inside_dhaka or 0))
        elif division:
            delivery_fee = Decimal(str(store.delivery_outside_dhaka or store.delivery_inside_dhaka or 0))
        else:
            delivery_fee = Decimal(str(store.delivery_inside_dhaka or 0))

    # Coupon validation (no side-effects yet; decrement after commit)
    coupon_discount = Decimal("0")
    coupon_obj = None
    if payload.coupon_code:
        from datetime import timezone as _tzc
        _now = datetime.now(_tzc.utc)
        coupon_obj = db.scalar(
            select(StoreCoupon).where(
                StoreCoupon.organization_id == organization_id,
                StoreCoupon.code == payload.coupon_code.upper(),
                StoreCoupon.is_active.is_(True),
            )
        )
        if coupon_obj:
            _ok = True
            if coupon_obj.valid_from and coupon_obj.valid_from > _now:
                _ok = False
            if coupon_obj.valid_to and coupon_obj.valid_to < _now:
                _ok = False
            if coupon_obj.max_uses is not None and coupon_obj.used_count >= coupon_obj.max_uses:
                _ok = False
            if subtotal < coupon_obj.min_order_bdt:
                _ok = False
            if _ok:
                if coupon_obj.discount_type == "percent":
                    coupon_discount = (subtotal * coupon_obj.discount_value / 100).quantize(MONEY)
                else:
                    coupon_discount = min(coupon_obj.discount_value, subtotal)

    total = (subtotal + delivery_fee - coupon_discount).quantize(MONEY)
    if total < Decimal("0"):
        total = Decimal("0")

    # Resolve optional store-customer JWT → link order to account
    sc_id: str | None = None
    if getattr(payload, "store_customer_token", None):
        try:
            from .store_customer_routes import _decode as _sc_decode
            from .domain_models import StoreCustomer as _SC
            _claims = _sc_decode(payload.store_customer_token)
            _sc = db.get(_SC, _claims["sub"])
            if _sc and _sc.is_active and _sc.token_version == _claims.get("tv", 0):
                sc_id = _sc.id
        except Exception:
            pass  # invalid token → place as guest

    screenshot_url = getattr(payload, "payment_screenshot", None)
    pay_status = "screenshot_uploaded" if screenshot_url else "pending"

    # Referral: if sc has a referral credit coming (referred_by set), apply ৳50 bonus
    referral_discount = Decimal("0")
    referral_applied = False
    if sc_id:
        sc_obj = db.get(StoreCustomer, sc_id)
        if sc_obj and sc_obj.referred_by and total > Decimal("200"):
            referral_discount = Decimal("50")
            referral_applied = True
            total = max(Decimal("0"), total - referral_discount)

    # Both the order number and the lookup token are generated server-side and
    # retried on collision, since an anonymous buyer supplies neither.
    for _ in range(5):
        document = SalesDocument(
            organization_id=organization_id, branch_id=branch.id, customer_id=None,
            document_type="order", document_number=f"WEB-{secrets.token_hex(5).upper()}",
            status="placed", channel="online", issued_at=datetime.now(),
            notes=(f"[{payload.payment_method.upper()}] " if payload.payment_method else "") + (payload.notes or ""),
            subtotal=subtotal, discount_amount=coupon_discount + referral_discount,
            tax_amount=Decimal("0"), total=total,
            shipping_name=payload.shipping_name, shipping_phone=payload.shipping_phone,
            shipping_address=payload.shipping_address, access_token=secrets.token_urlsafe(24),
            store_customer_id=sc_id,
            delivery_fee=delivery_fee,
            payment_status=pay_status,
            payment_screenshot_url=screenshot_url,
            coupon_code=coupon_obj.code if coupon_obj else None,
            coupon_discount=coupon_discount,
        )
        db.add(document)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        for item, price, line_total in lines:
            db.add(SalesDocumentLine(
                organization_id=organization_id, document_id=document.id, product_id=item.product_id,
                quantity=item.quantity, unit_price=price, discount_amount=Decimal("0"), line_total=line_total,
                variant_label=getattr(item, "variant_label", None),
            ))
        db.commit(); db.refresh(document)
        # Increment coupon usage
        if coupon_obj:
            coupon_obj.used_count = (coupon_obj.used_count or 0) + 1
            db.commit()
        # Clear referral credit (one-time use)
        if referral_applied and sc_obj:
            sc_obj.referred_by = None
            db.commit()
        break
    else:
        raise HTTPException(status_code=500, detail="Could not allocate an order number, try again")

    document = _load(db, organization_id, document.id)
    result = _public_view(document, products)

    # WhatsApp notification to the owning ORGANIZATION's number, not a missing Store.phone attribute.
    owner_phone = db.scalar(select(Organization.phone).where(Organization.id == organization_id))
    if store and owner_phone:
        import urllib.parse
        msg = f"নতুন অর্ডার #{document.document_number} — {payload.shipping_name} ({payload.shipping_phone}) — ৳{float(total):.0f}"
        phone_digits = "".join(ch for ch in owner_phone if ch.isdigit())
        result["whatsapp_notify_url"] = (f"https://wa.me/{phone_digits}?text={urllib.parse.quote(msg)}"
                                         if phone_digits else None)
    else:
        result["whatsapp_notify_url"] = None

    result["coupon_applied"] = coupon_discount > 0
    result["coupon_discount"] = float(coupon_discount)
    result["referral_discount"] = float(referral_discount)

    return result


@public_router.get("/{organization_id}/status/{access_token}", tags=["public-orders"])
def public_order_status(organization_id: str, access_token: str, db: Db):
    document = db.scalar(select(SalesDocument).options(selectinload(SalesDocument.lines)).where(
        SalesDocument.organization_id == organization_id, SalesDocument.access_token == access_token))
    if document is None:
        raise HTTPException(status_code=404, detail="Order not found")
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.id.in_({l.product_id for l in document.lines} or {""})))}
    return _public_view(document, products)


class PublicScreenshotIn(BaseModel):
    screenshot: str  # base64 data URL


@public_router.post("/{organization_id}/cancel/{access_token}", tags=["public-orders"])
def cancel_public_order(organization_id: str, access_token: str, db: Db):
    document = db.scalar(select(SalesDocument).options(selectinload(SalesDocument.lines)).where(
        SalesDocument.organization_id == organization_id, SalesDocument.access_token == access_token))
    if document is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if document.status != "placed":
        raise HTTPException(status_code=409, detail="শুধু 'placed' অবস্থায় থাকা অর্ডার বাতিল করা যাবে")
    document.status = "cancelled"
    db.commit()
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.id.in_({l.product_id for l in document.lines} or {""})))}
    return _public_view(document, products)


@public_router.post("/{organization_id}/payment-screenshot/{access_token}", tags=["public-orders"])
def upload_payment_screenshot(organization_id: str, access_token: str, body: PublicScreenshotIn, db: Db):
    document = db.scalar(select(SalesDocument).options(selectinload(SalesDocument.lines)).where(
        SalesDocument.organization_id == organization_id, SalesDocument.access_token == access_token))
    if document is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if document.status in ("cancelled", "delivered"):
        raise HTTPException(status_code=409, detail="এই অর্ডারে পেমেন্ট স্ক্রিনশট যোগ করা যাবে না")
    document.payment_screenshot_url = body.screenshot
    document.payment_status = "screenshot_uploaded"
    db.commit()
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.id.in_({l.product_id for l in document.lines} or {""})))}
    return _public_view(document, products)
