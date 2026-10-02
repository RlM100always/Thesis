"""Store management and public storefront endpoints.

Two routers live here:
- ``public_router``  — unauthenticated, rate-limited endpoints that the
  public storefront page calls. Returns only what the owner chose to make
  visible; never exposes revenue, costs, exact addresses unless the owner
  toggled those on, or any data unrelated to the store's own products.
- ``router``         — owner/manager-only CRUD for store settings, product
  listings, and online order management.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .auth import CurrentMembership
from .database import get_db
from .domain_models import (
    Branch, Customer, InventoryBalance, Organization, Product,
    SalesDocument, Store, StoreProduct, utcnow,
)
from .permissions import require_permission

router = APIRouter(prefix="/api/app/store", tags=["store-admin"])
public_router = APIRouter(prefix="/api/public/store", tags=["public-store"])
Db = Annotated[Session, Depends(get_db)]

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,78}[a-z0-9]$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_store_or_404(db: Session, org_id: str) -> Store:
    row = db.scalar(select(Store).where(Store.organization_id == org_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Store not found. Activate it first.")
    return row


def _stock_status(db: Session, org_id: str, product_id: str, show_level: str) -> dict:
    if show_level == "hide":
        return {}
    balance = db.scalar(
        select(func.coalesce(func.sum(InventoryBalance.quantity_on_hand), 0)).where(
            InventoryBalance.organization_id == org_id,
            InventoryBalance.product_id == product_id,
        )
    ) or Decimal("0")
    available = balance > 0
    if show_level == "available_only":
        return {"in_stock": available}
    return {"in_stock": available, "quantity": float(balance)}


def _public_product(p: Product, sp: StoreProduct | None, store: Store, db: Session) -> dict:
    price = float(sp.online_price_bdt) if sp and sp.online_price_bdt is not None else float(p.selling_price)
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "unit": p.unit,
        "price": price if store.show_price else None,
        "description": (sp.description_long if sp and sp.description_long else p.description) or "",
        "image_data_url": sp.image_data_url if sp else None,
        "tags": (sp.tags.split(",") if sp and sp.tags else []),
        "is_featured": sp.is_featured if sp else False,
        "sort_order": sp.sort_order if sp else 0,
        "max_order_qty": sp.max_order_qty if sp else None,
        **_stock_status(db, p.organization_id, p.id, store.show_stock_level),
    }


def _store_public_view(store: Store, org: Organization) -> dict:
    return {
        "organization_id": store.organization_id,
        "slug": store.slug,
        "is_active": store.is_active,
        "display_name": store.display_name,
        "tagline": store.tagline,
        "logo_data_url": store.logo_data_url,
        "cover_data_url": store.cover_data_url,
        "theme_preset": store.theme_preset,
        "theme_color": store.theme_color,
        "category": store.category,
        "area": store.area,
        "phone": org.phone if store.show_phone else None,
        "address": org.address if store.show_exact_address else None,
        "show_hours": store.show_hours,
        "hours_json": json.loads(store.hours_json) if store.show_hours and store.hours_json else None,
        "show_price": store.show_price,
        "show_stock_level": store.show_stock_level,
        "payment_cod": store.payment_cod,
        "payment_bkash": store.payment_bkash,
        "payment_nagad": store.payment_nagad,
        "min_order_bdt": float(store.min_order_bdt) if store.min_order_bdt else None,
        "delivery_note": store.delivery_note,
        "meta_title": store.meta_title,
        "meta_desc": store.meta_desc,
    }


def _store_admin_view(store: Store) -> dict:
    return {
        "organization_id": store.organization_id,
        "slug": store.slug,
        "is_active": store.is_active,
        "display_name": store.display_name,
        "tagline": store.tagline,
        "logo_data_url": store.logo_data_url,
        "cover_data_url": store.cover_data_url,
        "theme_preset": store.theme_preset,
        "theme_color": store.theme_color,
        "category": store.category,
        "area": store.area,
        "show_phone": store.show_phone,
        "show_exact_address": store.show_exact_address,
        "show_hours": store.show_hours,
        "show_stock_level": store.show_stock_level,
        "show_price": store.show_price,
        "payment_cod": store.payment_cod,
        "payment_bkash": store.payment_bkash,
        "payment_nagad": store.payment_nagad,
        "min_order_bdt": float(store.min_order_bdt) if store.min_order_bdt else None,
        "delivery_note": store.delivery_note,
        "hours_json": json.loads(store.hours_json) if store.hours_json else None,
        "meta_title": store.meta_title,
        "meta_desc": store.meta_desc,
        "created_at": store.created_at,
    }


# ---------------------------------------------------------------------------
# Public endpoints — no auth required
# ---------------------------------------------------------------------------

@public_router.get("/{organization_id}", tags=["public-store"])
def get_public_store(organization_id: str, db: Db):
    """Return the store profile and listed products in one call.

    404 when the store does not exist or is_active=False — the storefront
    renders a "not found" page rather than an empty shell, so inactive stores
    are genuinely invisible to the public.
    """
    store = db.scalar(select(Store).where(
        Store.organization_id == organization_id, Store.is_active.is_(True)
    ))
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found or not active")
    org = db.scalar(select(Organization).where(Organization.id == organization_id))
    if org is None:
        raise HTTPException(status_code=404, detail="Store not found")

    # Build product map: StoreProduct rows keyed by product_id.
    sp_rows = {
        sp.product_id: sp
        for sp in db.scalars(select(StoreProduct).where(
            StoreProduct.store_id == store.id, StoreProduct.is_listed.is_(True)
        ))
    }
    listed_product_ids = set(sp_rows.keys())

    # Active products that have a StoreProduct listing.
    products = list(db.scalars(
        select(Product).where(
            Product.organization_id == organization_id,
            Product.active.is_(True),
            Product.id.in_(listed_product_ids or {""}),
        ).order_by(Product.name)
    ))

    product_list = sorted(
        [_public_product(p, sp_rows.get(p.id), store, db) for p in products],
        key=lambda x: (x["sort_order"], x["name"]),
    )

    return {
        **_store_public_view(store, org),
        "products": product_list,
    }


# ---------------------------------------------------------------------------
# Admin endpoints — owner / manager only
# ---------------------------------------------------------------------------

class StoreCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=160)
    tagline: str | None = Field(default=None, max_length=300)
    theme_preset: str = Field(default="clean", max_length=20)
    theme_color: str = Field(default="#0a8752", max_length=7)
    category: str | None = Field(default=None, max_length=60)
    area: str | None = Field(default=None, max_length=120)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not SLUG_RE.match(v):
            raise ValueError("Slug must be 3-80 lowercase letters, digits, or hyphens")
        return v

    @field_validator("theme_color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("theme_color must be a 6-digit hex color like #0a8752")
        return v.lower()


class StoreUpdate(BaseModel):
    slug: str | None = Field(default=None, min_length=3, max_length=80)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    tagline: str | None = None
    logo_data_url: str | None = None
    cover_data_url: str | None = None
    theme_preset: str | None = Field(default=None, max_length=20)
    theme_color: str | None = Field(default=None, max_length=7)
    category: str | None = Field(default=None, max_length=60)
    area: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    show_phone: bool | None = None
    show_exact_address: bool | None = None
    show_hours: bool | None = None
    show_stock_level: str | None = Field(default=None, max_length=20)
    show_price: bool | None = None
    payment_cod: bool | None = None
    payment_bkash: bool | None = None
    payment_nagad: bool | None = None
    min_order_bdt: Decimal | None = None
    delivery_note: str | None = Field(default=None, max_length=300)
    hours_json: dict | None = None
    meta_title: str | None = Field(default=None, max_length=160)
    meta_desc: str | None = Field(default=None, max_length=320)


class StoreProductUpdate(BaseModel):
    is_listed: bool | None = None
    sort_order: int | None = None
    online_price_bdt: Decimal | None = None
    description_long: str | None = None
    image_data_url: str | None = None
    tags: str | None = Field(default=None, max_length=300)
    is_featured: bool | None = None
    max_order_qty: int | None = None


@router.get("", tags=["store-admin"])
def get_store(membership: CurrentMembership, db: Db):
    """Return this org's store config, or 404 if not yet created."""
    require_permission(membership, "catalog:read")
    store = db.scalar(select(Store).where(Store.organization_id == membership.organization_id))
    if store is None:
        raise HTTPException(status_code=404, detail="No store yet")
    return _store_admin_view(store)


