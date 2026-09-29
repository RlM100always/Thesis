"""Branches, staff, customers, and suppliers."""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import (
    BranchCreate, BranchView, CustomerCreate, CustomerUpdate, CustomerView, StaffInvite, StaffInvited,
    StaffUpdate, StaffView, SupplierCreate, SupplierView,
)
from .auth import CurrentMembership, CurrentUser
from .config import get_settings
from .database import get_db
from .domain_models import AuditLog, Branch, Customer, LedgerEntry, Membership, Supplier, User, utcnow
from .audit import record_audit
from .permissions import require_permission
from .security import new_setup_token

SETUP_LINK_DAYS = 7

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


def phone_hash(organization_id: str, phone: str | None) -> str | None:
    if not phone:
        return None
    key = f"{get_settings().jwt_secret}:{organization_id}".encode()
    return hmac.new(key, phone.encode(), hashlib.sha256).hexdigest()


@router.post("/branches", response_model=BranchView, tags=["branches"])
def create_branch(payload: BranchCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "branches:write")
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


def _staff_view(member: Membership, user: User) -> StaffView:
    return StaffView(
        membership_id=member.id, user_id=user.id, email=user.email,
        display_name=user.display_name, role=member.role, active=member.active,
        pending_setup=user.password_hash is None,
    )


def _issue_setup_token(user: User):
    raw, digest = new_setup_token()
    user.setup_token_hash = digest
    user.setup_token_expires_at = utcnow() + timedelta(days=SETUP_LINK_DAYS)
    return raw, user.setup_token_expires_at


def _audit(db: Session, membership: Membership, actor: User, action: str,
           entity_id: str, **details) -> None:
    db.add(AuditLog(
        organization_id=membership.organization_id, actor_user_id=actor.id,
        action=action, entity_type="membership", entity_id=entity_id,
        metadata_json=json.dumps(details, ensure_ascii=False) if details else None,
    ))


def _target_membership(db: Session, membership: Membership, membership_id: str):
    row = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id).where(
            Membership.id == membership_id,
            Membership.organization_id == membership.organization_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return row


@router.post("/staff", response_model=StaffInvited, tags=["staff"])
def invite_staff(payload: StaffInvite, membership: CurrentMembership, actor: CurrentUser, db: Db):
    """Add someone to this business.

    A brand-new person has no password yet, so the response carries a one-time
    setup link token (shown only here). Someone who already has an account is
    simply added; they keep their own password.
    """
    require_permission(membership, "staff:manage")
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
    raw = expires = None
    if user.password_hash is None:
        raw, expires = _issue_setup_token(user)
    try:
        db.flush()
        _audit(db, membership, actor, "staff.invited", member.id, role=payload.role)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member") from exc
    return StaffInvited(
        **_staff_view(member, user).model_dump(), setup_token=raw, setup_expires_at=expires,
    )


@router.get("/staff", response_model=list[StaffView], tags=["staff"])
def list_staff(membership: CurrentMembership, db: Db):
    require_permission(membership, "staff:read")
    rows = db.execute(select(Membership, User).join(User).where(
        Membership.organization_id == membership.organization_id
    ).order_by(User.display_name)).all()
    return [_staff_view(m, u) for m, u in rows]


@router.patch("/staff/{membership_id}", response_model=StaffView, tags=["staff"])
def update_staff(
    membership_id: str, payload: StaffUpdate, membership: CurrentMembership,
    actor: CurrentUser, db: Db,
):
    """Change someone's role, or deactivate / reactivate their access here."""
    require_permission(membership, "staff:manage")
    if payload.role is None and payload.active is None:
        raise HTTPException(status_code=422, detail="Nothing to change")
    target, user = _target_membership(db, membership, membership_id)
    new_role = payload.role or target.role
    new_active = target.active if payload.active is None else payload.active

    losing_owner = target.role == "owner" and target.active and (new_role != "owner" or not new_active)
    if losing_owner:
        other_owners = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.organization_id == membership.organization_id,
            Membership.role == "owner", Membership.active.is_(True), Membership.id != target.id,
        ))
        if not other_owners:
            raise HTTPException(
                status_code=409, detail="A business must keep at least one active owner",
            )

    changes = {}
    if new_role != target.role:
        changes["role"] = [target.role, new_role]
    if new_active != target.active:
        changes["active"] = [target.active, new_active]
    target.role, target.active = new_role, new_active
    if changes:
        action = "staff.role_changed" if "role" in changes else (
            "staff.reactivated" if new_active else "staff.deactivated")
        _audit(db, membership, actor, action, target.id, **changes)
    db.commit()
    return _staff_view(target, user)


