"""Account-wide customer commerce: saved addresses, wishlist, carts and order history.

These endpoints are deliberately separate from staff authentication. Every
record is scoped to the signed-in StoreCustomer and, where relevant, a real
active storefront. Prices are read from the server catalogue; the cart never
sets order prices.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .domain_models import (
    Product, SalesDocument, Store, StoreCustomer, StoreCustomerAddress,
    StoreCustomerCartItem, StoreCustomerWishlistItem, StoreProduct,
)
from .security import hash_password, verify_password
from .store_customer_routes import _customer_view, _decode, _get_customer, _issue, _order_view

router = APIRouter(prefix="/api/sc", tags=["store-customer-commerce"])
Db = Annotated[Session, Depends(get_db)]


class ScAddressCreate(BaseModel):
    label: str = Field(default="বাড়ি", min_length=1, max_length=40)
    recipient_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=20)
    division: str = Field(min_length=2, max_length=50)
    district: str = Field(min_length=2, max_length=50)
    thana: str | None = Field(default=None, max_length=80)
    address_detail: str = Field(min_length=3, max_length=400)
    postal_code: str | None = Field(default=None, max_length=12)
    is_default: bool = False


class ScAddressUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=40)
    recipient_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    division: str | None = Field(default=None, min_length=2, max_length=50)
    district: str | None = Field(default=None, min_length=2, max_length=50)
    thana: str | None = Field(default=None, max_length=80)
    address_detail: str | None = Field(default=None, min_length=3, max_length=400)
    postal_code: str | None = Field(default=None, max_length=12)
    is_default: bool | None = None


class ScWishlistAdd(BaseModel):
    store_slug: str = Field(min_length=3, max_length=80)
    product_id: str = Field(min_length=1, max_length=36)


class ScCartLine(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(ge=1, le=99)
    variant_label: str | None = Field(default=None, max_length=100)


class ScCartReplace(BaseModel):
    items: list[ScCartLine] = Field(max_length=50)


class ScPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def _address_view(a: StoreCustomerAddress) -> dict:
    return {
        "id": a.id, "label": a.label, "recipient_name": a.recipient_name,
        "phone": a.phone, "division": a.division, "district": a.district,
        "thana": a.thana, "address_detail": a.address_detail,
        "postal_code": a.postal_code, "is_default": bool(a.is_default),
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _store_for_customer(db: Session, slug: str) -> Store:
    store = db.scalar(select(Store).where(Store.slug == slug, Store.is_active.is_(True)))
    if store is None:
        raise HTTPException(status_code=404, detail="দোকানটি পাওয়া যায়নি বা বর্তমানে বন্ধ")
    return store


def _listed_product(db: Session, store: Store, product_id: str) -> tuple[Product, StoreProduct]:
    product = db.scalar(select(Product).where(
        Product.id == product_id, Product.organization_id == store.organization_id,
        Product.active.is_(True),
    ))
    listing = db.scalar(select(StoreProduct).where(
        StoreProduct.store_id == store.id, StoreProduct.product_id == product_id,
        StoreProduct.is_listed.is_(True),
    ))
    if product is None or listing is None:
        raise HTTPException(status_code=404, detail="পণ্যটি এই দোকানে উপলভ্য নয়")
    return product, listing


def _current_price(product: Product, listing: StoreProduct) -> Decimal:
    now = datetime.now(timezone.utc).isoformat()
    price = listing.online_price_bdt if listing.online_price_bdt is not None else product.selling_price
    if listing.sale_price is not None:
        start_ok = not listing.sale_start or listing.sale_start <= now
        end_ok = not listing.sale_end or listing.sale_end >= now
        if start_ok and end_ok:
            price = listing.sale_price
    return Decimal(str(price))


def _set_default_address(db: Session, customer_id: str, keep_id: str | None = None) -> None:
    rows = db.scalars(select(StoreCustomerAddress).where(
        StoreCustomerAddress.customer_id == customer_id
    )).all()
    for row in rows:
        row.is_default = bool(keep_id and row.id == keep_id)


@router.get("/orders", tags=["customer-orders"])
def all_store_orders(
    status: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1, le=100000),
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    """Account-wide order history across every store, never phone-matched to strangers."""
    customer = _get_customer(authorization, db)
    query = select(SalesDocument).where(
        SalesDocument.document_type == "order",
        SalesDocument.store_customer_id == customer.id,
    )
    if status:
        allowed = {"placed", "confirmed", "ready", "processing", "dispatched", "shipped", "delivered", "cancelled"}
        if status not in allowed:
            raise HTTPException(status_code=422, detail="অর্ডারের অবস্থা সঠিক নয়")
        query = query.where(SalesDocument.status == status)
    total = db.query(SalesDocument.id).filter(
        SalesDocument.document_type == "order", SalesDocument.store_customer_id == customer.id
    )
    if status:
        total = total.filter(SalesDocument.status == status)
    total_count = total.count()
    per_page = 10
    docs = db.scalars(query.order_by(SalesDocument.issued_at.desc()).offset((page - 1) * per_page).limit(per_page)).all()
    org_ids = {d.organization_id for d in docs}
    stores = {
        s.organization_id: s
        for s in db.scalars(select(Store).where(Store.organization_id.in_(org_ids or {""}))).all()
    }
    orders = []
    for doc in docs:
        row = _order_view(doc, db)
        store = stores.get(doc.organization_id)
        row["store_slug"] = store.slug if store else None
        row["store_name"] = store.display_name if store else "দোকান"
        row["is_demo"] = bool(store and store.slug.startswith("demo-bsmart-"))
        orders.append(row)
    return {"total": total_count, "page": page, "per_page": per_page, "orders": orders}


@router.get("/addresses", tags=["customer-addresses"])
def list_addresses(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    rows = db.scalars(select(StoreCustomerAddress).where(
        StoreCustomerAddress.customer_id == customer.id
    ).order_by(StoreCustomerAddress.is_default.desc(), StoreCustomerAddress.created_at.desc())).all()
    return {"addresses": [_address_view(row) for row in rows]}


@router.post("/addresses", status_code=201, tags=["customer-addresses"])
def create_address(
    payload: ScAddressCreate,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    exists = db.scalar(select(StoreCustomerAddress.id).where(
        StoreCustomerAddress.customer_id == customer.id
    ).limit(1))
    address = StoreCustomerAddress(
        customer_id=customer.id, **payload.model_dump(),
        is_default=bool(payload.is_default or not exists),
    )
    db.add(address)
    db.flush()
    if address.is_default:
        _set_default_address(db, customer.id, address.id)
    db.commit()
    db.refresh(address)
    return _address_view(address)


@router.patch("/addresses/{address_id}", tags=["customer-addresses"])
def update_address(
    address_id: str,
    payload: ScAddressUpdate,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    address = db.scalar(select(StoreCustomerAddress).where(
        StoreCustomerAddress.id == address_id,
        StoreCustomerAddress.customer_id == customer.id,
    ))
    if address is None:
        raise HTTPException(status_code=404, detail="ঠিকানাটি পাওয়া যায়নি")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(address, field, value)
    db.flush()
    if updates.get("is_default") is True:
        _set_default_address(db, customer.id, address.id)
    elif updates.get("is_default") is False and address.is_default:
        address.is_default = False
        replacement = db.scalar(select(StoreCustomerAddress).where(
            StoreCustomerAddress.customer_id == customer.id,
            StoreCustomerAddress.id != address.id,
        ).order_by(StoreCustomerAddress.created_at.desc()))
        if replacement:
            replacement.is_default = True
    db.commit()
    db.refresh(address)
    return _address_view(address)


@router.delete("/addresses/{address_id}", tags=["customer-addresses"])
def delete_address(
    address_id: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    address = db.scalar(select(StoreCustomerAddress).where(
        StoreCustomerAddress.id == address_id,
        StoreCustomerAddress.customer_id == customer.id,
    ))
    if address is None:
        raise HTTPException(status_code=404, detail="ঠিকানাটি পাওয়া যায়নি")
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        replacement = db.scalar(select(StoreCustomerAddress).where(
            StoreCustomerAddress.customer_id == customer.id,
        ).order_by(StoreCustomerAddress.created_at.desc()))
        if replacement:
            replacement.is_default = True
    db.commit()
    return {"ok": True}


@router.get("/wishlist", tags=["customer-wishlist"])
def list_wishlist(
    store_slug: str | None = Query(default=None, max_length=80),
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    query = select(StoreCustomerWishlistItem).where(
        StoreCustomerWishlistItem.customer_id == customer.id
    ).order_by(StoreCustomerWishlistItem.created_at.desc())
    if store_slug:
        store = db.scalar(select(Store).where(Store.slug == store_slug))
        if store is None:
            raise HTTPException(status_code=404, detail="দোকানটি পাওয়া যায়নি")
        query = query.where(StoreCustomerWishlistItem.store_id == store.id)
    rows = db.scalars(query).all()
    items = []
    for row in rows:
        store = db.get(Store, row.store_id)
        if store is None or not store.is_active:
            continue
        product = db.get(Product, row.product_id)
        if product is None or not product.active:
            continue
        listing = db.scalar(select(StoreProduct).where(
            StoreProduct.store_id == store.id, StoreProduct.product_id == product.id,
            StoreProduct.is_listed.is_(True),
        ))
        if listing is None:
            continue
        price = _current_price(product, listing)
        items.append({
            "id": row.id, "store_id": store.id, "store_slug": store.slug,
            "store_name": store.display_name, "organization_id": store.organization_id,
            "product_id": product.id, "product_name": product.name, "sku": product.sku,
            "price": float(price) if store.show_price else None,
            "image_data_url": listing.image_data_url, "description": listing.description_long or "",
            "tags": listing.tags.split(",") if listing.tags else [],
            "in_stock": True,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return {"items": items, "total": len(items)}


@router.post("/wishlist", status_code=201, tags=["customer-wishlist"])
def add_wishlist_item(
    payload: ScWishlistAdd,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = _store_for_customer(db, payload.store_slug)
    _listed_product(db, store, payload.product_id)
    item = db.scalar(select(StoreCustomerWishlistItem).where(
        StoreCustomerWishlistItem.customer_id == customer.id,
        StoreCustomerWishlistItem.store_id == store.id,
        StoreCustomerWishlistItem.product_id == payload.product_id,
    ))
    if item:
        return {"ok": True, "already_saved": True, "id": item.id}
    item = StoreCustomerWishlistItem(
        customer_id=customer.id, store_id=store.id, product_id=payload.product_id
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        item = db.scalar(select(StoreCustomerWishlistItem).where(
            StoreCustomerWishlistItem.customer_id == customer.id,
            StoreCustomerWishlistItem.store_id == store.id,
            StoreCustomerWishlistItem.product_id == payload.product_id,
        ))
        return {"ok": True, "already_saved": True, "id": item.id if item else None}
    db.refresh(item)
    return {"ok": True, "already_saved": False, "id": item.id}


@router.delete("/wishlist/{store_slug}/{product_id}", tags=["customer-wishlist"])
def remove_wishlist_item(
    store_slug: str,
    product_id: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if store is None:
        raise HTTPException(status_code=404, detail="দোকানটি পাওয়া যায়নি")
    item = db.scalar(select(StoreCustomerWishlistItem).where(
        StoreCustomerWishlistItem.customer_id == customer.id,
        StoreCustomerWishlistItem.store_id == store.id,
        StoreCustomerWishlistItem.product_id == product_id,
    ))
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}


@router.get("/cart/{store_slug}", tags=["customer-cart"])
def get_saved_cart(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = _store_for_customer(db, store_slug)
    rows = db.scalars(select(StoreCustomerCartItem).where(
        StoreCustomerCartItem.customer_id == customer.id,
        StoreCustomerCartItem.store_id == store.id,
    ).order_by(StoreCustomerCartItem.created_at)).all()
    items = []
    for row in rows:
        try:
            product, listing = _listed_product(db, store, row.product_id)
        except HTTPException:
            db.delete(row)
            continue
        items.append({
            "product_id": product.id, "quantity": row.quantity,
            "variant_label": row.variant_label, "product_name": product.name,
            "price": float(_current_price(product, listing)) if store.show_price else None,
            "image_data_url": listing.image_data_url,
        })
    db.commit()
    return {"store_slug": store.slug, "items": items}


@router.put("/cart/{store_slug}", tags=["customer-cart"])
def replace_saved_cart(
    store_slug: str,
    payload: ScCartReplace,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = _store_for_customer(db, store_slug)
    ids = [line.product_id for line in payload.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="একই পণ্য একাধিকবার না দিয়ে পরিমাণ একত্র করুন")
    checked = []
    for line in payload.items:
        product, listing = _listed_product(db, store, line.product_id)
        if listing.max_order_qty is not None and line.quantity > listing.max_order_qty:
            raise HTTPException(status_code=422, detail=f"{product.name}: সর্বোচ্চ {listing.max_order_qty}টি যোগ করা যাবে")
        checked.append(line)
    existing = db.scalars(select(StoreCustomerCartItem).where(
        StoreCustomerCartItem.customer_id == customer.id,
        StoreCustomerCartItem.store_id == store.id,
    )).all()
    for row in existing:
        db.delete(row)
    db.flush()
    for line in checked:
        db.add(StoreCustomerCartItem(
            customer_id=customer.id, store_id=store.id, product_id=line.product_id,
            quantity=line.quantity, variant_label=line.variant_label,
        ))
    db.commit()
    return {"ok": True, "items_count": len(checked)}


@router.delete("/cart/{store_slug}", tags=["customer-cart"])
def clear_saved_cart(
    store_slug: str,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    store = db.scalar(select(Store).where(Store.slug == store_slug))
    if store is None:
        raise HTTPException(status_code=404, detail="দোকানটি পাওয়া যায়নি")
    rows = db.scalars(select(StoreCustomerCartItem).where(
        StoreCustomerCartItem.customer_id == customer.id,
        StoreCustomerCartItem.store_id == store.id,
    )).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/password", tags=["customer-security"])
def change_password(
    payload: ScPasswordChange,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    if not customer.password_hash or not verify_password(payload.current_password, customer.password_hash):
        raise HTTPException(status_code=400, detail="বর্তমান পাসওয়ার্ড সঠিক নয়")
    if verify_password(payload.new_password, customer.password_hash):
        raise HTTPException(status_code=422, detail="নতুন পাসওয়ার্ডটি আগের পাসওয়ার্ড থেকে আলাদা হতে হবে")
    customer.password_hash = hash_password(payload.new_password)
    customer.token_version = int(customer.token_version or 0) + 1
    db.commit()
    db.refresh(customer)
    return {"token": _issue(customer.id, customer.token_version), "customer": _customer_view(customer)}


@router.post("/logout", tags=["customer-security"])
def revoke_customer_sessions(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    customer = _get_customer(authorization, db)
    customer.token_version = int(customer.token_version or 0) + 1
    db.commit()
    return {"ok": True, "message": "সব লগইন সেশন বন্ধ করা হয়েছে"}