@router.post("", tags=["store-admin"])
def create_store(payload: StoreCreate, membership: CurrentMembership, db: Db):
    """Activate the store for this organization (creates it if it doesn't exist)."""
    require_permission(membership, "catalog:write")
    existing = db.scalar(select(Store).where(Store.organization_id == membership.organization_id))
    if existing:
        raise HTTPException(status_code=409, detail="Store already exists. Use PATCH to update.")
    store = Store(
        organization_id=membership.organization_id,
        slug=payload.slug,
        display_name=payload.display_name,
        tagline=payload.tagline,
        theme_preset=payload.theme_preset,
        theme_color=payload.theme_color,
        category=payload.category,
        area=payload.area,
        is_active=False,
    )
    db.add(store)
    try:
        db.commit()
        db.refresh(store)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already taken. Choose a different one.")
    return _store_admin_view(store)


@router.patch("", tags=["store-admin"])
def update_store(payload: StoreUpdate, membership: CurrentMembership, db: Db):
    require_permission(membership, "catalog:write")
    store = _get_store_or_404(db, membership.organization_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "slug" and value is not None:
            if not SLUG_RE.match(value):
                raise HTTPException(status_code=422, detail="Invalid slug format")
        if field == "hours_json":
            setattr(store, field, json.dumps(value) if value is not None else None)
        else:
            setattr(store, field, value)
    try:
        db.commit()
        db.refresh(store)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already taken")
    return _store_admin_view(store)


@router.get("/products", tags=["store-admin"])
def list_store_products(membership: CurrentMembership, db: Db):
    """All active products with their store listing state."""
    require_permission(membership, "catalog:read")
    org_id = membership.organization_id
    store = db.scalar(select(Store).where(Store.organization_id == org_id))

    products = list(db.scalars(
        select(Product).where(Product.organization_id == org_id, Product.active.is_(True)).order_by(Product.name)
    ))
    sp_map: dict[str, StoreProduct] = {}
    if store:
        sp_map = {
            sp.product_id: sp
            for sp in db.scalars(select(StoreProduct).where(StoreProduct.store_id == store.id))
        }

    return [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "unit": p.unit,
            "selling_price": float(p.selling_price),
            "is_listed": sp_map[p.id].is_listed if p.id in sp_map else False,
            "is_featured": sp_map[p.id].is_featured if p.id in sp_map else False,
            "sort_order": sp_map[p.id].sort_order if p.id in sp_map else 0,
            "online_price_bdt": float(sp_map[p.id].online_price_bdt) if p.id in sp_map and sp_map[p.id].online_price_bdt else None,
            "description_long": sp_map[p.id].description_long if p.id in sp_map else None,
            "image_data_url": sp_map[p.id].image_data_url if p.id in sp_map else None,
            "tags": sp_map[p.id].tags if p.id in sp_map else None,
            "max_order_qty": sp_map[p.id].max_order_qty if p.id in sp_map else None,
            "store_product_id": sp_map[p.id].id if p.id in sp_map else None,
        }
        for p in products
    ]


