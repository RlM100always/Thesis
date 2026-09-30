"""Loyalty points: a customer's balance and history, and the owner's rule."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import record_audit
from .auth import CurrentMembership
from .database import get_db
from .domain_models import Customer, LoyaltyEntry, LoyaltyRule
from .loyalty import balance as loyalty_balance
from .loyalty import get_rule
from .permissions import require_permission

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


@router.get("/loyalty/rule", tags=["loyalty"])
def read_rule(membership: CurrentMembership, db: Db):
    require_permission(membership, "customers:read")
    rule = get_rule(db, membership.organization_id)
    if rule is None:
        return None
    return {
        "points_per_taka": rule.points_per_taka, "redemption_value": rule.redemption_value, "active": rule.active,
    }


class LoyaltyRuleUpdate(BaseModel):
    points_per_taka: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    redemption_value: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=4)
    active: bool | None = None


@router.patch("/loyalty/rule", tags=["loyalty"])
def update_rule(body: LoyaltyRuleUpdate, membership: CurrentMembership, db: Db):
    """Owner-only: how fast points are earned, what they're worth, on or off."""
    require_permission(membership, "settings:write")
    org_id = membership.organization_id
    rule = db.scalar(select(LoyaltyRule).where(LoyaltyRule.organization_id == org_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="No loyalty rule found for this organization")
    changes = {}
    for field in ("points_per_taka", "redemption_value", "active"):
        value = getattr(body, field)
        if value is not None:
            setattr(rule, field, value)
            changes[field] = value
    record_audit(db, membership, "loyalty_rule.updated", "loyalty_rule", rule.id, **changes)
    db.commit()
    return {"points_per_taka": rule.points_per_taka, "redemption_value": rule.redemption_value, "active": rule.active}


@router.get("/customers/{customer_id}/loyalty", tags=["loyalty"])
def customer_loyalty(customer_id: str, membership: CurrentMembership, db: Db, limit: int = Query(default=20, ge=1, le=100)):
    require_permission(membership, "customers:read")
    org_id = membership.organization_id
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == org_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    rule = get_rule(db, org_id)
    entries = list(db.scalars(select(LoyaltyEntry).where(
        LoyaltyEntry.organization_id == org_id, LoyaltyEntry.customer_id == customer_id,
    ).order_by(LoyaltyEntry.occurred_at.desc()).limit(limit)))
    return {
        "customer_id": customer_id, "balance": loyalty_balance(db, org_id, customer_id),
        "active": bool(rule and rule.active), "redemption_value": rule.redemption_value if rule else None,
        "history": [{
            "id": e.id, "points_delta": e.points_delta, "reason": e.reason, "occurred_at": e.occurred_at,
        } for e in entries],
    }
