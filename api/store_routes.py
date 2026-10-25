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
    ProductVariant, SalesDocument, Store, StoreProduct, utcnow,
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
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
            InventoryBalance.organization_id == org_id,
            InventoryBalance.product_id == product_id,
        )
    ) or Decimal("0")
    available = balance > 0
    if show_level == "available_only":
        return {"in_stock": available}
    return {"in_stock": available, "quantity": float(balance)}


def _public_product(p: Product, sp: StoreProduct | None, store: Store, db: Session) -> dict:
    from datetime import datetime, timezone as tz
    price = float(sp.online_price_bdt) if sp and sp.online_price_bdt is not None else float(p.selling_price)
    # Flash sale
    sale_price = None
    sale_end = None
    if sp and sp.sale_price is not None:
        now = datetime.now(tz.utc).isoformat()
        start_ok = (not sp.sale_start) or sp.sale_start <= now
        end_ok   = (not sp.sale_end)   or sp.sale_end   >= now
        if start_ok and end_ok:
            sale_price = float(sp.sale_price)
            sale_end   = sp.sale_end
    # Variants
    variants = []
    for v in db.scalars(select(ProductVariant).where(ProductVariant.product_id == p.id)).all():
        try:
            opts = json.loads(v.options)
        except Exception:
            opts = []
        try:
            deltas = json.loads(v.price_deltas) if v.price_deltas else {}
        except Exception:
            deltas = {}
        variants.append({"id": v.id, "name": v.name, "options": opts, "price_deltas": deltas})
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "unit": p.unit,
        "price": price if store.show_price else None,
        "sale_price": sale_price if store.show_price else None,
        "sale_end": sale_end,
        "description": (sp.description_long if sp and sp.description_long else "") or "",
        "image_data_url": sp.image_data_url if sp else None,
        "tags": (sp.tags.split(",") if sp and sp.tags else []),
        "is_featured": sp.is_featured if sp else False,
        "sort_order": sp.sort_order if sp else 0,
        "max_order_qty": sp.max_order_qty if sp else None,
        "variants": variants,
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
        "bkash_number": store.bkash_number if store.payment_bkash else None,
        "nagad_number": store.nagad_number if store.payment_nagad else None,
        "min_order_bdt": float(store.min_order_bdt) if store.min_order_bdt else None,
        "delivery_note": store.delivery_note,
        "meta_title": store.meta_title,
        "meta_desc": store.meta_desc,
        "delivery_inside_dhaka": float(store.delivery_inside_dhaka) if store.delivery_inside_dhaka else None,
        "delivery_outside_dhaka": float(store.delivery_outside_dhaka) if store.delivery_outside_dhaka else None,
        "delivery_free_above": float(store.delivery_free_above) if store.delivery_free_above else None,
        "allow_zone_restriction": store.allow_zone_restriction,
        "allowed_divisions": store.allowed_divisions,
        # Expose only the store_id (not password) to public — needed for frontend to show SSLCommerz option
        "sslcz_store_id": store.sslcz_store_id or None,
        "sslcz_is_live": store.sslcz_is_live,
        # Expose presence (not secrets) so frontend knows direct API mode is available
        "bkash_app_key": store.bkash_app_key or None,
        "nagad_merchant_id": store.nagad_merchant_id or None,
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
        "bkash_number": store.bkash_number,
        "nagad_number": store.nagad_number,
        "min_order_bdt": float(store.min_order_bdt) if store.min_order_bdt else None,
        "delivery_note": store.delivery_note,
        "hours_json": json.loads(store.hours_json) if store.hours_json else None,
        "meta_title": store.meta_title,
        "meta_desc": store.meta_desc,
        "delivery_inside_dhaka": float(store.delivery_inside_dhaka) if store.delivery_inside_dhaka else None,
        "delivery_outside_dhaka": float(store.delivery_outside_dhaka) if store.delivery_outside_dhaka else None,
        "delivery_free_above": float(store.delivery_free_above) if store.delivery_free_above else None,
        "allow_zone_restriction": store.allow_zone_restriction,
        "allowed_divisions": store.allowed_divisions,
        "sslcz_store_id": store.sslcz_store_id or None,
        "sslcz_store_passwd": store.sslcz_store_passwd or None,
        "sslcz_is_live": store.sslcz_is_live,
        "created_at": store.created_at,
    }