@router.post("/staff/{membership_id}/setup-link", response_model=StaffInvited, tags=["staff"])
def issue_setup_link(
    membership_id: str, membership: CurrentMembership, actor: CurrentUser, db: Db,
):
    """Issue a fresh one-time password-setup link for a staff member.

    An owner may do this only for people who cannot be hijacked from anywhere
    else: someone who has not set a password yet, or someone whose only active
    membership is in *this* business. Otherwise the owner of one shop could take
    over a colleague's account in another shop.
    """
    require_permission(membership, "staff:manage")
    target, user = _target_membership(db, membership, membership_id)
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="Use change password for your own account")
    if user.password_hash is not None:
        elsewhere = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.user_id == user.id, Membership.active.is_(True),
            Membership.organization_id != membership.organization_id,
        ))
        if elsewhere:
            raise HTTPException(
                status_code=409,
                detail="This person belongs to other businesses; they must reset their own password",
            )
    raw, expires = _issue_setup_token(user)
    _audit(db, membership, actor, "staff.setup_link_issued", target.id)
    db.commit()
    return StaffInvited(
        **_staff_view(target, user).model_dump(), setup_token=raw, setup_expires_at=expires,
    )


@router.post("/customers", response_model=CustomerView, tags=["customers-app"])
def create_customer(payload: CustomerCreate, membership: CurrentMembership, db: Db):
    require_permission(membership, "customers:write")
    data = payload.model_dump(exclude={"phone"})
    customer = Customer(
        organization_id=membership.organization_id,
        phone_hash=phone_hash(membership.organization_id, payload.phone), **data,
    )
    db.add(customer)
    try:
        db.flush()
        # The customer's own details (name, phone) stay out of the trail.
        record_audit(db, membership, "customer.created", "customer", customer.id,
                     marketing_consent=customer.marketing_consent)
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
    require_permission(membership, "customers:read")
    statement = select(Customer).where(Customer.organization_id == membership.organization_id)
    if q:
        statement = statement.where(
            Customer.code.ilike(f"%{q}%") | Customer.display_name.ilike(f"%{q}%")
        )
    customers = list(db.scalars(statement.order_by(Customer.code).limit(limit)))
    owed = dict(db.execute(
        select(LedgerEntry.party_id, func.sum(LedgerEntry.amount_delta)).where(
            LedgerEntry.organization_id == membership.organization_id, LedgerEntry.ledger_type == "receivable",
            LedgerEntry.party_type == "customer", LedgerEntry.party_id.in_([c.id for c in customers]),
        ).group_by(LedgerEntry.party_id)).all())
    return [CustomerView.model_validate(c).model_copy(update={"balance": Decimal(str(owed.get(c.id) or 0))}) for c in customers]


@router.patch("/customers/{customer_id}", response_model=CustomerView, tags=["customers-app"])
def update_customer(customer_id: str, payload: CustomerUpdate, membership: CurrentMembership, db: Db):
    """Name, phone, consent, credit limit and price tier. Name and phone stay out of the audit trail."""
    require_permission(membership, "customers:write")
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.organization_id == membership.organization_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    fields = payload.model_dump(exclude_unset=True)
    changed = []
    if "phone" in fields:
        customer.phone_hash = phone_hash(membership.organization_id, fields.pop("phone"))
        changed.append("phone")
    for field, value in fields.items():
        if value is None and field in ("marketing_consent", "price_tier"):
            continue
        if isinstance(value, str):
            value = value.strip() or None
        setattr(customer, field, value)
        changed.append(field)
    details = {"fields": sorted(changed)}
    if "credit_limit" in changed:
        details["credit_limit"] = str(customer.credit_limit) if customer.credit_limit is not None else None
    if "price_tier" in changed:
        details["price_tier"] = customer.price_tier
    record_audit(db, membership, "customer.updated", "customer", customer.id, **details)
    db.commit()
    owed = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == membership.organization_id, LedgerEntry.ledger_type == "receivable",
        LedgerEntry.party_type == "customer", LedgerEntry.party_id == customer.id))
    return CustomerView.model_validate(customer).model_copy(update={"balance": Decimal(str(owed or 0))})


@router.post("/suppliers", response_model=SupplierView, tags=["suppliers"])
def create_supplier(payload: SupplierCreate, membership: CurrentMembership, db: Db):
    require_permission(membership, "suppliers:write")
    supplier = Supplier(organization_id=membership.organization_id, **payload.model_dump())
    db.add(supplier)
    try:
        db.flush()
        record_audit(db, membership, "supplier.created", "supplier", supplier.id, code=supplier.code)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Supplier code already exists") from exc
    db.refresh(supplier)
    return supplier


@router.get("/suppliers", response_model=list[SupplierView], tags=["suppliers"])
def list_suppliers(membership: CurrentMembership, db: Db):
    require_permission(membership, "suppliers:read")
    return list(db.scalars(select(Supplier).where(
        Supplier.organization_id == membership.organization_id
    ).order_by(Supplier.name)))
