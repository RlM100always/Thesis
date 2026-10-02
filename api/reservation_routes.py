"""Reservation Board (SRD Panel E02): allocate stock to an order before it's
invoiced. Never touches on-hand quantity -- see `reservations.py` for how
availability is computed and `commerce_routes.py` for where it's enforced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .app_schemas import ReservationCreate, ReservationView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .database import get_db
from .domain_models import Reservation, SalesDocument, SalesDocumentLine
from .permissions import require_permission
from .reservations import reserved_quantity

router = APIRouter(prefix="/api/app/reservations", tags=["reservations"])
Db = Annotated[Session, Depends(get_db)]


@router.post("", response_model=list[ReservationView])
def create_reservation(payload: ReservationCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "orders:create")
    org_id = membership.organization_id
    document = db.scalar(select(SalesDocument).where(
        SalesDocument.id == payload.sales_document_id, SalesDocument.organization_id == org_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Sales document not found")
    if document.document_type != "order":
        raise HTTPException(status_code=422, detail="Only an order (not a quotation) can reserve stock")
    existing = db.scalar(select(Reservation.id).where(
        Reservation.sales_document_id == document.id, Reservation.status == "active"))
    if existing is not None:
        raise HTTPException(status_code=409, detail="This order already has active reservations")
    lines = db.scalars(select(SalesDocumentLine).where(SalesDocumentLine.document_id == document.id)).all()
    if not lines:
        raise HTTPException(status_code=422, detail="This order has no lines to reserve")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.hold_hours)
    created = []
    for line in lines:
        reservations = Reservation(
            organization_id=org_id, branch_id=document.branch_id, product_id=line.product_id,
            sales_document_id=document.id, quantity=line.quantity, expires_at=expires_at,
            created_by_user_id=user.id,
        )
        db.add(reservations)
        created.append(reservations)
    db.flush()
    record_audit(db, membership, "reservation.created", "sales_document", document.id,
                 lines=len(created), expires_at=expires_at.isoformat())
    db.commit()
    return created


@router.get("", response_model=list[ReservationView])
def list_reservations(
    membership: CurrentMembership, db: Db,
    branch_id: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern=r"^(active|released|fulfilled)$"),
):
    require_permission(membership, "orders:read")
    query = select(Reservation).where(Reservation.organization_id == membership.organization_id)
    if branch_id:
        query = query.where(Reservation.branch_id == branch_id)
    if status:
        query = query.where(Reservation.status == status)
    return list(db.scalars(query.order_by(Reservation.expires_at)))


@router.post("/{sales_document_id}/release", response_model=list[ReservationView])
def release_reservation(sales_document_id: str, membership: CurrentMembership, db: Db):
    """Free this order's held stock back to the pool without fulfilling it."""
    require_permission(membership, "orders:fulfill")
    rows = db.scalars(select(Reservation).where(
        Reservation.organization_id == membership.organization_id,
        Reservation.sales_document_id == sales_document_id, Reservation.status == "active",
    )).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No active reservations for this order")
    for row in rows:
        row.status = "released"
    record_audit(db, membership, "reservation.released", "sales_document", sales_document_id, lines=len(rows))
    db.commit()
    return rows


@router.get("/availability/{product_id}")
def check_availability(product_id: str, branch_id: str, membership: CurrentMembership, db: Db):
    require_permission(membership, "inventory:read")
    from .domain_models import InventoryBalance
    on_hand = db.scalar(select(InventoryBalance.quantity).where(
        InventoryBalance.organization_id == membership.organization_id,
        InventoryBalance.branch_id == branch_id, InventoryBalance.product_id == product_id,
    )) or 0
    reserved = reserved_quantity(db, membership.organization_id, branch_id, product_id)
    return {"product_id": product_id, "branch_id": branch_id, "on_hand": on_hand,
            "reserved": reserved, "available": on_hand - reserved}
