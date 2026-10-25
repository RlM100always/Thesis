"""Product reviews and star ratings from verified buyers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Annotated

from .database import get_db
from .domain_models import ProductReview, SalesDocument, StoreCustomer
from .store_customer_routes import _get_customer

Db = Session

router = APIRouter(prefix="/api/public/reviews", tags=["reviews"])


class ReviewIn(BaseModel):
    product_id: str
    order_id: str   # SalesDocument.id — proves purchase
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


def _view(r: ProductReview, name: str | None = None) -> dict:
    return {
        "id": r.id,
        "product_id": r.product_id,
        "rating": r.rating,
        "comment": r.comment,
        "reviewer_name": name or "গ্রাহক",
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.post("/{org_id}", status_code=201)
def submit_review(
    org_id: str,
    body: ReviewIn,
    authorization: Annotated[str | None, Header()] = None,
    db: Db = Depends(get_db),
):
    customer = _get_customer(authorization, db, required=True)
    # Verify the order belongs to this customer and this org
    order = db.scalar(
        select(SalesDocument).where(
            SalesDocument.id == body.order_id,
            SalesDocument.organization_id == org_id,
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="অর্ডার পাওয়া যায়নি")
    if order.store_customer_id != customer.id and order.shipping_phone != customer.phone:
        raise HTTPException(status_code=403, detail="এই অর্ডারের জন্য আপনি রিভিউ দিতে পারবেন না")

    existing = db.scalar(
        select(ProductReview).where(
            ProductReview.organization_id == org_id,
            ProductReview.product_id == body.product_id,
            ProductReview.store_customer_id == customer.id,
        )
    )
    if existing:
        existing.rating = body.rating
        existing.comment = body.comment
        existing.order_id = body.order_id
        db.commit()
        db.refresh(existing)
        return _view(existing, customer.display_name)

    review = ProductReview(
        organization_id=org_id,
        product_id=body.product_id,
        store_customer_id=customer.id,
        order_id=body.order_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _view(review, customer.display_name)


@router.get("/{org_id}/{product_id}")
def list_reviews(org_id: str, product_id: str, db: Db = Depends(get_db)):
    reviews = db.scalars(
        select(ProductReview).where(
            ProductReview.organization_id == org_id,
            ProductReview.product_id == product_id,
        ).order_by(ProductReview.created_at.desc()).limit(50)
    ).all()
    customer_ids = [r.store_customer_id for r in reviews]
    customers = {
        c.id: c.display_name
        for c in db.scalars(
            select(StoreCustomer).where(StoreCustomer.id.in_(customer_ids))
        ).all()
    } if customer_ids else {}

    avg = db.scalar(
        select(func.avg(ProductReview.rating)).where(
            ProductReview.organization_id == org_id,
            ProductReview.product_id == product_id,
        )
    )
    count = db.scalar(
        select(func.count(ProductReview.id)).where(
            ProductReview.organization_id == org_id,
            ProductReview.product_id == product_id,
        )
    )
    return {
        "average": round(float(avg), 1) if avg else None,
        "count": count or 0,
        "reviews": [_view(r, customers.get(r.store_customer_id)) for r in reviews],
    }
