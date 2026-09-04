"""Branches, staff, customers, and suppliers."""

import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import (
    BranchCreate, BranchView, CustomerCreate, CustomerView, StaffInvite, StaffView,
    SupplierCreate, SupplierView,
)
from .auth import CurrentMembership, CurrentUser
from .commerce_routes import require_role
from .config import get_settings
from .database import get_db
from .domain_models import AuditLog, Branch, Customer, Membership, Supplier, User

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


def phone_hash(organization_id: str, phone: str | None) -> str | None:
    if not phone:
        return None
    key = f"{get_settings().jwt_secret}:{organization_id}".encode()
    return hmac.new(key, phone.encode(), hashlib.sha256).hexdigest()


@router.post("/branches", response_model=BranchView, tags=["branches"])
def create_branch(payload: BranchCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_role(membership, "owner", "manager")
    branch = Branch(organization_id=membership.organization_id, **payload.model_dump())
    db.add(branch)
    try:
        db.flush()
        db.add(AuditLog(
            organization_id=membership.organization_id, actor_user_id=user.id,
            action="branch.created", entity_type="branch", entity_id=branch.id,
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Branch code already exists") from exc
    return branch


@router.get("/branches", response_model=list[BranchView], tags=["branches"])
def list_branches(membership: CurrentMembership, db: Db):
    return list(db.scalars(select(Branch).where(
        Branch.organization_id == membership.organization_id, Branch.active.is_(True)
    ).order_by(Branch.name)))


@router.post("/staff", response_model=StaffView, tags=["staff"])
def invite_staff(payload: StaffInvite, membership: CurrentMembership, actor: CurrentUser, db: Db):
    require_role(membership, "owner")
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=payload.display_name)
        db.add(user)
        db.flush()
    member = Membership(
        organization_id=membership.organization_id, user_id=user.id, role=payload.role
    )
    db.add(member)
    try:
        db.flush()
        db.add(AuditLog(
            organization_id=membership.organization_id, actor_user_id=actor.id,
            action="staff.invited", entity_type="membership", entity_id=member.id,
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member") from exc
    return StaffView(
        membership_id=member.id, user_id=user.id, email=user.email,
        display_name=user.display_name, role=member.role, active=member.active,
    )


@router.get("/staff", response_model=list[StaffView], tags=["staff"])
def list_staff(membership: CurrentMembership, db: Db):
    require_role(membership, "owner", "manager")
    rows = db.execute(select(Membership, User).join(User).where(
        Membership.organization_id == membership.organization_id
    ).order_by(User.display_name)).all()
    return [StaffView(
        membership_id=m.id, user_id=u.id, email=u.email, display_name=u.display_name,
        role=m.role, active=m.active,
    ) for m, u in rows]


@router.post("/customers", response_model=CustomerView, tags=["customers-app"])
def create_customer(payload: CustomerCreate, membership: CurrentMembership, db: Db):
    data = payload.model_dump(exclude={"phone"})
    customer = Customer(
        organization_id=membership.organization_id,
        phone_hash=phone_hash(membership.organization_id, payload.phone), **data,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer code already exists") from exc
    db.refresh(customer)
    return customer


@router.get("/customers", response_model=list[CustomerView], tags=["customers-app"])
def list_customers_app(
    membership: CurrentMembership, db: Db, q: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
):
    statement = select(Customer).where(Customer.organization_id == membership.organization_id)
    if q:
        statement = statement.where(
            Customer.code.ilike(f"%{q}%") | Customer.display_name.ilike(f"%{q}%")
        )
    return list(db.scalars(statement.order_by(Customer.code).limit(limit)))


@router.post("/suppliers", response_model=SupplierView, tags=["suppliers"])
def create_supplier(payload: SupplierCreate, membership: CurrentMembership, db: Db):
    require_role(membership, "owner", "manager", "accountant")
    supplier = Supplier(organization_id=membership.organization_id, **payload.model_dump())
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Supplier code already exists") from exc
    db.refresh(supplier)
    return supplier


@router.get("/suppliers", response_model=list[SupplierView], tags=["suppliers"])
def list_suppliers(membership: CurrentMembership, db: Db):
    return list(db.scalars(select(Supplier).where(
        Supplier.organization_id == membership.organization_id
    ).order_by(Supplier.name)))
