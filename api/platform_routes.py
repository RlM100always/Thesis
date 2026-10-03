"""Platform operations control plane for the complete B-SMART deployment.

Every route is gated by ``get_platform_admin``. Sensitive configuration is
reported only as ready/not-ready; credentials are never returned to the UI.
Mutating actions are audit logged and destructive tenant deletion requires a
separate suspension step.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_platform_admin
from .auth_routes import TokenOut, _token_response
from .config import get_settings
from .database import get_db
from .domain_models import (
    AdminConversation,
    AdminMessage,
    utcnow,
    AuditLog,
    Branch,
    Membership,
    Notification,
    Organization,
    OutboundMessage,
    Product,
    SalesOrder,
    SiteContent,
    User,
    UserSession,
)
from .permissions import ROLES

router = APIRouter(prefix="/api/platform", tags=["platform"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(get_platform_admin)]


def _money(value) -> float:
    return round(float(value or 0), 2)

# Canonical list of togglable modules. A missing key in an org's
# feature_flags_json means "enabled" -- see the Organization model docstring.
FEATURE_FLAGS: tuple[str, ...] = (
    "workforce", "crm", "fulfilment", "team_chat", "bsmart", "upload",
)

BACKUP_DIR = Path("backups")


def _sqlite_path() -> Path:
    """The on-disk file behind ``DATABASE_URL`` -- Profile A (SRD 3.3) only.

    Postgres (Profile B) backup/restore is `pg_dump`/`pg_restore` run by the
    operator, not an API call; this endpoint deliberately refuses that case
    rather than pretending to cover it.
    """
    url = get_settings().database_url
    if not url.startswith("sqlite"):
        raise HTTPException(
            status_code=400,
            detail="This deployment uses PostgreSQL; back it up with pg_dump, not this endpoint",
        )
    # sqlite:///./bsmart.db -> ./bsmart.db ; sqlite:////abs/path -> /abs/path
    raw = url.split("sqlite:///", 1)[1]
    return Path(raw)


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_file(filename: str) -> Path:
    if "/" in filename or "\\" in filename or not filename.startswith("backup_") or not filename.endswith(".sqlite3"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    path = BACKUP_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    return path


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
                "suspended_at": o.suspended_at.isoformat() if o.suspended_at else None,
                "member_count": members.get(o.id, 0),
                "branch_count": branches.get(o.id, 0),
                "product_count": products.get(o.id, 0),
                "last_sale_at": last_sale.get(o.id).isoformat() if last_sale.get(o.id) else None,
            }
            for o in orgs
        ],
    }


# ── Organization health: who's going quiet ──────────────────────────────────

@router.get("/organizations/stale")
def stale_organizations(admin: Admin, db: Db, inactive_days: int = 14):
    """Active (not suspended) organizations with no sale in `inactive_days` --
    the platform-admin signal for "who might be churning or stuck onboarding",
    computed from real SalesOrder rows, never a guessed engagement score."""
    inactive_days = max(1, min(inactive_days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=inactive_days)
    last_sale = dict(db.execute(
        select(SalesOrder.organization_id, func.max(SalesOrder.sold_at)).group_by(SalesOrder.organization_id)
    ).all())
    orgs = list(db.scalars(select(Organization).where(
        Organization.active.is_(True), Organization.suspended_at.is_(None),
    )))
    stale = []
    for org in orgs:
        last = last_sale.get(org.id)
        if last is None or last.replace(tzinfo=last.tzinfo or timezone.utc) < cutoff:
            stale.append({
                "id": org.id, "name": org.name, "slug": org.slug,
                "created_at": org.created_at.isoformat(),
                "last_sale_at": last.isoformat() if last else None,
            })
    stale.sort(key=lambda o: o["last_sale_at"] or "")
    return {"inactive_days": inactive_days, "count": len(stale), "organizations": stale}


@router.get("/organizations/onboarding")
def organization_onboarding_pipeline(admin: Admin, db: Db):
    """Real onboarding milestones from tenant data, never a guessed score."""
    orgs = list(db.scalars(select(Organization).where(
        Organization.active.is_(True), Organization.suspended_at.is_(None),
    ).order_by(Organization.created_at.desc())))
    if not orgs:
        return {"organizations": [], "count": 0, "completed": 0}
    org_ids = [org.id for org in orgs]
    members = dict(db.execute(select(Membership.organization_id, func.count(Membership.id)).where(
        Membership.organization_id.in_(org_ids), Membership.active.is_(True),
    ).group_by(Membership.organization_id)).all())
    branches = dict(db.execute(select(Branch.organization_id, func.count(Branch.id)).where(
        Branch.organization_id.in_(org_ids), Branch.active.is_(True),
    ).group_by(Branch.organization_id)).all())
    products = dict(db.execute(select(Product.organization_id, func.count(Product.id)).where(
        Product.organization_id.in_(org_ids), Product.active.is_(True),
    ).group_by(Product.organization_id)).all())
    sales = dict(db.execute(select(SalesOrder.organization_id, func.count(SalesOrder.id)).where(
        SalesOrder.organization_id.in_(org_ids),
    ).group_by(SalesOrder.organization_id)).all())
    now = datetime.now(timezone.utc)
    rows = []
    for org in orgs:
        checklist = {
            "profile": bool(org.name and org.sector and org.phone and org.address),
            "team": members.get(org.id, 0) > 0,
            "branch": branches.get(org.id, 0) > 0,
            "catalog": products.get(org.id, 0) > 0,
            "first_sale": sales.get(org.id, 0) > 0,
        }
        done = sum(checklist.values())
        created = org.created_at.replace(tzinfo=org.created_at.tzinfo or timezone.utc)
        rows.append({
            "id": org.id, "name": org.name, "slug": org.slug, "sector": org.sector,
            "created_at": org.created_at.isoformat(),
            "age_days": max(0, (now - created).days),
            "progress_percent": done * 20,
            "stage": "live" if checklist["first_sale"] else "ready" if done >= 4 else "setup",
            "checklist": checklist,
        })
    rows.sort(key=lambda row: (row["progress_percent"], -row["age_days"]))
    return {
        "count": len(rows),
        "completed": sum(1 for row in rows if row["stage"] == "live"),
        "organizations": rows,
    }


@router.get("/organizations/{org_id}")
def get_organization(org_id: str, admin: Admin, db: Db):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    member_rows = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == org_id).order_by(User.display_name)
    ).all()
    members = [{
        "membership_id": membership.id,
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": membership.role,
        "active": membership.active,
        "account_active": user.active,
        "mfa_enabled": user.mfa_enabled,
    } for membership, user in member_rows]
    owners = [member for member in members if member["role"] == "owner" and member["active"]]
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "sector": org.sector,
        "size_class": org.size_class, "currency": org.currency, "timezone": org.timezone,
        "locale": org.locale, "address": org.address, "phone": org.phone,
        "vat_reg_no": org.vat_reg_no,
        "active": org.active, "created_at": org.created_at.isoformat(),
        "suspended_at": org.suspended_at.isoformat() if org.suspended_at else None,
        "suspended_reason": org.suspended_reason,
        "member_count": sum(1 for member in members if member["active"]),
        "branch_count": db.scalar(select(func.count(Branch.id)).where(Branch.organization_id == org.id)) or 0,
        "product_count": db.scalar(select(func.count(Product.id)).where(Product.organization_id == org.id)) or 0,
        "owners": owners, "members": members,
        "feature_flags": {**{f: True for f in FEATURE_FLAGS}, **json.loads(org.feature_flags_json or "{}")},
    }


class OrganizationProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    sector: str = Field(min_length=2, max_length=40)
    size_class: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=30)
    vat_reg_no: str | None = Field(default=None, max_length=40)


@router.patch("/organizations/{org_id}")
def update_organization_profile(org_id: str, payload: OrganizationProfileIn, admin: Admin, db: Db):
    """Correct a tenant profile without changing its stable slug or financial data."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    before = {field: getattr(org, field) for field in payload.model_fields_set}
    changes = payload.model_dump()
    for field, value in changes.items():
        setattr(org, field, value.strip() if isinstance(value, str) else value)
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.organization_profile_updated",
        entity_type="organization", entity_id=org.id,
        metadata_json=json.dumps({"before": before, "after": changes}),
    ))
    db.commit()
    return {"status": "updated"}