@router.put("/products/{product_id}", tags=["store-admin"])
def upsert_store_product(product_id: str, payload: StoreProductUpdate, membership: CurrentMembership, db: Db):
    """Create or update the store listing for one product."""
    require_permission(membership, "catalog:write")
    org_id = membership.organization_id
    store = _get_store_or_404(db, org_id)
    product = db.scalar(select(Product).where(Product.id == product_id, Product.organization_id == org_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    sp = db.scalar(select(StoreProduct).where(
        StoreProduct.store_id == store.id, StoreProduct.product_id == product_id
    ))
    if sp is None:
        sp = StoreProduct(store_id=store.id, product_id=product_id)
        db.add(sp)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sp, field, value)
    db.commit()
    db.refresh(sp)
    return {
        "id": sp.id, "product_id": sp.product_id, "is_listed": sp.is_listed,
        "is_featured": sp.is_featured, "sort_order": sp.sort_order,
        "online_price_bdt": float(sp.online_price_bdt) if sp.online_price_bdt else None,
        "description_long": sp.description_long, "tags": sp.tags,
        "max_order_qty": sp.max_order_qty,
    }


@router.get("/orders", tags=["store-admin"])
def list_online_orders(
    membership: CurrentMembership, db: Db,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """Online orders placed through the public storefront (channel='online')."""
    require_permission(membership, "orders:read")
    stmt = (
        select(SalesDocument)
        .options(selectinload(SalesDocument.lines))
        .where(
            SalesDocument.organization_id == membership.organization_id,
            SalesDocument.document_type == "order",
            SalesDocument.channel == "online",
        )
        .order_by(SalesDocument.issued_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(SalesDocument.status == status)

    orders = list(db.scalars(stmt))
    product_ids = {line.product_id for order in orders for line in order.lines}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids or {""})))}

    return [
        {
            "id": doc.id,
            "order_number": doc.document_number,
            "status": doc.status,
            "placed_at": doc.issued_at,
            "customer_name": doc.shipping_name,
            "customer_phone": doc.shipping_phone,
            "delivery_address": doc.shipping_address,
            "total": float(doc.total),
            "access_token": doc.access_token,
            "items": [
                {
                    "product_name": products[l.product_id].name if l.product_id in products else l.product_id,
                    "quantity": float(l.quantity),
                    "unit_price": float(l.unit_price),
                    "line_total": float(l.line_total),
                }
                for l in doc.lines
            ],
        }
        for doc in orders
    ]


