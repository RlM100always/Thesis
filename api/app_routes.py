"""Operational product API, separate from the legacy research endpoints.

The thesis prototype currently uses the local development owner supplied by
``api.auth``. External identity-provider integration is intentionally deferred.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .accounting import seed_default_accounts
from .approvals import seed_default_rules
from .app_schemas import OrganizationCreate, OrganizationOperations, OrganizationProfile, OrganizationView, UserView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .permissions import require_permission
from .database import get_db
from .domain_models import AuditLog, Branch, Membership, Organization, OrganizationSetting, Product

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


def _setting_values(setting: OrganizationSetting | None) -> dict:
    if setting is None:
        return {"business_mode": "products", "payment_methods": ["cash"], "sales_channels": ["in_store"]}
    return {
        "business_mode": setting.business_mode,
        "payment_methods": json.loads(setting.payment_methods_json),
        "sales_channels": json.loads(setting.sales_channels_json),
    }


@router.get("/auth/me", response_model=UserView, tags=["app-auth"])
def me(current_user: CurrentUser):
    return current_user


@router.post("/organizations", response_model=OrganizationView, tags=["organizations"])
def create_organization(payload: OrganizationCreate, current_user: CurrentUser, db: Db):
    organization = Organization(
        name=payload.name.strip(), slug=payload.slug, sector=payload.sector,
        size_class=payload.size_class,
    )
    db.add(organization)
    try:
        db.flush()
        seed_default_accounts(db, organization.id)
        seed_default_rules(db, organization.id)
        db.add_all([
            Membership(organization_id=organization.id, user_id=current_user.id, role="owner"),
            OrganizationSetting(organization_id=organization.id),
            Branch(
                organization_id=organization.id, code="MAIN",
                name=payload.default_branch_name.strip(),
            ),
            AuditLog(
                organization_id=organization.id, actor_user_id=current_user.id,
                action="organization.created", entity_type="organization",
                entity_id=organization.id,
            ),
        ])
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Organization slug already exists") from exc
    return OrganizationView(
        id=organization.id, name=organization.name, slug=organization.slug,
        sector=organization.sector, size_class=organization.size_class,
        currency=organization.currency, timezone=organization.timezone,
        locale=organization.locale, role="owner",
        address=organization.address, phone=organization.phone,
        vat_reg_no=organization.vat_reg_no, receipt_footer=organization.receipt_footer,
        **_setting_values(db.get(OrganizationSetting, organization.id)),
    )


@router.get("/organizations", response_model=list[OrganizationView], tags=["organizations"])
def list_organizations(current_user: CurrentUser, db: Db):
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == current_user.id, Membership.active.is_(True))
        .order_by(Organization.name)
    ).all()
    expiry_orgs = set(db.scalars(select(Product.organization_id).where(
        Product.track_expiry.is_(True),
        Product.organization_id.in_([org.id for org, _ in rows]),
    ).distinct()))
    settings = {row.organization_id: row for row in db.scalars(select(OrganizationSetting).where(
        OrganizationSetting.organization_id.in_([org.id for org, _ in rows])
    ))} if rows else {}
    return [
        OrganizationView(
            id=org.id, name=org.name, slug=org.slug, sector=org.sector,
            size_class=org.size_class, currency=org.currency,
            timezone=org.timezone, locale=org.locale, role=role,
            uses_expiry=org.id in expiry_orgs,
            address=org.address, phone=org.phone, vat_reg_no=org.vat_reg_no,
            receipt_footer=org.receipt_footer,
            **_setting_values(settings.get(org.id)),
        )
        for org, role in rows
    ]


@router.patch("/organization", response_model=OrganizationView, tags=["organizations"])
def update_organization(payload: OrganizationProfile, membership: CurrentMembership, db: Db):
    """Shop name, type and the details printed on receipts. Owner only."""
    require_permission(membership, "settings:write")
    org = db.get(Organization, membership.organization_id)
    changes = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        value = value.strip() if isinstance(value, str) else value
        if field == "name" and not value:
            continue
        setattr(org, field, value or None if field != "name" else value)
        changes[field] = bool(value)
    record_audit(db, membership, "organization.updated", "organization", org.id, fields=sorted(changes))
    db.commit()
    from .domain_models import Product
    return OrganizationView(
        id=org.id, name=org.name, slug=org.slug, sector=org.sector, size_class=org.size_class,
        currency=org.currency, timezone=org.timezone, locale=org.locale, role=membership.role,
        uses_expiry=bool(db.scalar(select(Product.id).where(
            Product.organization_id == org.id, Product.track_expiry.is_(True)).limit(1))),
        address=org.address, phone=org.phone, vat_reg_no=org.vat_reg_no, receipt_footer=org.receipt_footer,
        **_setting_values(db.get(OrganizationSetting, org.id)),
    )


@router.patch("/organization/operations", response_model=OrganizationView, tags=["organizations"])
def update_organization_operations(payload: OrganizationOperations, membership: CurrentMembership, db: Db):
    """The operational choices made in onboarding and Settings.

    These are product configuration, not external-connector credentials. The
    POS consumes the enabled payment methods immediately.
    """
    require_permission(membership, "settings:write")
    org = db.get(Organization, membership.organization_id)
    setting = db.get(OrganizationSetting, org.id)
    if setting is None:
        setting = OrganizationSetting(organization_id=org.id)
        db.add(setting)
    setting.business_mode = payload.business_mode
    setting.payment_methods_json = json.dumps(payload.payment_methods)
    setting.sales_channels_json = json.dumps(payload.sales_channels)
    record_audit(db, membership, "organization.operations_updated", "organization", org.id,
                 business_mode=payload.business_mode, payment_methods=payload.payment_methods,
                 sales_channels=payload.sales_channels)
    db.commit()
    return OrganizationView(
        id=org.id, name=org.name, slug=org.slug, sector=org.sector, size_class=org.size_class,
        currency=org.currency, timezone=org.timezone, locale=org.locale, role=membership.role,
        uses_expiry=bool(db.scalar(select(Product.id).where(
            Product.organization_id == org.id, Product.track_expiry.is_(True)).limit(1))),
        address=org.address, phone=org.phone, vat_reg_no=org.vat_reg_no,
        receipt_footer=org.receipt_footer, **_setting_values(setting),
    )