class PlatformMembershipIn(BaseModel):
    role: str
    active: bool


@router.patch("/organizations/{org_id}/members/{membership_id}")
def update_organization_member(
    org_id: str, membership_id: str, payload: PlatformMembershipIn, admin: Admin, db: Db,
):
    """Repair tenant access during support incidents with owner lockout guards."""
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="Unknown role")
    membership = db.scalar(select(Membership).where(
        Membership.id == membership_id, Membership.organization_id == org_id,
    ))
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    removing_owner = membership.active and membership.role == "owner" and (
        not payload.active or payload.role != "owner"
    )
    if removing_owner:
        other_owners = db.scalar(select(func.count(Membership.id)).where(
            Membership.organization_id == org_id,
            Membership.id != membership.id,
            Membership.role == "owner",
            Membership.active.is_(True),
        )) or 0
        if other_owners == 0:
            raise HTTPException(status_code=409, detail="A business must keep at least one active owner")
    before = {"role": membership.role, "active": membership.active}
    membership.role = payload.role
    membership.active = payload.active
    target = db.get(User, membership.user_id)
    if target:
        target.token_version += 1
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.membership_updated",
        entity_type="membership", entity_id=membership.id,
        metadata_json=json.dumps({"organization_id": org_id, "before": before,
                                  "after": payload.model_dump()}),
    ))
    db.commit()
    return {"id": membership.id, "role": membership.role, "active": membership.active}


class SuspendIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