@router.get("/stats", tags=["store-admin"])
def store_stats(membership: CurrentMembership, db: Db):
    """Quick stats for the store admin dashboard card."""
    require_permission(membership, "orders:read")
    from sqlalchemy import case
    org_id = membership.organization_id

    total_online = db.scalar(
        select(func.count(SalesDocument.id)).where(
            SalesDocument.organization_id == org_id,
            SalesDocument.document_type == "order",
            SalesDocument.channel == "online",
        )
    ) or 0

    pending_count = db.scalar(
        select(func.count(SalesDocument.id)).where(
            SalesDocument.organization_id == org_id,
            SalesDocument.document_type == "order",
            SalesDocument.channel == "online",
            SalesDocument.status == "placed",
        )
    ) or 0

    revenue = db.scalar(
        select(func.coalesce(func.sum(SalesDocument.total), 0)).where(
            SalesDocument.organization_id == org_id,
            SalesDocument.document_type == "order",
            SalesDocument.channel == "online",
            SalesDocument.status.in_(["confirmed", "ready", "dispatched", "delivered", "invoiced"]),
        )
    ) or Decimal("0")

    listed = db.scalar(
        select(func.count(StoreProduct.id)).join(Store).where(
            Store.organization_id == org_id,
            StoreProduct.is_listed.is_(True),
        )
    ) or 0

    return {
        "total_orders": total_online,
        "pending_orders": pending_count,
        "confirmed_revenue_bdt": float(revenue),
        "listed_products": listed,
    }
