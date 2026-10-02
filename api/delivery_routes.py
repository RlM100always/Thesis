"""Deliveries and COD handover (SRD Panels E04-E06).

"Delivered" and "the business has the cash" are deliberately different facts:
completing a delivery only records what the rider says happened at the door;
the money isn't counted anywhere until a cashier confirms a handover, which
lands as a real `CashMovement` on that cashier's open shift -- the same
reconciliation path a cash drop or top-up already goes through.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import CODHandoverCreate, CODHandoverView, DeliveryComplete, DeliveryCreate, DeliveryView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import CashierShift, CashMovement, CODHandover, Delivery, SalesOrder
from .permissions import require_permission

router = APIRouter(prefix="/api/app/deliveries", tags=["deliveries"])
Db = Annotated[Session, Depends(get_db)]


def _get_delivery(db: Session, org_id: str, delivery_id: str) -> Delivery:
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id, Delivery.organization_id == org_id))
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery


def _require_assigned_rider(delivery: Delivery, user) -> None:
    if delivery.rider_user_id != user.id:
        raise HTTPException(status_code=403, detail="This delivery is not assigned to you")


@router.post("", response_model=DeliveryView)
def create_delivery(payload: DeliveryCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "deliveries:write")
    order = db.scalar(select(SalesOrder).where(
        SalesOrder.id == payload.sales_order_id, SalesOrder.organization_id == membership.organization_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    existing = db.scalar(select(Delivery).where(
        Delivery.sales_order_id == payload.sales_order_id, Delivery.status.in_(("assigned", "out_for_delivery")),
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This order already has an active delivery")
    delivery = Delivery(
        organization_id=membership.organization_id, branch_id=order.branch_id, created_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(delivery)
    db.flush()
    record_audit(db, membership, "delivery.assigned", "delivery", delivery.id,
                 rider_user_id=payload.rider_user_id, sales_order_id=payload.sales_order_id)
    db.commit()
    return delivery


@router.get("/me", response_model=list[DeliveryView])
def my_deliveries(membership: CurrentMembership, user: CurrentUser, db: Db):
    return list(db.scalars(
        select(Delivery).where(
            Delivery.organization_id == membership.organization_id, Delivery.rider_user_id == user.id,
        ).order_by(Delivery.created_at.desc())
    ))


@router.get("", response_model=list[DeliveryView])
def list_deliveries(
    membership: CurrentMembership, db: Db,
    status: str | None = Query(default=None, pattern=r"^(assigned|out_for_delivery|delivered|failed)$"),
):
    require_permission(membership, "deliveries:read")
    query = select(Delivery).where(Delivery.organization_id == membership.organization_id)
    if status:
        query = query.where(Delivery.status == status)
    return list(db.scalars(query.order_by(Delivery.created_at.desc())))


@router.post("/{delivery_id}/out-for-delivery", response_model=DeliveryView)
def start_delivery(delivery_id: str, membership: CurrentMembership, user: CurrentUser, db: Db):
    delivery = _get_delivery(db, membership.organization_id, delivery_id)
    _require_assigned_rider(delivery, user)
    if delivery.status != "assigned":
        raise HTTPException(status_code=409, detail=f"Cannot start from status {delivery.status!r}")
    delivery.status = "out_for_delivery"
    db.commit()
    return delivery


@router.post("/{delivery_id}/complete", response_model=DeliveryView)
def complete_delivery(delivery_id: str, payload: DeliveryComplete, membership: CurrentMembership, user: CurrentUser, db: Db):
    delivery = _get_delivery(db, membership.organization_id, delivery_id)
    _require_assigned_rider(delivery, user)
    if delivery.status != "out_for_delivery":
        raise HTTPException(status_code=409, detail="Delivery must be out for delivery first")
    if payload.status == "failed" and not payload.failure_reason:
        raise HTTPException(status_code=422, detail="A failure reason is required")
    delivery.status = payload.status
    delivery.delivered_at = datetime.now(timezone.utc)
    delivery.proof_note = payload.proof_note
    delivery.failure_reason = payload.failure_reason
    if payload.status == "delivered":
        delivery.cod_amount_collected = payload.cod_collected or Decimal("0")
    record_audit(db, membership, "delivery.completed", "delivery", delivery.id, status=payload.status)
    db.commit()
    return delivery


@router.post("/{delivery_id}/handover", response_model=CODHandoverView)
def hand_over_cod(delivery_id: str, payload: CODHandoverCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    """A cashier (with an open shift) confirms receiving the rider's collected cash.

    This is the only point money actually lands anywhere -- a delivered status
    alone never does.
    """
    require_permission(membership, "cash:close")
    delivery = _get_delivery(db, membership.organization_id, delivery_id)
    if delivery.status != "delivered":
        raise HTTPException(status_code=409, detail="This delivery was not completed as delivered")
    existing = db.scalar(select(CODHandover).where(CODHandover.delivery_id == delivery_id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This delivery's cash was already handed over")
    shift = db.scalar(select(CashierShift).where(
        CashierShift.id == payload.shift_id, CashierShift.organization_id == membership.organization_id,
    ))
    if shift is None or shift.status != "open":
        raise HTTPException(status_code=404, detail="No open shift with that id")
    collected = delivery.cod_amount_collected or Decimal("0")
    shortage = max(Decimal("0"), collected - payload.handed_over_amount)
    handover = CODHandover(
        organization_id=membership.organization_id, delivery_id=delivery_id, shift_id=payload.shift_id,
        handed_over_amount=payload.handed_over_amount, shortage_amount=shortage, received_by_user_id=user.id,
    )
    db.add(handover)
    if payload.handed_over_amount > 0:
        db.add(CashMovement(
            organization_id=membership.organization_id, shift_id=payload.shift_id, direction="add",
            amount=payload.handed_over_amount, reason=f"COD handover: delivery {delivery_id}",
            created_by=user.id,
        ))
    record_audit(db, membership, "delivery.cod_handed_over", "delivery", delivery_id,
                 handed_over_amount=payload.handed_over_amount, shortage=shortage)
    db.commit()
    return handover