@router.post("/organizations/{org_id}/suspend")
def suspend_organization(org_id: str, payload: SuspendIn, admin: Admin, db: Db):
    """Locks out every member of this org (api/auth.py's get_org_membership
    checks suspended_at on every tenant-scoped request) without touching or
    deleting any of their data -- reversible with /unsuspend."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.suspended_at = datetime.now(timezone.utc)
    org.suspended_reason = payload.reason
    db.add(AuditLog(actor_user_id=admin.id, action="platform.organization_suspended",
                     entity_type="organization", entity_id=org.id, metadata_json=f'{{"reason": {json.dumps(payload.reason)}}}'))
    db.commit()
    return {"status": "suspended"}


@router.post("/organizations/{org_id}/unsuspend")
def unsuspend_organization(org_id: str, admin: Admin, db: Db):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.suspended_at = None
    org.suspended_reason = None
    db.add(AuditLog(actor_user_id=admin.id, action="platform.organization_unsuspended",
                     entity_type="organization", entity_id=org.id))
    db.commit()
    return {"status": "active"}


@router.delete("/organizations/{org_id}")
def delete_organization(org_id: str, admin: Admin, db: Db):
    """Hard delete, cascading through every tenant table via the ondelete=CASCADE
    foreign keys already on every org-scoped model. Irreversible, so it only
    accepts an org that is ALREADY suspended -- an admin cannot delete a live,
    unsuspended business by mistake in one call."""
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.suspended_at is None:
        raise HTTPException(status_code=409, detail="Suspend the organization first, then delete it")
    name, slug = org.name, org.slug
    db.delete(org)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.organization_deleted",
                     entity_type="organization", entity_id=org_id, metadata_json=f'{{"name": {json.dumps(name)}, "slug": {json.dumps(slug)}}}'))
    db.commit()
    return {"status": "deleted"}


class FeatureFlagsIn(BaseModel):
    flags: dict[str, bool]


class FeatureRolloutIn(BaseModel):
    enabled: bool
    organization_ids: list[str] | None = None


@router.patch("/organizations/{org_id}/features")
def set_feature_flags(org_id: str, payload: FeatureFlagsIn, admin: Admin, db: Db):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    unknown = set(payload.flags) - set(FEATURE_FLAGS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown feature(s): {', '.join(sorted(unknown))}")
    current = json.loads(org.feature_flags_json or "{}")
    current.update(payload.flags)
    org.feature_flags_json = json.dumps(current)
    db.add(AuditLog(actor_user_id=admin.id, action="platform.features_updated",
                     entity_type="organization", entity_id=org.id, metadata_json=json.dumps(payload.flags)))
    db.commit()
    return {"feature_flags": {**{f: True for f in FEATURE_FLAGS}, **current}}


@router.patch("/features/{feature_key}")
def set_feature_rollout(feature_key: str, payload: FeatureRolloutIn, admin: Admin, db: Db):
    """Enable or disable one module for selected tenants or every active tenant."""
    if feature_key not in FEATURE_FLAGS:
        raise HTTPException(status_code=404, detail="Feature not found")
    query = select(Organization).where(
        Organization.active.is_(True), Organization.suspended_at.is_(None),
    )
    if payload.organization_ids is not None:
        unique_ids = set(payload.organization_ids)
        if len(unique_ids) > 500:
            raise HTTPException(status_code=422, detail="At most 500 organizations can be changed at once")
        query = query.where(Organization.id.in_(unique_ids or {""}))
    orgs = list(db.scalars(query))
    for org in orgs:
        current = json.loads(org.feature_flags_json or "{}")
        current[feature_key] = payload.enabled
        org.feature_flags_json = json.dumps(current)
    db.add(AuditLog(
        actor_user_id=admin.id,
        action="platform.feature_rollout_updated",
        entity_type="feature",
        entity_id=feature_key,
        metadata_json=json.dumps({
            "enabled": payload.enabled,
            "organization_count": len(orgs),
            "scope": "selected" if payload.organization_ids is not None else "all_active",
        }),
    ))
    db.commit()
    return {"feature": feature_key, "enabled": payload.enabled, "updated_count": len(orgs)}


# ── Global user directory and access lifecycle ────────────────────────────

@router.get("/users")
def list_platform_users(
    admin: Admin, db: Db, q: str = "", filter: Literal["all", "mfa", "inactive", "admin"] = "all",
    page: int = 1, page_size: int = 50,
):
    """All deployment users with membership counts; never exposes credentials."""
    page = max(1, page)
    page_size = max(10, min(page_size, 100))
    conditions = []
    if q.strip():
        like = f"%{q.strip()}%"
        conditions.append((User.email.ilike(like)) | (User.display_name.ilike(like)))
    if filter == "mfa":
        conditions.extend((User.active.is_(True), User.mfa_enabled.is_(False)))
    elif filter == "inactive":
        conditions.append(User.active.is_(False))
    elif filter == "admin":
        conditions.append(User.is_platform_admin.is_(True))
    query = select(User)
    count_query = select(func.count(User.id))
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)
    total = db.scalar(count_query) or 0
    users = list(db.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ))
    ids = [u.id for u in users]
    memberships = dict(db.execute(
        select(Membership.user_id, func.count(Membership.id)).where(
            Membership.user_id.in_(ids or [""]), Membership.active.is_(True)
        ).group_by(Membership.user_id)
    ).all())
    return {"count": total, "page": page, "page_size": page_size,
            "has_next": page * page_size < total, "users": [{
        "id": u.id, "email": u.email, "display_name": u.display_name,
        "active": u.active, "is_platform_admin": u.is_platform_admin,
        "mfa_enabled": u.mfa_enabled, "created_at": u.created_at.isoformat(),
        "membership_count": memberships.get(u.id, 0),
    } for u in users]}


@router.get("/users/{user_id}")
def get_platform_user(user_id: str, admin: Admin, db: Db):
    """Account, tenant access and recent device sessions for support/security."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    memberships = db.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    ).all()
    now = datetime.now(timezone.utc)
    sessions = list(db.scalars(
        select(UserSession).where(UserSession.user_id == user.id)
        .order_by(UserSession.last_used_at.desc()).limit(30)
    ))
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "active": user.active,
        "mfa_enabled": user.mfa_enabled,
        "is_platform_admin": user.is_platform_admin,
        "created_at": user.created_at.isoformat(),
        "memberships": [{
            "id": membership.id,
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_slug": org.slug,
            "role": membership.role,
            "active": membership.active,
            "organization_suspended": org.suspended_at is not None,
        } for membership, org in memberships],
        "sessions": [{
            "id": session.id,
            "device_label": session.device_label or "Unknown device",
            "ip_address": session.ip_address,
            "last_used_at": session.last_used_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "active": session.revoked_at is None and session.expires_at.replace(
                tzinfo=session.expires_at.tzinfo or timezone.utc,
            ) > now,
            "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
            "revoked_reason": session.revoked_reason,
        } for session in sessions],
    }