# ---------------------------------------------------------------------------
# Public endpoints — no auth required
# ---------------------------------------------------------------------------

@public_router.get("/", tags=["public-store"])
def list_public_stores(
    db: Db,
    category: str | None = Query(None),
    area: str | None = Query(None),
):
    """Return all active stores for the public directory page."""
    q = select(Store, Organization).join(
        Organization, Organization.id == Store.organization_id
    ).where(Store.is_active.is_(True)).order_by(Store.display_name)
    rows = db.execute(q).all()
    result = []
    for store, org in rows:
        if category and store.category and category.lower() not in store.category.lower():
            continue
        if area and store.area and area.lower() not in store.area.lower():
            continue
        result.append({
            "organization_id": store.organization_id,
            "slug": store.slug,
            "display_name": store.display_name,
            "tagline": store.tagline,
            "logo_data_url": store.logo_data_url,
            "cover_data_url": store.cover_data_url,
            "category": store.category,
            "area": store.area,
            "theme_color": store.theme_color,
            "theme_preset": store.theme_preset,
            "payment_cod": store.payment_cod,
            "payment_bkash": store.payment_bkash,
            "payment_nagad": store.payment_nagad,
        })
    return result


@public_router.get("/slug/{slug}", tags=["public-store"])
def get_public_store_by_slug(slug: str, db: Db):
    """Lookup a store by its slug instead of org UUID."""
    store = db.scalar(select(Store).where(
        Store.slug == slug, Store.is_active.is_(True)
    ))
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found or not active")
    org = db.scalar(select(Organization).where(Organization.id == store.organization_id))
    if org is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return _build_store_response(store, org, db)


def _build_store_response(store: Store, org: Organization, db: Session) -> dict:
    """Shared logic for public store responses (by org_id or by slug)."""
    sp_rows = {
        sp.product_id: sp
        for sp in db.scalars(select(StoreProduct).where(
            StoreProduct.store_id == store.id, StoreProduct.is_listed.is_(True)
        ))
    }
    listed_product_ids = set(sp_rows.keys())
    products = list(db.scalars(
        select(Product).where(
            Product.organization_id == store.organization_id,
            Product.active.is_(True),
            Product.id.in_(listed_product_ids or {""}),
        ).order_by(Product.name)
    ))
    product_list = sorted(
        [_public_product(p, sp_rows.get(p.id), store, db) for p in products],
        key=lambda x: (x["sort_order"], x["name"]),
    )
    return {**_store_public_view(store, org), "products": product_list}


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
    return _build_store_response(store, org, db)


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
    bkash_number: str | None = Field(default=None, max_length=20)
    nagad_number: str | None = Field(default=None, max_length=20)
    min_order_bdt: Decimal | None = None
    delivery_note: str | None = Field(default=None, max_length=300)
    hours_json: dict | None = None
    meta_title: str | None = Field(default=None, max_length=160)
    meta_desc: str | None = Field(default=None, max_length=320)
    delivery_inside_dhaka: Decimal | None = None
    delivery_outside_dhaka: Decimal | None = None
    delivery_free_above: Decimal | None = None
    allow_zone_restriction: bool | None = None
    allowed_divisions: str | None = Field(default=None, max_length=200)
    sslcz_store_id: str | None = Field(default=None, max_length=100)
    sslcz_store_passwd: str | None = Field(default=None, max_length=200)
    sslcz_is_live: bool | None = None
    bkash_app_key: str | None = Field(default=None, max_length=200)
    bkash_app_secret: str | None = Field(default=None, max_length=200)
    bkash_username: str | None = Field(default=None, max_length=100)
    bkash_password: str | None = Field(default=None, max_length=100)
    bkash_is_live: bool | None = None
    nagad_merchant_id: str | None = Field(default=None, max_length=100)
    nagad_merchant_number: str | None = Field(default=None, max_length=20)
    nagad_pub_key: str | None = None
    nagad_priv_key: str | None = None
    nagad_is_live: bool | None = None


