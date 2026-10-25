"""Coupon / promo-code management and validation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentMembership
from .database import get_db
from .domain_models import StoreCoupon
from .permissions import require_permission

Db = Session

router = APIRouter(prefix="/api/app/store/coupons", tags=["store-coupons"])
public_router = APIRouter(prefix="/api/public/store", tags=["store-public"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    discount_type: str = "percent"   # "percent" | "fixed"
    discount_value: Decimal
    min_order_bdt: Decimal = Decimal("0")
    max_uses: int | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool = True


class CouponUpdate(BaseModel):
    discount_type: str | None = None
    discount_value: Decimal | None = None
    min_order_bdt: Decimal | None = None
    max_uses: int | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool | None = None


def _view(c: StoreCoupon) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "discount_type": c.discount_type,
        "discount_value": float(c.discount_value),
        "min_order_bdt": float(c.min_order_bdt),
        "max_uses": c.max_uses,
        "used_count": c.used_count,
        "valid_from": c.valid_from.isoformat() if c.valid_from else None,
        "valid_to": c.valid_to.isoformat() if c.valid_to else None,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("")
def list_coupons(membership: CurrentMembership, db: Db = Depends(get_db)):
    require_permission(membership, "catalog:read")
    coupons = db.scalars(
        select(StoreCoupon)
        .where(StoreCoupon.organization_id == membership.organization_id)
        .order_by(StoreCoupon.created_at.desc())
    ).all()
    return [_view(c) for c in coupons]


@router.post("", status_code=201)
def create_coupon(payload: CouponCreate, membership: CurrentMembership, db: Db = Depends(get_db)):
    require_permission(membership, "catalog:write")
    existing = db.scalar(
        select(StoreCoupon).where(
            StoreCoupon.organization_id == membership.organization_id,
            StoreCoupon.code == payload.code.upper(),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="এই কোড ইতিমধ্যে আছে")
    coupon = StoreCoupon(
        organization_id=membership.organization_id,
        code=payload.code.upper(),
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_bdt=payload.min_order_bdt,
        max_uses=payload.max_uses,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        is_active=payload.is_active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return _view(coupon)


@router.patch("/{coupon_id}")
def update_coupon(coupon_id: str, payload: CouponUpdate, membership: CurrentMembership, db: Db = Depends(get_db)):
    require_permission(membership, "catalog:write")
    coupon = db.scalar(
        select(StoreCoupon).where(
            StoreCoupon.id == coupon_id,
            StoreCoupon.organization_id == membership.organization_id,
        )
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    db.commit()
    db.refresh(coupon)
    return _view(coupon)


@router.delete("/{coupon_id}", status_code=204)
def delete_coupon(coupon_id: str, membership: CurrentMembership, db: Db = Depends(get_db)):
    require_permission(membership, "catalog:write")
    coupon = db.scalar(
        select(StoreCoupon).where(
            StoreCoupon.id == coupon_id,
            StoreCoupon.organization_id == membership.organization_id,
        )
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(coupon)
    db.commit()


# ── Public validation endpoint ────────────────────────────────────────────────

class ValidateBody(BaseModel):
    code: str
    order_subtotal: Decimal


@public_router.post("/{org_id}/coupon/validate")
def validate_coupon(org_id: str, body: ValidateBody, db: Db = Depends(get_db)):
    """Check a coupon code and return the discount amount (no side-effects)."""
    now = datetime.now(timezone.utc)
    coupon = db.scalar(
        select(StoreCoupon).where(
            StoreCoupon.organization_id == org_id,
            StoreCoupon.code == body.code.upper(),
            StoreCoupon.is_active.is_(True),
        )
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="অবৈধ কুপন কোড")
    if coupon.valid_from and coupon.valid_from > now:
        raise HTTPException(status_code=400, detail="কুপনটি এখনও সক্রিয় হয়নি")
    if coupon.valid_to and coupon.valid_to < now:
        raise HTTPException(status_code=400, detail="কুপনের মেয়াদ শেষ")
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="কুপন সীমা পূর্ণ হয়েছে")
    if body.order_subtotal < coupon.min_order_bdt:
        raise HTTPException(
            status_code=400,
            detail=f"ন্যূনতম অর্ডার ৳{coupon.min_order_bdt} হতে হবে",
        )
    if coupon.discount_type == "percent":
        discount = round(body.order_subtotal * coupon.discount_value / 100, 2)
    else:
        discount = min(coupon.discount_value, body.order_subtotal)
    return {
        "valid": True,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "discount_amount": float(discount),
    }