class UserAccessIn(BaseModel):
    active: bool


@router.patch("/users/{user_id}/access")
def set_platform_user_access(user_id: str, payload: UserAccessIn, admin: Admin, db: Db):
    """Deactivate/reactivate a user globally, with a guard against self lockout."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and not payload.active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own platform-admin account")
    user.active = payload.active
    user.token_version += 1  # revoke existing sessions immediately
    if not payload.active:
        now = datetime.now(timezone.utc)
        for session in db.scalars(select(UserSession).where(
            UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
        )):
            session.revoked_at = now
            session.revoked_reason = "platform_account_deactivated"
    db.add(AuditLog(actor_user_id=admin.id,
                     action="platform.user_activated" if payload.active else "platform.user_deactivated",
                     entity_type="user", entity_id=user.id,
                     metadata_json=json.dumps({"email": user.email})))
    db.commit()
    return {"id": user.id, "active": user.active}


@router.post("/users/{user_id}/sessions/{session_id}/revoke")
def revoke_platform_user_session(user_id: str, session_id: str, admin: Admin, db: Db):
    """Immediately revoke one device session after ownership verification."""
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = "platform_admin_revoked"
        db.add(AuditLog(
            actor_user_id=admin.id,
            action="platform.user_session_revoked",
            entity_type="user_session",
            entity_id=session.id,
            metadata_json=json.dumps({"user_id": user_id}),
        ))
        db.commit()
    return {"status": "revoked"}


# ── Platform administrator governance ────────────────────────────────────

@router.get("/administrators")
def list_platform_administrators(admin: Admin, db: Db):
    admins = list(db.scalars(
        select(User).where(User.is_platform_admin.is_(True)).order_by(User.display_name)
    ))
    rows = []
    for user in admins:
        last_used = db.scalar(select(func.max(UserSession.last_used_at)).where(
            UserSession.user_id == user.id,
        ))
        rows.append({
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "active": user.active,
            "mfa_enabled": user.mfa_enabled,
            "created_at": user.created_at.isoformat(),
            "last_session_at": last_used.isoformat() if last_used else None,
            "is_current": user.id == admin.id,
        })
    return {"administrators": rows, "count": len(rows)}


class PlatformAdministratorIn(BaseModel):
    is_platform_admin: bool


@router.patch("/administrators/{user_id}")
def set_platform_administrator(
    user_id: str, payload: PlatformAdministratorIn, admin: Admin, db: Db,
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.is_platform_admin:
        if not target.active:
            raise HTTPException(status_code=409, detail="Activate the account before granting admin access")
        if not target.mfa_enabled:
            raise HTTPException(status_code=409, detail="MFA is required before granting platform admin access")
    elif target.id == admin.id:
        raise HTTPException(status_code=409, detail="You cannot remove your own platform admin access")
    if not payload.is_platform_admin and target.is_platform_admin:
        admin_count = db.scalar(select(func.count(User.id)).where(
            User.is_platform_admin.is_(True), User.active.is_(True),
        )) or 0
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="The platform must keep at least one active administrator")
    changed = target.is_platform_admin != payload.is_platform_admin
    target.is_platform_admin = payload.is_platform_admin
    if changed:
        target.token_version += 1
        db.add(AuditLog(
            actor_user_id=admin.id,
            action="platform.administrator_granted" if payload.is_platform_admin else "platform.administrator_revoked",
            entity_type="user", entity_id=target.id,
            metadata_json=json.dumps({"email": target.email}),
        ))
        db.commit()
    return {"id": target.id, "is_platform_admin": target.is_platform_admin}


# ── Cross-tenant in-app announcements ────────────────────────────────────

class PlatformAnnouncementIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=1500)
    severity: Literal["info", "warning", "critical"] = "info"
    audience: Literal["owners", "leadership", "all"] = "owners"
    organization_ids: list[str] | None = None


@router.post("/announcements")
def send_platform_announcement(payload: PlatformAnnouncementIn, admin: Admin, db: Db):
    roles = {
        "owners": ("owner",),
        "leadership": ("owner", "manager"),
        "all": ROLES,
    }[payload.audience]
    org_query = select(Organization.id).where(
        Organization.active.is_(True), Organization.suspended_at.is_(None),
    )
    if payload.organization_ids is not None:
        unique_ids = set(payload.organization_ids)
        if not unique_ids:
            raise HTTPException(status_code=422, detail="Select at least one organization")
        if len(unique_ids) > 500:
            raise HTTPException(status_code=422, detail="At most 500 organizations can be targeted")
        org_query = org_query.where(Organization.id.in_(unique_ids))
    org_ids = list(db.scalars(org_query))
    memberships = list(db.scalars(
        select(Membership).join(User, User.id == Membership.user_id).where(
            Membership.organization_id.in_(org_ids or [""]),
            Membership.role.in_(roles), Membership.active.is_(True), User.active.is_(True),
        )
    ))
    for membership in memberships:
        db.add(Notification(
            organization_id=membership.organization_id,
            recipient_user_id=membership.user_id,
            category="system",
            severity=payload.severity,
            title=payload.title.strip(),
            body=payload.body.strip(),
        ))
    audit = AuditLog(
        actor_user_id=admin.id, action="platform.announcement_sent",
        entity_type="platform_announcement",
        metadata_json=json.dumps({
            "title": payload.title.strip(), "body": payload.body.strip(),
            "severity": payload.severity, "audience": payload.audience,
            "organization_count": len(org_ids), "recipient_count": len(memberships),
        }),
    )
    db.add(audit)
    db.commit()
    return {"id": audit.id, "organization_count": len(org_ids), "recipient_count": len(memberships)}


@router.get("/announcements")
def list_platform_announcements(admin: Admin, db: Db):
    rows = list(db.scalars(select(AuditLog).where(
        AuditLog.action == "platform.announcement_sent",
    ).order_by(AuditLog.created_at.desc()).limit(50)))
    actor_ids = {row.actor_user_id for row in rows if row.actor_user_id}
    actors = {user.id: user for user in db.scalars(select(User).where(User.id.in_(actor_ids or {""})))}
    return {"announcements": [{
        "id": row.id,
        "actor_email": actors[row.actor_user_id].email if row.actor_user_id in actors else None,
        "created_at": row.created_at.isoformat(),
        **json.loads(row.metadata_json or "{}"),
    } for row in rows]}


@router.post("/organizations/{org_id}/impersonate/{user_id}", response_model=TokenOut)
def impersonate(org_id: str, user_id: str, admin: Admin, db: Db, request: Request):
    """Issue real tokens for ``user_id`` so a platform admin can see exactly
    what that person sees, for support. Always audit-logged with the admin's
    own id as actor -- the token itself is indistinguishable from a normal
    login, so this log entry is the only record that it was impersonation."""
    membership = db.scalar(select(Membership).where(
        Membership.organization_id == org_id, Membership.user_id == user_id, Membership.active.is_(True),
    ))
    if membership is None:
        raise HTTPException(status_code=404, detail="That user is not an active member of this organization")
    target = db.get(User, user_id)
    if target is None or not target.active:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    db.add(AuditLog(actor_user_id=admin.id, action="platform.impersonation_started",
                     entity_type="user", entity_id=user_id,
                     metadata_json=f'{{"organization_id": {json.dumps(org_id)}, "target_email": {json.dumps(target.email)}}}'))
    db.commit()
    return _token_response(target, db, request)


@router.get("/site-content")
def list_site_content(admin: Admin, db: Db):
    from .site_defaults import SITE_DEFAULTS
    rows = list(db.scalars(select(SiteContent)))
    db_vals = {r.key: json.loads(r.value_json) for r in rows}
    return {"content": {**SITE_DEFAULTS, **db_vals}}


class SiteContentIn(BaseModel):
    value: object


@router.put("/site-content/{key}")
def set_site_content(key: str, payload: SiteContentIn, admin: Admin, db: Db):
    row = db.get(SiteContent, key)
    if row is None:
        row = SiteContent(key=key, value_json=json.dumps(payload.value), updated_by_user_id=admin.id)
        db.add(row)
    else:
        row.value_json = json.dumps(payload.value)
        row.updated_by_user_id = admin.id
    db.add(AuditLog(actor_user_id=admin.id, action="platform.site_content_updated",
                     entity_type="site_content", entity_id=key))
    db.commit()
    return {"key": key, "value": payload.value}


@router.delete("/site-content/{key}")
def delete_site_content(key: str, admin: Admin, db: Db):
    row = db.get(SiteContent, key)
    if row is not None:
        db.delete(row)
        db.add(AuditLog(actor_user_id=admin.id, action="platform.site_content_reset",
                         entity_type="site_content", entity_id=key))
        db.commit()
    return {"status": "reset"}


@router.get("/audit")
def platform_audit(
    admin: Admin, db: Db,
    cursor: str | None = None, limit: int = 50, action: str | None = None,
):
    """Every platform-admin action (suspend, delete, impersonate, feature
    flags, site content, backups) -- all of it, regardless of which admin did
    it, never filtered down to "just me". Cursor-paginated on created_at+id so
    a page is stable even as new rows land. Platform actions are the only
    AuditLog rows with organization_id IS NULL (see every `record` call in
    this module), which is what separates this from any tenant's own log."""
    limit = max(1, min(limit, 200))
    query = select(AuditLog).where(
        AuditLog.organization_id.is_(None), AuditLog.action.like("platform.%"),
    )
    if action:
        query = query.where(AuditLog.action == action)
    if cursor:
        cursor_row = db.get(AuditLog, cursor)
        if cursor_row is not None:
            query = query.where(
                (AuditLog.created_at < cursor_row.created_at)
                | ((AuditLog.created_at == cursor_row.created_at) & (AuditLog.id < cursor_row.id))
            )
    rows = list(db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    actor_ids = {r.actor_user_id for r in rows if r.actor_user_id}
    actors = {u.id: u for u in db.scalars(select(User).where(User.id.in_(actor_ids or {""})))}
    return {
        "entries": [
            {
                "id": r.id, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
                "actor_email": actors[r.actor_user_id].email if r.actor_user_id in actors else None,
                "metadata": json.loads(r.metadata_json) if r.metadata_json else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "next_cursor": rows[-1].id if has_more and rows else None,
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


@router.get("/system-health")
def platform_system_health(admin: Admin, db: Db):
    """Operational readiness based on the live database and runtime settings.

    Deliberately returns booleans rather than any provider credential, URL
    containing secrets, or raw database connection string.
    """
    settings = get_settings()
    db.scalar(select(func.count(User.id)))  # real round trip; raises on failure
    database_profile = "postgresql" if settings.database_url.startswith("postgres") else "sqlite"

    latest_backup = None
    if BACKUP_DIR.exists():
        files = sorted(BACKUP_DIR.glob("backup_*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            newest = files[0]
            modified = datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)
            latest_backup = {
                "filename": newest.name,
                "modified_at": modified.isoformat(),
                "age_hours": round((datetime.now(timezone.utc) - modified).total_seconds() / 3600, 1),
                "size_bytes": newest.stat().st_size,
            }

    providers = [
        {
            "key": "bkash", "name": "bKash Merchant API", "category": "payment",
            "configured": all((settings.bkash_app_key, settings.bkash_app_secret,
                               settings.bkash_username, settings.bkash_password)),
        },
        {
            "key": "whatsapp", "name": "WhatsApp Cloud API", "category": "messaging",
            "configured": all((settings.whatsapp_phone_number_id, settings.whatsapp_access_token,
                               settings.whatsapp_verify_token, settings.whatsapp_app_secret)),
        },
        {
            "key": "sms", "name": "SMS gateway", "category": "messaging",
            "configured": all((settings.sms_api_key, settings.sms_sender_id)),
        },
        {
            "key": "ai", "name": "AI decision engine", "category": "intelligence",
            "configured": bool(settings.anthropic_api_key),
        },
    ]
    ready_count = sum(1 for provider in providers if provider["configured"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": settings.app_env,
        "auth_mode": settings.auth_mode,
        "integration_mode": settings.integration_mode,
        "database": {"profile": database_profile, "connected": True},
        "backup": {
            "supported_in_panel": database_profile == "sqlite",
            "latest": latest_backup,
        },
        "providers": providers,
        "provider_ready_count": ready_count,
        "provider_total": len(providers),
    }


@router.get("/integration-operations")
def platform_integration_operations(admin: Admin, db: Db):
    """Cross-tenant delivery telemetry without message bodies or full recipients."""
    status_rows = db.execute(
        select(OutboundMessage.status, func.count(OutboundMessage.id))
        .group_by(OutboundMessage.status)
    ).all()
    channel_rows = db.execute(
        select(OutboundMessage.channel, func.count(OutboundMessage.id))
        .group_by(OutboundMessage.channel)
    ).all()
    recent = db.execute(
        select(OutboundMessage, Organization)
        .join(Organization, Organization.id == OutboundMessage.organization_id)
        .order_by(OutboundMessage.created_at.desc()).limit(100)
    ).all()

    def masked(recipient: str) -> str:
        clean = recipient or ""
        return f"••••{clean[-4:]}" if len(clean) > 4 else "••••"

    return {
        "status_counts": {str(status): int(count) for status, count in status_rows},
        "channel_counts": {str(channel): int(count) for channel, count in channel_rows},
        "messages": [{
            "id": message.id,
            "organization_id": org.id,
            "organization_name": org.name,
            "channel": message.channel,
            "recipient_masked": masked(message.recipient),
            "template": message.template,
            "status": message.status,
            "last_error": message.last_error,
            "created_at": message.created_at.isoformat(),
            "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        } for message, org in recent],
    }


@router.get("/security")
def platform_security_posture(admin: Admin, db: Db):
    """Deployment-wide account and session security posture from real rows."""
    now = datetime.now(timezone.utc)
    users_total = db.scalar(select(func.count(User.id))) or 0
    users_active = db.scalar(select(func.count(User.id)).where(User.active.is_(True))) or 0
    mfa_enabled = db.scalar(select(func.count(User.id)).where(
        User.active.is_(True), User.mfa_enabled.is_(True),
    )) or 0
    platform_admins = db.scalar(select(func.count(User.id)).where(
        User.active.is_(True), User.is_platform_admin.is_(True),
    )) or 0
    sessions_active = db.scalar(select(func.count(UserSession.id)).where(
        UserSession.revoked_at.is_(None), UserSession.expires_at > now,
    )) or 0
    sessions_revoked = db.scalar(select(func.count(UserSession.id)).where(
        UserSession.revoked_at.is_not(None),
    )) or 0
    return {
        "generated_at": now.isoformat(),
        "users_total": users_total,
        "users_active": users_active,
        "users_inactive": max(0, users_total - users_active),
        "mfa_enabled": mfa_enabled,
        "mfa_missing": max(0, users_active - mfa_enabled),
        "mfa_coverage_percent": round((mfa_enabled / users_active) * 100, 1) if users_active else 0,
        "platform_admins": platform_admins,
        "sessions_active": sessions_active,
        "sessions_revoked": sessions_revoked,
    }


@router.get("/features")
def platform_feature_rollout(admin: Admin, db: Db):
    """Module rollout coverage and tenant exceptions for every feature flag."""
    orgs = list(db.scalars(select(Organization).order_by(Organization.name)))
    active_orgs = [org for org in orgs if org.active and org.suspended_at is None]
    rows = []
    for key in FEATURE_FLAGS:
        enabled_orgs = []
        disabled_orgs = []
        for org in active_orgs:
            flags = json.loads(org.feature_flags_json or "{}")
            target = enabled_orgs if flags.get(key, True) else disabled_orgs
            target.append({"id": org.id, "name": org.name, "slug": org.slug})
        total = len(active_orgs)
        rows.append({
            "key": key,
            "enabled_count": len(enabled_orgs),
            "disabled_count": len(disabled_orgs),
            "coverage_percent": round((len(enabled_orgs) / total) * 100, 1) if total else 0,
            "disabled_organizations": disabled_orgs,
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_organizations": len(active_orgs),
        "features": rows,
    }


@router.get("/trends")
def platform_trends(admin: Admin, db: Db, days: int = 30):
    """Real daily series across every tenant -- new organizations signed up
    and total sales volume, platform-wide. Never estimated or smoothed: a day
    with zero of either is a real zero, not an interpolated guess."""
    days = max(7, min(days, 180))
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    signup_rows = dict(db.execute(
        select(func.date(Organization.created_at), func.count(Organization.id))
        .where(Organization.created_at >= start)
        .group_by(func.date(Organization.created_at))
    ).all())
    sales_rows = dict(db.execute(
        select(func.date(SalesOrder.sold_at), func.coalesce(func.sum(SalesOrder.total), 0))
        .where(SalesOrder.sold_at >= start)
        .group_by(func.date(SalesOrder.sold_at))
    ).all())

    series = []
    for offset in range(days - 1, -1, -1):
        day = (now - timedelta(days=offset)).date()
        key = day.isoformat()
        series.append({
            "date": key,
            "new_organizations": int(signup_rows.get(key, 0) or 0),
            "sales_bdt": _money(sales_rows.get(key, 0)),
        })
    return {"days": days, "series": series}




# ── Backup / restore (SRD 15.1, NFR-DR-01/02) ───────────────────────────────
#
# A raw file copy of a live SQLite database can land mid-write and corrupt the
# copy; sqlite3's own online backup API (`Connection.backup`) takes a
# consistent snapshot even while the app keeps writing, so that is what both
# endpoints below use -- never `shutil.copy`.

@router.post("/backups")
def create_backup(admin: Admin, db: Db):
    """Take a consistent snapshot of the live database (Profile A / SQLite)."""
    source_path = _sqlite_path()
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest_path = BACKUP_DIR / f"backup_{stamp}.sqlite3"
    source = sqlite3.connect(str(source_path))
    try:
        dest = sqlite3.connect(str(dest_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    checksum = _checksum(dest_path)
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.backup_created",
        entity_type="backup", entity_id=dest_path.name,
        metadata_json=f'{{"checksum_sha256": "{checksum}", "size_bytes": {dest_path.stat().st_size}}}',
    ))
    db.commit()
    return {
        "filename": dest_path.name,
        "size_bytes": dest_path.stat().st_size,
        "checksum_sha256": checksum,
        "created_at": stamp,
    }


@router.get("/backups")
def list_backups(admin: Admin):
    if not BACKUP_DIR.exists():
        return {"backups": []}
    files = sorted(BACKUP_DIR.glob("backup_*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "backups": [
            {
                "filename": f.name, "size_bytes": f.stat().st_size,
                "checksum_sha256": _checksum(f),
                "modified_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
            for f in files
        ],
    }


@router.get("/backups/{filename}/download")
def download_backup(filename: str, admin: Admin):
    path = _backup_file(filename)
    return FileResponse(
        path=str(path), filename=path.name, media_type="application/vnd.sqlite3",
    )


@router.delete("/backups/{filename}")
def delete_backup(filename: str, admin: Admin, db: Db):
    path = _backup_file(filename)
    existing = list(BACKUP_DIR.glob("backup_*.sqlite3"))
    if len(existing) <= 1:
        raise HTTPException(status_code=409, detail="The last available backup cannot be deleted")
    checksum = _checksum(path)
    size = path.stat().st_size
    path.unlink()
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.backup_deleted",
        entity_type="backup", entity_id=filename,
        metadata_json=json.dumps({"checksum_sha256": checksum, "size_bytes": size}),
    ))
    db.commit()
    return {"status": "deleted", "filename": filename}


# Tables whose row count is cheap to check and tenant/financial-critical
# enough that a mismatch after restore means "stop, don't trust this backup".
_RECONCILE_TABLES = (
    "organizations", "users", "memberships", "branches", "products",
    "sales_orders", "journal_entries", "inventory_balances",
)


@router.post("/backups/{filename}/restore-drill")
def restore_drill(filename: str, admin: Admin, db: Db):
    """Restore a backup into a throwaway file and reconcile row counts -- never the live DB.

    This is the quarterly "can we actually restore this" drill NFR-DR-01 asks
    for, without the irreversible risk of overwriting production data from an
    API call. Promoting a verified backup to be the live database is a manual,
    out-of-band operator action (stop the app, swap the file, restart) by
    design -- not something this endpoint will ever do automatically.
    """
    backup_path = _backup_file(filename)

    live_path = _sqlite_path()
    verify_path = BACKUP_DIR / f"_verify_{filename}"
    source = sqlite3.connect(str(backup_path))
    try:
        dest = sqlite3.connect(str(verify_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    def _counts(path: Path) -> dict[str, int | None]:
        conn = sqlite3.connect(str(path))
        try:
            out: dict[str, int | None] = {}
            for table in _RECONCILE_TABLES:
                try:
                    out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.OperationalError:
                    out[table] = None  # table doesn't exist in this snapshot's schema version
            return out
        finally:
            conn.close()

    restored_counts = _counts(verify_path)
    live_counts = _counts(live_path)
    verify_path.unlink(missing_ok=True)

    mismatches = {
        table: {"live": live_counts[table], "restored": restored_counts[table]}
        for table in _RECONCILE_TABLES
        if live_counts[table] != restored_counts[table]
    }
    db.add(AuditLog(
        actor_user_id=admin.id, action="platform.restore_drill_run",
        entity_type="backup", entity_id=filename,
    ))
    db.commit()
    return {
        "filename": filename,
        "restorable": True,  # the backup file itself opened and read cleanly
        "row_counts": restored_counts,
        "live_row_counts": live_counts,
        "mismatches": mismatches,
        "reconciled": not mismatches,
    }


# ── Admin ↔ Business Messaging ─────────────────────────────────────────────

def _conv_row(conv: AdminConversation) -> dict:
    return {
        "id": conv.id,
        "organization_id": conv.organization_id,
        "organization_name": conv.organization.name if conv.organization else conv.organization_id,
        "unread_by_admin": conv.unread_by_admin,
        "unread_by_business": conv.unread_by_business,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "last_message_preview": conv.last_message_preview,
    }


def _msg_row(msg: AdminMessage) -> dict:
    return {
        "id": msg.id,
        "sender_type": msg.sender_type,
        "sender_name": (msg.sender.display_name or msg.sender.email) if msg.sender else "Platform Admin",
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
    }


def _get_or_create_conv(db: Session, org_id: str) -> AdminConversation:
    conv = db.scalars(
        select(AdminConversation).where(AdminConversation.organization_id == org_id)
    ).first()
    if not conv:
        conv = AdminConversation(organization_id=org_id)
        db.add(conv)
        db.flush()
    return conv


class AdminMsgIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


@router.get("/conversations")
def list_conversations(admin: Admin, db: Db):
    """List all org conversations, most recently active first."""
    convs = db.scalars(
        select(AdminConversation).order_by(AdminConversation.last_message_at.desc().nullslast())
    ).all()
    # Also include orgs with no conversation yet so admin can start one
    all_orgs = db.scalars(select(Organization).order_by(Organization.name)).all()
    conv_org_ids = {c.organization_id for c in convs}
    result = [_conv_row(c) for c in convs]
    for org in all_orgs:
        if org.id not in conv_org_ids:
            result.append({
                "id": None,
                "organization_id": org.id,
                "organization_name": org.name,
                "unread_by_admin": 0,
                "unread_by_business": 0,
                "last_message_at": None,
                "last_message_preview": None,
            })
    return {"conversations": result}


@router.get("/conversations/{org_id}/messages")
def get_conversation(org_id: str, admin: Admin, db: Db):
    """Fetch full thread for an org; marks admin's unread count as 0."""
    db.query(Organization).filter(Organization.id == org_id).first() or (_ for _ in ()).throw(
        HTTPException(status_code=404, detail="Organization not found")
    )
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    conv = db.scalars(
        select(AdminConversation).where(AdminConversation.organization_id == org_id)
    ).first()
    if not conv:
        return {"conversation_id": None, "messages": []}
    # Mark all business→admin messages as read
    now = utcnow()
    for m in conv.messages:
        if m.sender_type == "business" and m.read_at is None:
            m.read_at = now
    conv.unread_by_admin = 0
    db.commit()
    return {"conversation_id": conv.id, "messages": [_msg_row(m) for m in conv.messages]}


@router.post("/conversations/{org_id}/messages")
def send_message_to_org(org_id: str, body: AdminMsgIn, admin: Admin, db: Db):
    """Admin sends a message to an org."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    conv = _get_or_create_conv(db, org_id)
    now = utcnow()
    msg = AdminMessage(
        conversation_id=conv.id,
        sender_type="admin",
        sender_user_id=admin.id,
        content=body.content,
        created_at=now,
    )
    db.add(msg)
    conv.unread_by_business += 1
    conv.last_message_at = now
    conv.last_message_preview = body.content[:120]
    db.commit()
    db.refresh(msg)
    return _msg_row(msg)