class StoreProductUpdate(BaseModel):
    is_listed: bool | None = None
    sort_order: int | None = None
    online_price_bdt: Decimal | None = None
    description_long: str | None = None
    image_data_url: str | None = None
    tags: str | None = Field(default=None, max_length=300)
    is_featured: bool | None = None
    max_order_qty: int | None = None
    # Flash sale
    sale_price: Decimal | None = None
    sale_start: str | None = None   # ISO datetime string or null to clear
    sale_end: str | None = None


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
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
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
    if from_date:
        from datetime import datetime as _dt
        try:
            stmt = stmt.where(SalesDocument.issued_at >= _dt.fromisoformat(from_date))
        except ValueError:
            pass
    if to_date:
        from datetime import datetime as _dt
        try:
            stmt = stmt.where(SalesDocument.issued_at <= _dt.fromisoformat(to_date))
        except ValueError:
            pass

    orders = list(db.scalars(stmt))
    product_ids = {line.product_id for order in orders for line in order.lines}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids or {""})))}

    return [
        {
            "id": doc.id,
            "order_number": doc.document_number,
            "status": doc.status,
            "payment_status": getattr(doc, "payment_status", "pending"),
            "status_note": getattr(doc, "status_note", None),
            "placed_at": doc.issued_at,
            "customer_name": doc.shipping_name,
            "customer_phone": doc.shipping_phone,
            "delivery_address": doc.shipping_address,
            "subtotal": float(doc.subtotal),
            "delivery_fee": float(getattr(doc, "delivery_fee", 0) or 0),
            "total": float(doc.total),
            "notes": doc.notes,
            "access_token": doc.access_token,
            "has_payment_screenshot": bool(getattr(doc, "payment_screenshot_url", None)),
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


class PaymentStatusIn(BaseModel):
    payment_status: str = Field(max_length=20)


class StatusNoteIn(BaseModel):
    note: str = Field(max_length=500)


class BulkStatusIn(BaseModel):
    order_ids: list[str] = Field(min_length=1, max_length=100)
    status: str = Field(max_length=20)


@router.post("/orders/{order_id}/payment-status", tags=["store-admin"])
def update_payment_status(order_id: str, body: PaymentStatusIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "orders:write")
    doc = db.scalar(select(SalesDocument).where(
        SalesDocument.id == order_id,
        SalesDocument.organization_id == membership.organization_id,
    ))
    if doc is None:
        raise HTTPException(status_code=404, detail="Order not found")
    doc.payment_status = body.payment_status
    db.commit()
    return {"id": doc.id, "payment_status": doc.payment_status}


@router.post("/orders/{order_id}/status-note", tags=["store-admin"])
def update_status_note(order_id: str, body: StatusNoteIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "orders:write")
    doc = db.scalar(select(SalesDocument).where(
        SalesDocument.id == order_id,
        SalesDocument.organization_id == membership.organization_id,
    ))
    if doc is None:
        raise HTTPException(status_code=404, detail="Order not found")
    doc.status_note = body.note
    db.commit()
    return {"id": doc.id, "status_note": doc.status_note}


@router.post("/orders/bulk-status", tags=["store-admin"])
def bulk_update_status(body: BulkStatusIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "orders:write")
    from .order_routes import ORDER_TRANSITIONS
    updated = []
    for order_id in body.order_ids:
        doc = db.scalar(select(SalesDocument).where(
            SalesDocument.id == order_id,
            SalesDocument.organization_id == membership.organization_id,
        ))
        if doc is None:
            continue
        allowed = ORDER_TRANSITIONS.get(doc.status, set())
        if body.status in allowed:
            doc.status = body.status
            updated.append(order_id)
    db.commit()
    return {"updated": updated, "count": len(updated)}


@router.get("/orders/export.csv", tags=["store-admin"])
def export_orders_csv(membership: CurrentMembership, db: Db):
    import csv
    import io
    from fastapi.responses import StreamingResponse
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
        .limit(5000)
    )
    orders = list(db.scalars(stmt))
    product_ids = {line.product_id for order in orders for line in order.lines}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids or {""})))}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order Number", "Status", "Payment Status", "Placed At", "Customer Name", "Phone", "Address", "Subtotal", "Delivery Fee", "Total", "Items"])
    for doc in orders:
        items_str = "; ".join(
            f"{products[l.product_id].name if l.product_id in products else l.product_id} x{float(l.quantity)}"
            for l in doc.lines
        )
        writer.writerow([
            doc.document_number, doc.status,
            getattr(doc, "payment_status", "pending"),
            doc.issued_at.isoformat() if doc.issued_at else "",
            doc.shipping_name, doc.shipping_phone, doc.shipping_address,
            float(doc.subtotal), float(getattr(doc, "delivery_fee", 0) or 0), float(doc.total),
            items_str,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


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


# ── Revenue chart ─────────────────────────────────────────────────────────────

@router.get("/revenue-chart", tags=["store-admin"])
def revenue_chart(
    membership: CurrentMembership,
    db: Db,
    days: int = Query(default=30, ge=7, le=365),
):
    """Daily confirmed revenue for the last N days."""
    require_permission(membership, "orders:read")
    from datetime import datetime, timedelta, timezone as tz
    import json as _json

    org_id = membership.organization_id
    cutoff = datetime.now(tz.utc) - timedelta(days=days)

    docs = db.scalars(
        select(SalesDocument).where(
            SalesDocument.organization_id == org_id,
            SalesDocument.document_type == "order",
            SalesDocument.channel == "online",
            SalesDocument.status.in_(["confirmed", "ready", "dispatched", "delivered", "invoiced"]),
            SalesDocument.issued_at >= cutoff,
        )
    ).all()

    # Aggregate by date
    by_date: dict[str, float] = {}
    for doc in docs:
        day = doc.issued_at.strftime("%Y-%m-%d")
        by_date[day] = by_date.get(day, 0.0) + float(doc.total)

    # Fill gaps
    result = []
    for i in range(days):
        day = (datetime.now(tz.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        result.append({"date": day, "revenue": by_date.get(day, 0.0)})

    return {"days": days, "data": result}


# ── Low stock alerts ──────────────────────────────────────────────────────────

@router.get("/low-stock", tags=["store-admin"])
def low_stock_alerts(membership: CurrentMembership, db: Db):
    """Products below their stock_alert_threshold."""
    require_permission(membership, "catalog:read")
    from .domain_models import InventoryBalance as IB, Product as P

    org_id = membership.organization_id
    products = db.scalars(
        select(P).where(
            P.organization_id == org_id,
            P.active.is_(True),
            P.stock_alert_threshold.isnot(None),
        )
    ).all()

    alerts = []
    for p in products:
        bal = db.scalar(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.organization_id == org_id,
                InventoryBalance.product_id == p.id,
            )
        ) or Decimal("0")
        if float(bal) <= p.stock_alert_threshold:
            alerts.append({
                "product_id": p.id,
                "name": p.name,
                "sku": p.sku,
                "current_stock": float(bal),
                "threshold": p.stock_alert_threshold,
            })
    return alerts


# ── Stock alert threshold update ─────────────────────────────────────────────

class AlertThresholdIn(BaseModel):
    threshold: int | None = None


@router.patch("/products/{product_id}/alert-threshold", tags=["store-admin"])
def set_alert_threshold(product_id: str, body: AlertThresholdIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "catalog:write")
    from .domain_models import Product as P
    product = db.scalar(
        select(P).where(P.id == product_id, P.organization_id == membership.organization_id)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.stock_alert_threshold = body.threshold
    db.commit()
    return {"ok": True}


# ── Product variant CRUD ──────────────────────────────────────────────────────

class VariantIn(BaseModel):
    name: str = Field(max_length=50)
    options: list[str]
    price_deltas: dict[str, float] | None = None


@router.get("/products/{product_id}/variants", tags=["store-admin"])
def list_variants(product_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "catalog:read")
    variants = db.scalars(
        select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.organization_id == membership.organization_id,
        )
    ).all()
    return [
        {
            "id": v.id,
            "name": v.name,
            "options": json.loads(v.options),
            "price_deltas": json.loads(v.price_deltas) if v.price_deltas else {},
        }
        for v in variants
    ]


@router.post("/products/{product_id}/variants", status_code=201, tags=["store-admin"])
def create_variant(product_id: str, body: VariantIn, membership: CurrentMembership, db: Db):
    require_permission(membership, "catalog:write")
    v = ProductVariant(
        organization_id=membership.organization_id,
        product_id=product_id,
        name=body.name,
        options=json.dumps(body.options),
        price_deltas=json.dumps(body.price_deltas) if body.price_deltas else None,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"id": v.id, "name": v.name, "options": body.options, "price_deltas": body.price_deltas or {}}


@router.delete("/products/{product_id}/variants/{variant_id}", status_code=204, tags=["store-admin"])
def delete_variant(product_id: str, variant_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "catalog:write")
    v = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
            ProductVariant.organization_id == membership.organization_id,
        )
    )
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    db.delete(v)
    db.commit()
