"""Operational product API, separate from the legacy research endpoints.

The thesis prototype currently uses the local development owner supplied by
``api.auth``. External identity-provider integration is intentionally deferred.
"""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .accounting import seed_default_accounts
from .approvals import seed_default_rules
from .loyalty import seed_default_rule as seed_default_loyalty_rule
from .commission import seed_default_rule as seed_default_commission_rule
from .app_schemas import OrganizationCreate, OrganizationOperations, OrganizationProfile, OrganizationView, UserView
from .audit import record_audit
from .auth import CurrentMembership, CurrentUser
from .permissions import require_permission
from .database import get_db
from .domain_models import AdminConversation, AdminMessage, AuditLog, Branch, Membership, Organization, OrganizationSetting, Product, SiteContent, utcnow

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


@router.get("/site-content", tags=["app-auth"])
def site_content(db: Db):
    """Public, unauthenticated: full site content — DB values merged over defaults."""
    from .site_defaults import SITE_DEFAULTS
    rows = list(db.scalars(select(SiteContent)))
    db_vals = {r.key: json.loads(r.value_json) for r in rows}
    return {"content": {**SITE_DEFAULTS, **db_vals}}


def _setting_values(setting: OrganizationSetting | None) -> dict:
    if setting is None:
        return {"business_mode": "products", "payment_methods": ["cash"], "sales_channels": ["in_store"], "reorder_budget_bdt": None}
    return {
        "business_mode": setting.business_mode,
        "payment_methods": json.loads(setting.payment_methods_json),
        "sales_channels": json.loads(setting.sales_channels_json),
        "reorder_budget_bdt": setting.reorder_budget_bdt,
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
        seed_default_loyalty_rule(db, organization.id)
        seed_default_commission_rule(db, organization.id)
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
            feature_flags=json.loads(org.feature_flags_json or "{}"),
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
    if payload.reorder_budget_bdt is not None:
        setting.reorder_budget_bdt = payload.reorder_budget_bdt
    record_audit(db, membership, "organization.operations_updated", "organization", org.id,
                 business_mode=payload.business_mode, payment_methods=payload.payment_methods,
                 sales_channels=payload.sales_channels, reorder_budget_bdt=payload.reorder_budget_bdt)
    db.commit()
    return OrganizationView(
        id=org.id, name=org.name, slug=org.slug, sector=org.sector, size_class=org.size_class,
        currency=org.currency, timezone=org.timezone, locale=org.locale, role=membership.role,
        uses_expiry=bool(db.scalar(select(Product.id).where(
            Product.organization_id == org.id, Product.track_expiry.is_(True)).limit(1))),
        address=org.address, phone=org.phone, vat_reg_no=org.vat_reg_no,
        receipt_footer=org.receipt_footer, **_setting_values(setting),
    )


# ── Business ↔ Admin Messaging ─────────────────────────────────────────────

class BusinessMsgIn(BaseModel):
    content: str = Field(default="", max_length=4000)
    attachment_url: str | None = Field(default=None, max_length=512)
    attachment_name: str | None = Field(default=None, max_length=260)
    attachment_size: int | None = None


def _msg_row(msg: AdminMessage) -> dict:
    return {
        "id": msg.id,
        "sender_type": msg.sender_type,
        "sender_name": (msg.sender.display_name or msg.sender.email) if msg.sender else "Platform Admin",
        "content": msg.content,
        "attachment_url": msg.attachment_url,
        "attachment_name": msg.attachment_name,
        "attachment_size": msg.attachment_size,
        "created_at": msg.created_at.isoformat(),
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
    }


@router.get("/messages")
def get_admin_messages(membership: CurrentMembership, db: Annotated[Session, Depends(get_db)]):
    """Business fetches their conversation thread with platform admin."""
    require_permission(membership, "organization:view")
    org_id = membership.organization_id
    conv = db.scalars(
        select(AdminConversation).where(AdminConversation.organization_id == org_id)
    ).first()
    if not conv:
        return {"conversation_id": None, "unread_by_business": 0, "messages": []}
    # Mark admin→business messages as read
    now = utcnow()
    for m in conv.messages:
        if m.sender_type == "admin" and m.read_at is None:
            m.read_at = now
    conv.unread_by_business = 0
    db.commit()
    return {
        "conversation_id": conv.id,
        "unread_by_business": 0,
        "messages": [_msg_row(m) for m in conv.messages],
    }


@router.get("/messages/unread-count")
def messages_unread_count(membership: CurrentMembership, db: Annotated[Session, Depends(get_db)]):
    """Lightweight poll endpoint for badge — no read marking."""
    require_permission(membership, "organization:view")
    conv = db.scalars(
        select(AdminConversation).where(AdminConversation.organization_id == membership.organization_id)
    ).first()
    return {"unread": conv.unread_by_business if conv else 0}


@router.post("/messages")
def reply_to_admin(
    body: BusinessMsgIn,
    membership: CurrentMembership,
    db: Annotated[Session, Depends(get_db)],
):
    """Business user replies to the platform admin."""
    require_permission(membership, "organization:view")
    org_id = membership.organization_id
    conv = db.scalars(
        select(AdminConversation).where(AdminConversation.organization_id == org_id)
    ).first()
    if not conv:
        # Auto-create conversation when business initiates
        conv = AdminConversation(organization_id=org_id)
        db.add(conv)
        db.flush()
    now = utcnow()
    if not body.content.strip() and not body.attachment_url:
        raise HTTPException(status_code=422, detail="content or attachment required")
    msg = AdminMessage(
        conversation_id=conv.id,
        sender_type="business",
        sender_user_id=membership.user_id,
        content=body.content,
        attachment_url=body.attachment_url,
        attachment_name=body.attachment_name,
        attachment_size=body.attachment_size,
        created_at=now,
    )
    db.add(msg)
    conv.unread_by_admin += 1
    conv.last_message_at = now
    conv.last_message_preview = (body.attachment_name or body.content)[:120]
    db.commit()
    db.refresh(msg)
    return _msg_row(msg)


_CHAT_UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "chat"
_ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel", "text/csv", "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/messages/upload")
async def upload_chat_file(
    file: UploadFile = File(...),
    membership: CurrentMembership = None,
):
    """Upload a file attachment for a chat message. Returns url + filename."""
    require_permission(membership, "organization:view")
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"ফাইলের ধরন সমর্থিত নয়: {file.content_type}")
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="ফাইল সর্বোচ্চ ১০ MB হতে পারবে")
    _CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import uuid, os
    ext = os.path.splitext(file.filename or "")[1][:10]
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = _CHAT_UPLOAD_DIR / filename
    dest.write_bytes(data)
    url = f"/api/app/messages/uploads/{filename}"
    return {"url": url, "filename": file.filename or filename, "size": len(data)}
