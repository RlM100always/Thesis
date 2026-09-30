"""Platform super-admin: read-only visibility across every tenant.

Wave 3 of `docs/BUSINESS_OS_VISION.md`'s build order ("Platform: tenants,
model registry, drift board"), scoped down to its first, most tractable
slice: a tenant list with real per-org counts. No route here writes to a
tenant's own data, and no route can ever be used to *become* an admin of a
tenant the caller wasn't already a member of -- this is visibility, not a
backdoor. `get_platform_admin` (api/auth.py) gates every route; that flag is
never settable through any API, only by a migration or a direct DB edit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_platform_admin
from .database import get_db
from .domain_models import Branch, Membership, Organization, Product, SalesOrder, User

router = APIRouter(prefix="/api/platform", tags=["platform"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(get_platform_admin)]


@router.get("/organizations")
def list_organizations(admin: Admin, db: Db):
    """Every tenant on this deployment, with real (not estimated) counts."""
    orgs = list(db.scalars(select(Organization).order_by(Organization.created_at.desc())))
    org_ids = [o.id for o in orgs]
    if not org_ids:
        return {"count": 0, "organizations": []}

    members = dict(db.execute(
        select(Membership.organization_id, func.count(Membership.id))
        .where(Membership.organization_id.in_(org_ids), Membership.active.is_(True))
        .group_by(Membership.organization_id)
    ).all())
    branches = dict(db.execute(
        select(Branch.organization_id, func.count(Branch.id))
        .where(Branch.organization_id.in_(org_ids), Branch.active.is_(True))
        .group_by(Branch.organization_id)
    ).all())
    products = dict(db.execute(
        select(Product.organization_id, func.count(Product.id))
        .where(Product.organization_id.in_(org_ids), Product.active.is_(True))
        .group_by(Product.organization_id)
    ).all())
    last_sale = dict(db.execute(
        select(SalesOrder.organization_id, func.max(SalesOrder.sold_at))
        .where(SalesOrder.organization_id.in_(org_ids))
        .group_by(SalesOrder.organization_id)
    ).all())

    return {
        "count": len(orgs),
        "organizations": [
            {
                "id": o.id, "name": o.name, "slug": o.slug, "sector": o.sector,
                "active": o.active, "created_at": o.created_at.isoformat(),
                "member_count": members.get(o.id, 0),
                "branch_count": branches.get(o.id, 0),
                "product_count": products.get(o.id, 0),
                "last_sale_at": last_sale.get(o.id).isoformat() if last_sale.get(o.id) else None,
            }
            for o in orgs
        ],
    }


@router.get("/summary")
def platform_summary(admin: Admin, db: Db):
    """Platform-wide counts for a one-screen overview."""
    now = datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(),
        "organizations_total": db.scalar(select(func.count(Organization.id))) or 0,
        "organizations_active": db.scalar(select(func.count(Organization.id)).where(Organization.active.is_(True))) or 0,
        "users_total": db.scalar(select(func.count(User.id))) or 0,
        "sales_orders_total": db.scalar(select(func.count(SalesOrder.id))) or 0,
    }
