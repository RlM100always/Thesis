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
    BranchCreate, BranchView, CustomerCreate, CustomerUpdate, CustomerView, StaffBranchesIn, StaffInvite,
    StaffInvited, StaffUpdate, StaffView, SupplierCreate, SupplierView, WarehouseCreate, WarehouseView,
)
from .auth import CurrentMembership, CurrentUser
from .config import get_settings
from .database import get_db
from .domain_models import (
    AuditLog, Branch, Customer, LedgerEntry, Membership, MembershipBranch, Supplier, User, Warehouse, utcnow,
)
from .audit import record_audit
from .permissions import assigned_branch_ids, require_permission
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
    """Branches this membership may work in -- the Branch Selector's data source.

    A branch-scoped membership (``MembershipBranch`` rows present) sees only
    its assigned branches; an unscoped one (the pre-ABAC default) still sees
    every branch, unchanged from before.
    """
    query = select(Branch).where(
        Branch.organization_id == membership.organization_id, Branch.active.is_(True)
    )
    allowed = assigned_branch_ids(db, membership)
    if allowed is not None:
        query = query.where(Branch.id.in_(allowed))
    return list(db.scalars(query.order_by(Branch.name)))


def _staff_view(db: Session, member: Membership, user: User) -> StaffView:
    branches = assigned_branch_ids(db, member)
    return StaffView(
        membership_id=member.id, user_id=user.id, email=user.email,
        display_name=user.display_name, role=member.role, active=member.active,
        pending_setup=user.password_hash is None,
        assigned_branch_ids=sorted(branches) if branches else [],
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
        **_staff_view(db, member, user).model_dump(), setup_token=raw, setup_expires_at=expires,
    )


@router.get("/staff", response_model=list[StaffView], tags=["staff"])
def list_staff(membership: CurrentMembership, db: Db):
    require_permission(membership, "staff:read")
    rows = db.execute(select(Membership, User).join(User).where(
        Membership.organization_id == membership.organization_id
    ).order_by(User.display_name)).all()
    return [_staff_view(db, m, u) for m, u in rows]


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
    return _staff_view(db, target, user)


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
        **_staff_view(db, target, user).model_dump(), setup_token=raw, setup_expires_at=expires,
    )


@router.put("/staff/{membership_id}/branches", response_model=StaffView, tags=["staff"])
def set_staff_branches(
    membership_id: str, payload: StaffBranchesIn, membership: CurrentMembership,
    actor: CurrentUser, db: Db,
):
    """Restrict (or un-restrict) a staff member to specific branches (SRD 2.3 ABAC).

    An empty list removes every restriction, which means org-wide access --
    the same as a membership that was never scoped at all.
    """
    require_permission(membership, "staff:manage")
    target, user = _target_membership(db, membership, membership_id)
    valid_branch_ids = set(db.scalars(
        select(Branch.id).where(Branch.organization_id == membership.organization_id)
    ))
    unknown = set(payload.branch_ids) - valid_branch_ids
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown branch id(s): {sorted(unknown)}")
    db.execute(
        MembershipBranch.__table__.delete().where(MembershipBranch.membership_id == target.id)
    )
    for branch_id in set(payload.branch_ids):
        db.add(MembershipBranch(membership_id=target.id, branch_id=branch_id))
    _audit(db, membership, actor, "staff.branches_set", target.id, branch_ids=sorted(payload.branch_ids))
    db.commit()
    return _staff_view(db, target, user)


@router.post("/warehouses", response_model=WarehouseView, tags=["branches"])
def create_warehouse(payload: WarehouseCreate, membership: CurrentMembership, user: CurrentUser, db: Db):
    require_permission(membership, "branches:write")
    branch = db.get(Branch, payload.branch_id)
    if branch is None or branch.organization_id != membership.organization_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    warehouse = Warehouse(organization_id=membership.organization_id, **payload.model_dump())
    db.add(warehouse)
    try:
        db.flush()
        db.add(AuditLog(
            organization_id=membership.organization_id, actor_user_id=user.id,
            action="warehouse.created", entity_type="warehouse", entity_id=warehouse.id,
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Warehouse code already exists for this branch") from exc
    return warehouse


@router.get("/warehouses", response_model=list[WarehouseView], tags=["branches"])
def list_warehouses(membership: CurrentMembership, db: Db, branch_id: str | None = Query(default=None)):
    query = select(Warehouse).where(
        Warehouse.organization_id == membership.organization_id, Warehouse.active.is_(True)
    )
    if branch_id:
        query = query.where(Warehouse.branch_id == branch_id)
    return list(db.scalars(query.order_by(Warehouse.name)))


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


@router.get("/customers/{customer_id}/360", tags=["customers-app"])
def customer_360(customer_id: str, membership: CurrentMembership, db: Db):
    """Customer 360 (SRD Panel C02): one read model over everything the rest of
    this file, loyalty, tickets, leads and feedback already track separately.
    Pulls together existing data; nothing here is a new source of truth."""
    require_permission(membership, "customers:read")
    from .domain_models import Feedback, Lead, SalesOrder, SupportTicket
    from .loyalty import balance as loyalty_balance

    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.organization_id == membership.organization_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    org_id = membership.organization_id
    owed = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
        LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == "receivable",
        LedgerEntry.party_type == "customer", LedgerEntry.party_id == customer_id))
    recent_orders = db.scalars(
        select(SalesOrder).where(SalesOrder.organization_id == org_id, SalesOrder.customer_id == customer_id)
        .order_by(SalesOrder.sold_at.desc()).limit(10)
    ).all()
    lifetime_total = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.organization_id == org_id, SalesOrder.customer_id == customer_id))
    open_tickets = db.scalars(
        select(SupportTicket).where(
            SupportTicket.organization_id == org_id, SupportTicket.customer_id == customer_id,
            SupportTicket.status.in_(("open", "pending")),
        ).order_by(SupportTicket.created_at.desc())
    ).all()
    feedback_entries = db.scalars(
        select(Feedback).where(Feedback.organization_id == org_id, Feedback.customer_id == customer_id)
        .order_by(Feedback.created_at.desc()).limit(10)
    ).all()
    originating_lead = db.scalar(select(Lead).where(
        Lead.organization_id == org_id, Lead.converted_customer_id == customer_id))

    return {
        "customer": CustomerView.model_validate(customer).model_copy(update={"balance": Decimal(str(owed or 0))}),
        "lifetime_sales_total": Decimal(str(lifetime_total or 0)),
        "recent_orders": [
            {"id": o.id, "invoice_number": o.invoice_number, "sold_at": o.sold_at.isoformat(), "total": o.total}
            for o in recent_orders
        ],
        "loyalty_balance": loyalty_balance(db, org_id, customer_id),
        "open_tickets": [
            {"id": t.id, "subject": t.subject, "status": t.status, "priority": t.priority}
            for t in open_tickets
        ],
        "feedback": [
            {"id": f.id, "score": f.score, "comment": f.comment, "created_at": f.created_at.isoformat()}
            for f in feedback_entries
        ],
        "originated_from_lead_id": originating_lead.id if originating_lead else None,
    }


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
