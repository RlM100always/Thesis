"""Sales Targets (SRD Panel H05). Progress is computed from `SalesOrder` +
`AuditLog` (who actually rang up the sale) every time it's read -- never
stored, so it can't drift from the sales ledger.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import SalesTargetCreate, SalesTargetUpdate, SalesTargetView
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import AuditLog, SalesOrder, SalesTarget
from .permissions import require_permission

router = APIRouter(prefix="/api/app/targets", tags=["targets"])
Db = Annotated[Session, Depends(get_db)]


def _achieved(db: Session, org_id: str, user_id: str, period_start: date, period_end: date):
    sale_ids = select(AuditLog.entity_id).where(
        AuditLog.organization_id == org_id, AuditLog.action == "sale.created", AuditLog.actor_user_id == user_id,
    )
    start = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    end = datetime.combine(period_end, time.max, tzinfo=timezone.utc)
    total = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.id.in_(sale_ids),
        SalesOrder.sold_at >= start, SalesOrder.sold_at <= end, SalesOrder.status != "voided",
    ))
    return total or 0


def _view(target: SalesTarget, achieved) -> dict:
    return {
        **SalesTargetView.model_validate(target).model_dump(),
        "achieved_amount": achieved,
        "progress_percent": round(float(achieved) / float(target.target_amount) * 100, 1) if target.target_amount else 0.0,
    }


@router.post("")
def create_target(payload: SalesTargetCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "targets:write")
    target = SalesTarget(
        organization_id=membership.organization_id, created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(target)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A target for this person and period already exists") from exc
    achieved = _achieved(db, membership.organization_id, target.user_id, target.period_start, target.period_end)
    return _view(target, achieved)


@router.get("/me")
def my_targets(membership: CurrentMembership, user: CurrentUser, db: Db):
    targets = db.scalars(
        select(SalesTarget).where(
            SalesTarget.organization_id == membership.organization_id, SalesTarget.user_id == user.id,
        ).order_by(SalesTarget.period_start.desc())
    ).all()
    return [
        _view(t, _achieved(db, membership.organization_id, t.user_id, t.period_start, t.period_end))
        for t in targets
    ]


@router.get("")
def list_targets(membership: CurrentMembership, db: Db):
    require_permission(membership, "commission:read")
    targets = db.scalars(
        select(SalesTarget).where(SalesTarget.organization_id == membership.organization_id)
        .order_by(SalesTarget.period_start.desc())
    ).all()
    return [
        _view(t, _achieved(db, membership.organization_id, t.user_id, t.period_start, t.period_end))
        for t in targets
    ]


@router.patch("/{target_id}")
def update_target(target_id: str, payload: SalesTargetUpdate, membership: CurrentMembership, db: Db):
    require_permission(membership, "targets:write")
    target = db.scalar(select(SalesTarget).where(
        SalesTarget.id == target_id, SalesTarget.organization_id == membership.organization_id))
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    target.target_amount = payload.target_amount
    db.commit()
    achieved = _achieved(db, membership.organization_id, target.user_id, target.period_start, target.period_end)
    return _view(target, achieved)
