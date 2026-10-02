"""Commission (SRD Panel H05): the owner's rate, and each person's earn/clawback
history. Earning and clawback themselves happen inline in the sale and return
routes (`commerce_routes.py`, `finance_routes.py`) -- this file is read plus
the rule's on/off switch, the same split `loyalty_routes.py` uses.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import CommissionEntryView, CommissionRuleUpdate
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .commission import balance_for, get_rule
from .database import get_db
from .domain_models import CommissionEntry, CommissionRule
from .permissions import require_permission

router = APIRouter(prefix="/api/app/commission", tags=["commission"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/rule")
def read_rule(membership: CurrentMembership, db: Db):
    require_permission(membership, "commission:read")
    rule = get_rule(db, membership.organization_id)
    if rule is None:
        return None
    return {"rate_percent": rule.rate_percent, "active": rule.active}


@router.patch("/rule")
def update_rule(payload: CommissionRuleUpdate, membership: CurrentMembership, db: Db):
    """Owner-only: the commission rate, on or off."""
    require_permission(membership, "settings:write")
    rule = db.scalar(select(CommissionRule).where(CommissionRule.organization_id == membership.organization_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="No commission rule found for this organization")
    changes = {}
    for field in ("rate_percent", "active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(rule, field, value)
            changes[field] = value
    record_audit(db, membership, "commission_rule.updated", "commission_rule", rule.id, **changes)
    db.commit()
    return {"rate_percent": rule.rate_percent, "active": rule.active}


@router.get("/me")
def my_commission(membership: CurrentMembership, user: CurrentUser, db: Db,
                  limit: int = Query(default=50, ge=1, le=500)):
    entries = list(db.scalars(
        select(CommissionEntry).where(
            CommissionEntry.organization_id == membership.organization_id, CommissionEntry.user_id == user.id,
        ).order_by(CommissionEntry.occurred_at.desc()).limit(limit)
    ))
    return {
        "balance": balance_for(db, membership.organization_id, user.id),
        "entries": [CommissionEntryView.model_validate(e) for e in entries],
    }


@router.get("")
def team_commission(membership: CurrentMembership, db: Db):
    """Everyone's running commission balance -- the Target/Commission team view."""
    require_permission(membership, "commission:read")
    from sqlalchemy import func

    from .domain_models import User

    rows = db.execute(
        select(CommissionEntry.user_id, User.display_name, func.sum(CommissionEntry.amount))
        .join(User, User.id == CommissionEntry.user_id)
        .where(CommissionEntry.organization_id == membership.organization_id)
        .group_by(CommissionEntry.user_id, User.display_name)
        .order_by(func.sum(CommissionEntry.amount).desc())
    ).all()
    return [{"user_id": uid, "name": name, "balance": balance} for uid, name, balance in rows]
