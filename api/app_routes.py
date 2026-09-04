"""Operational product API, separate from the legacy research endpoints.

The thesis prototype currently uses the local development owner supplied by
``api.auth``. External identity-provider integration is intentionally deferred.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app_schemas import OrganizationCreate, OrganizationView, UserView
from .auth import CurrentUser
from .database import get_db
from .domain_models import AuditLog, Branch, Membership, Organization

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


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
        db.add_all([
            Membership(organization_id=organization.id, user_id=current_user.id, role="owner"),
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
    )


@router.get("/organizations", response_model=list[OrganizationView], tags=["organizations"])
def list_organizations(current_user: CurrentUser, db: Db):
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == current_user.id, Membership.active.is_(True))
        .order_by(Organization.name)
    ).all()
    return [
        OrganizationView(
            id=org.id, name=org.name, slug=org.slug, sector=org.sector,
            size_class=org.size_class, currency=org.currency,
            timezone=org.timezone, locale=org.locale, role=role,
        )
        for org, role in rows
    ]
