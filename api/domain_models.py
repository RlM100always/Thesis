"""Core multi-tenant operational schema for Bangladeshi retail SMEs.

All business-owned records carry ``organization_id``. Inventory is an
append-only movement ledger; balances are derived rather than overwritten.
Amounts use Decimal-backed NUMERIC columns and timestamps are stored in UTC.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(40), default="retail")
    size_class: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="BDT")
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Dhaka")
    locale: Mapped[str] = mapped_column(String(10), default="bn-BD")
    # Printed on receipts and reports.
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(30))
    vat_reg_no: Mapped[str | None] = mapped_column(String(40))
    receipt_footer: Mapped[str | None] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Platform-admin suspend, distinct from `active`: a suspended org's own
    # owner/staff see a "contact support" lock screen instead of logging in,
    # vs. an org that deactivated itself. Null means never suspended.
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_reason: Mapped[str | None] = mapped_column(String(300))
    # JSON object of {flag_key: bool}; a missing key means "enabled" (opt-out,
    # not opt-in), so adding a new module never silently locks out every
    # existing tenant. Only a platform admin ever writes this.
    feature_flags_json: Mapped[str | None] = mapped_column(Text)


class OrganizationSetting(Base, TimestampMixin):
    """Operational choices that shape an organization's workspace.

    Kept in its own table so older installations can gain the settings through
    ``create_schema`` without an unsafe rewrite of the core organization row.
    JSON stores small validated lists only; credentials never belong here.
    """

    __tablename__ = "organization_settings"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    business_mode: Mapped[str] = mapped_column(String(20), default="products")
    payment_methods_json: Mapped[str] = mapped_column(Text, default='["cash"]')
    sales_channels_json: Mapped[str] = mapped_column(Text, default='["in_store"]')
    # None = not declared yet -- the live B-SMART engine (api/bsmart_live.py)
    # must not invent a budget cap when the owner hasn't set a real one.
    reorder_budget_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class ReferenceValue(Base, TimestampMixin):
    """Auditable public reference data shared by all organizations."""

    __tablename__ = "reference_values"
    __table_args__ = (UniqueConstraint("kind", "code"), Index("ix_reference_kind_parent", "kind", "parent_code"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(30), index=True)
    parent_code: Mapped[str | None] = mapped_column(String(50), index=True)
    label_en: Mapped[str] = mapped_column(String(120))
    label_bn: Mapped[str] = mapped_column(String(120))
    details: Mapped[str | None] = mapped_column(String(240))
    source_url: Mapped[str] = mapped_column(String(500))
    verified_on: Mapped[date] = mapped_column(Date)


class OutboundMessage(Base, TimestampMixin):
    """Durable SMS/WhatsApp outbox; provider secrets are never stored here."""

    __tablename__ = "outbound_messages"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    recipient: Mapped[str] = mapped_column(String(40))
    template: Mapped[str] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(160))
    last_error: Mapped[str | None] = mapped_column(String(500))
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    # Small profile photo stored inline as a data: URL -- this app has no
    # object storage (S3/GCS) anywhere, so a second storage system just for
    # avatars would be new infrastructure for one field. Capped at ~300KB by
    # the upload endpoint, resized client-side first; fine for a face photo.
    avatar_data_url: Mapped[str | None] = mapped_column(Text)
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # Bumped on logout / password change; tokens carry the value they were issued
    # under, so bumping it revokes every outstanding token for this user.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # One-time "set your password" token for invited staff (and admin-issued
    # resets). Stored as a SHA-256 digest; the raw value is shown once.
    setup_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    setup_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Platform-level super-admin: sees every organization, not just ones they
    # have a Membership in. The first account is bootstrapped directly; later
    # grants are MFA-gated, self-lockout protected and audit logged by the
    # platform administrator governance API.
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # TOTP MFA (AUTH-003). The secret is set on /mfa/setup but mfa_enabled only
    # flips true once the owner proves they can generate a matching code on
    # /mfa/enable -- a secret alone, never confirmed, must not gate login.
    mfa_totp_secret: Mapped[str | None] = mapped_column(String(64))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # JSON list of SHA-256 digests; each one-time recovery code is removed
    # (not just marked used) the moment it is spent.
    mfa_recovery_codes_json: Mapped[str | None] = mapped_column(Text)


class UserSession(Base, TimestampMixin):
    """One rotating-refresh-token family (one logged-in device/browser).

    ``current_jti_hash`` is the SHA-256 digest of the one refresh token that is
    currently valid for this session; every ``/auth/refresh`` call replaces it
    (rotation). A refresh call presenting a *previous* token's jti means that
    token was stolen and already used elsewhere, or replayed -- the whole
    session is revoked rather than trusted (AUTH-005 reuse detection).
    """

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    current_jti_hash: Mapped[str] = mapped_column(String(64), index=True)
    device_label: Mapped[str | None] = mapped_column(String(200))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(60))


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="cashier")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Monthly base salary for payroll (SRD Panel H06). Null means "not set yet" --
    # such a person is skipped when a payroll run is generated, not paid ৳0.
    base_salary: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    division: Mapped[str | None] = mapped_column(String(30))
    district: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Warehouse(Base, TimestampMixin):
    """A physical stock location under a branch (SRD 11.1 Tenant aggregate).

    A branch may have more than one: a shop floor plus a back-room store, for
    example. Stock movements/balances reference ``warehouse_id`` once a
    warehouse exists for their branch; a branch with none keeps stock at
    branch granularity (backward compatible with installations before this
    table existed).
    """

    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("branch_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class MembershipBranch(Base, TimestampMixin):
    """Branch-scoping for a membership (SRD 2.3 ABAC: ``branch_id in assigned_branches``).

    No rows for a membership means org-wide access (the default today, and
    how ``owner``/``accountant`` typically operate). Any row present narrows
    that membership to only the listed branches -- enforced in
    ``api/permissions.py: require_branch_access``.
    """

    __tablename__ = "membership_branches"
    __table_args__ = (UniqueConstraint("membership_id", "branch_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    membership_id: Mapped[str] = mapped_column(ForeignKey("memberships.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), index=True)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku"),
        CheckConstraint("selling_price >= 0"),
        CheckConstraint("cost_price >= 0"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(80))
    barcode: Mapped[str | None] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    # Price for customers on the wholesale tier; null means the product has no wholesale price.
    wholesale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    # When true, stock is held in batches with expiry dates and sold first-expiry-
    # first-out (FEFO). Pharmacy products are tracked; plain goods need not be.
    track_expiry: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str | None] = mapped_column(String(160))
    phone_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    # Most this customer may owe on credit; null means no limit has been set.
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    price_tier: Mapped[str] = mapped_column(String(20), default="retail", server_default="retail")


class SupportTicket(Base, TimestampMixin):
    """Customer support ticket (SRD Panel C07). Status is a small fixed set,
    not free text, so a Support dashboard can filter/count reliably."""

    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="general")
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # low/normal/high/urgent
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open/pending/resolved/closed
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assigned_to_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketMessage(Base, TimestampMixin):
    """One conversation entry on a ticket. ``internal`` marks a staff-only note,
    never shown on a future Customer Portal view of the same ticket."""

    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Lead(Base, TimestampMixin):
    """A prospective customer moving through a sales pipeline (SRD Panel C06).

    Converting a won lead creates a real ``Customer`` row (``converted_customer_id``);
    a lead itself never has a credit limit, loyalty balance or sales history --
    those only make sense for an actual customer.
    """

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    source: Mapped[str | None] = mapped_column(String(60))
    stage: Mapped[str] = mapped_column(String(20), default="new", index=True)
    # new -> qualified -> quoted -> won/lost
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    lost_reason: Mapped[str | None] = mapped_column(String(200))
    converted_customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeadActivity(Base, TimestampMixin):
    """One logged touch-point (call, visit, note) on a lead."""

    __tablename__ = "lead_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(Text)


class Feedback(Base, TimestampMixin):
    """Post-sale/delivery feedback (SRD Panel C08). ``score`` is an NPS-style
    0-10 rating; nothing here is fabricated -- only what the customer actually
    submitted is stored, and a low score is meant to drive a follow-up, not a
    public rating display.
    """

    __tablename__ = "feedback_entries"
    __table_args__ = (CheckConstraint("score >= 0 AND score <= 10"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    sales_order_id: Mapped[str | None] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    follow_up_ticket_id: Mapped[str | None] = mapped_column(ForeignKey("support_tickets.id"))


class Notification(Base, TimestampMixin):
    """An in-app bell-icon notification for one person (SRD Panel G03).

    Always created server-side by a domain event (a ticket, an approval, a low
    stock alert), never by direct API write -- a notification is a pointer to
    something real that happened, not freestanding content a client can inject.
    """

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20))  # action_required/money/stock/staff/system/security
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info/warning/critical
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link_type: Mapped[str | None] = mapped_column(String(30))
    link_id: Mapped[str | None] = mapped_column(String(36))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttendanceRecord(Base, TimestampMixin):
    """One check-in/check-out pair (SRD Panel H03). ``source`` says how it was
    created; a manager correction never edits the original row -- it adds a
    new one with ``source="manager_correction"`` and ``corrects_record_id``
    pointing at the one being fixed, so the original stays on the books.
    """

    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="device")  # device/manager_correction/import
    corrects_record_id: Mapped[str | None] = mapped_column(ForeignKey("attendance_records.id"))
    note: Mapped[str | None] = mapped_column(String(300))


class LeaveRequest(Base, TimestampMixin):
    """A staff leave request (SRD Panel H04): submit -> approve/reject -> (cancel
    while still pending). Dates are inclusive calendar dates, not timestamps --
    leave is taken in whole/half days, not at a specific minute."""

    __tablename__ = "leave_requests"
    __table_args__ = (CheckConstraint("end_date >= start_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30), default="casual")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(300))


class RosterShift(Base, TimestampMixin):
    """A planned shift assignment (SRD Panel H02) -- separate from `AttendanceRecord`,
    which is what actually happened. The roster is the plan; attendance is the fact."""

    __tablename__ = "roster_shifts"
    __table_args__ = (CheckConstraint("end_time > start_time"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    shift_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[str] = mapped_column(String(5))  # "HH:MM", 24h
    end_time: Mapped[str] = mapped_column(String(5))
    station: Mapped[str | None] = mapped_column(String(60))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    typical_lead_days: Mapped[int] = mapped_column(Integer, default=0)


class Store(Base, TimestampMixin):
    """One optional public storefront per organization.

    Activating a store does not affect normal POS or inventory operations —
    it only opens a public URL at /store/{org_id} where anonymous buyers can
    browse listed products and place online orders. All settings here control
    what the public page shows; nothing financial is ever visible.
    """

    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    display_name: Mapped[str] = mapped_column(String(160))
    tagline: Mapped[str | None] = mapped_column(String(300))
    # Logo and cover stored inline as data: URLs (same pattern as User.avatar_data_url).
    logo_data_url: Mapped[str | None] = mapped_column(Text)
    cover_data_url: Mapped[str | None] = mapped_column(Text)
    theme_preset: Mapped[str] = mapped_column(String(20), default="clean")
    theme_color: Mapped[str] = mapped_column(String(7), default="#0a8752")
    category: Mapped[str | None] = mapped_column(String(60))
    area: Mapped[str | None] = mapped_column(String(120))
    # Visibility toggles — all default to the privacy-first setting.
    show_phone: Mapped[bool] = mapped_column(Boolean, default=False)
    show_exact_address: Mapped[bool] = mapped_column(Boolean, default=False)
    show_hours: Mapped[bool] = mapped_column(Boolean, default=True)
    show_stock_level: Mapped[str] = mapped_column(String(20), default="available_only")
    show_price: Mapped[bool] = mapped_column(Boolean, default=True)
    # Payment methods accepted at checkout.
    payment_cod: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_bkash: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_nagad: Mapped[bool] = mapped_column(Boolean, default=False)
    min_order_bdt: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    delivery_note: Mapped[str | None] = mapped_column(String(300))
    hours_json: Mapped[str | None] = mapped_column(Text)
    meta_title: Mapped[str | None] = mapped_column(String(160))
    meta_desc: Mapped[str | None] = mapped_column(String(320))


class StoreProduct(Base, TimestampMixin):
    """Opt-in listing of an existing Product on this org's storefront.

    Only products with is_listed=True appear in the public catalog. The
    owner can override the selling price, add a longer description, upload
    a product photo, and tag items for filtering — none of that touches the
    canonical Product record used by the POS.
    """

    __tablename__ = "store_products"
    __table_args__ = (UniqueConstraint("store_id", "product_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    is_listed: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    online_price_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    description_long: Mapped[str | None] = mapped_column(Text)
    image_data_url: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(300))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    max_order_qty: Mapped[int | None] = mapped_column(Integer)


class SalesOrder(Base, TimestampMixin):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number"),
        CheckConstraint("subtotal >= 0 AND discount_amount >= 0 AND tax_amount >= 0 AND total >= 0"),
        Index("ix_sales_org_branch_time", "organization_id", "branch_id", "sold_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(80))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(30), default="in_store")
    status: Mapped[str] = mapped_column(String(30), default="completed")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    items: Mapped[list[SalesOrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class SyncOperation(Base, TimestampMixin):
    """Durable receipt for an offline/retriable client mutation."""

    __tablename__ = "sync_operations"
    __table_args__ = (UniqueConstraint("organization_id", "operation_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(String(100), index=True)
    operation_type: Mapped[str] = mapped_column(String(30), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)


class SalesOrderItem(Base, TimestampMixin):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price >= 0 AND discount_amount >= 0 AND line_total >= 0"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_cost_at_sale: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    order: Mapped[SalesOrder] = relationship(back_populates="items")


class SalesDocument(Base, TimestampMixin):
    """A pre-invoice commercial document: quotation or fulfilment order.

    It reserves no stock and posts no money. Only conversion to a real invoice
    goes through the canonical sale path, keeping inventory and accounting in
    one implementation.
    """

    __tablename__ = "sales_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_number"),
        CheckConstraint("document_type in ('quotation','order')", name="ck_sales_document_type"),
        Index("ix_sales_document_org_time", "organization_id", "issued_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(20), index=True)
    document_number: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), index=True)
    channel: Mapped[str] = mapped_column(String(30), default="in_store")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_until: Mapped[date | None] = mapped_column(Date)
    expected_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    # Set only for an order placed through the public online-storefront
    # checkout, where there is no staff member to key in a walk-in sale and
    # often no existing Customer record at all.
    shipping_name: Mapped[str | None] = mapped_column(String(160))
    shipping_phone: Mapped[str | None] = mapped_column(String(32))
    shipping_address: Mapped[str | None] = mapped_column(Text)
    # Unguessable token handed back to the customer at checkout so they can
    # look up their own order status without an account. Null for orders that
    # were never placed through the public endpoint.
    access_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    lines: Mapped[list["SalesDocumentLine"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class SalesDocumentLine(Base, TimestampMixin):
    __tablename__ = "sales_document_lines"
    __table_args__ = (CheckConstraint("quantity > 0 AND unit_price >= 0 AND discount_amount >= 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("sales_documents.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    document: Mapped[SalesDocument] = relationship(back_populates="lines")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    method: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Which cashier drawer this belongs to, when the cashier had a shift open
    # at sale time (api/shift_routes.py). Null for sales made with no open
    # shift -- shifts are additive accountability, not a hard requirement.
    shift_id: Mapped[str | None] = mapped_column(ForeignKey("cashier_shifts.id"), index=True)


class StockMovement(Base, TimestampMixin):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity_delta <> 0"),
        Index("ix_stock_org_branch_product_time", "organization_id", "branch_id", "product_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(30))
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    # Set for movements of expiry-tracked products, so the ledger says *which* batch.
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Batch(Base, TimestampMixin):
    """One lot of a product, as printed on the pack: batch number and expiry.

    Stock per branch lives in ``BatchStock``. A batch with ``status='blocked'``
    (recall, quarantine, damaged) is never sold, whatever its expiry.
    """

    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("organization_id", "product_id", "batch_no"),
        CheckConstraint("status in ('active','blocked')", name="ck_batch_status"),
        Index("ix_batch_org_expiry", "organization_id", "expiry_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    batch_no: Mapped[str] = mapped_column(String(80))
    expiry_date: Mapped[date | None] = mapped_column(Date)  # None = unknown / does not expire
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # None = cost not known
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(20), default="purchase")  # purchase|opening|adjustment|return
    status: Mapped[str] = mapped_column(String(12), default="active")
    status_reason: Mapped[str | None] = mapped_column(String(160))


class BatchStock(Base, TimestampMixin):
    """Units of a batch held at one branch. Never negative."""

    __tablename__ = "batch_stock"
    __table_args__ = (
        UniqueConstraint("branch_id", "batch_id"),
        CheckConstraint("quantity >= 0"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)


class StockCount(Base, TimestampMixin):
    """A physical stock take at one branch: system quantities snapshotted at the
    start, counted quantities entered against them, variances applied on
    completion. Expiry-tracked products are out of scope here — a variance on
    one of those needs a batch to attribute it to, which "মেয়াদ ও ব্যাচ" already
    handles per-batch; counting everything else together would either guess the
    batch or ask a question this workflow has no good place to ask."""

    __tablename__ = "stock_counts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | completed
    note: Mapped[str | None] = mapped_column(String(300))
    started_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list[StockCountLine]] = relationship(back_populates="count", cascade="all, delete-orphan")


class StockCountLine(Base, TimestampMixin):
    """One product's system quantity at the moment counting started, and what
    was actually counted (null until entered). Never edited after the count
    completes — a wrong count is corrected with a new stock take, not by
    silently rewriting history."""

    __tablename__ = "stock_count_lines"
    __table_args__ = (UniqueConstraint("stock_count_id", "product_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    stock_count_id: Mapped[str] = mapped_column(ForeignKey("stock_counts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    system_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    counted_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    count: Mapped[StockCount] = relationship(back_populates="lines")


class SaleItemBatch(Base, TimestampMixin):
    """Which batches a sale line was filled from.

    Lets a return go back to the batch it came from, and lets a recall answer
    "who bought from this batch?".
    """

    __tablename__ = "sale_item_batches"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sales_order_item_id: Mapped[str] = mapped_column(ForeignKey("sales_order_items.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)


class CashClose(Base, TimestampMixin):
    """End-of-day cash count for a branch: what the books say should be in the drawer,
    what was counted, and the difference (never quietly forced to zero)."""

    __tablename__ = "cash_closes"
    __table_args__ = (UniqueConstraint("organization_id", "branch_id", "business_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    business_date: Mapped[date] = mapped_column(Date)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    counted_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    variance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    breakdown_json: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(300))
    closed_by: Mapped[str | None] = mapped_column(String(36))


class CashierShift(Base, TimestampMixin):
    """A cashier's own drawer accountability window -- distinct from
    ``CashClose``, which is the owner/accountant's once-a-day book for the
    whole branch. A shift is opened with a counted float, every cash sale and
    refund made while it is open belongs to it, and it is closed with its own
    count and variance. Several cashiers can each have their own open shift
    on the same branch on the same day."""

    __tablename__ = "cashier_shifts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    drawer_label: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | closed
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    variance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    note: Mapped[str | None] = mapped_column(String(300))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(36))


class CashMovement(Base, TimestampMixin):
    """Cash physically added to or removed from a drawer mid-shift (a drop to
    the safe, topping up change) -- not a sale, refund or expense, but it
    still changes what should be left in the drawer at close."""

    __tablename__ = "cash_movements"
    __table_args__ = (CheckConstraint("amount > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("cashier_shifts.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(10))  # drop | add
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[str | None] = mapped_column(String(36))


class InventoryBalance(Base, TimestampMixin):
    """Lockable projection of the append-only movement ledger."""

    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_id", "product_id"),
        CheckConstraint("quantity >= 0"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_method: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    incurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoyaltyRule(Base, TimestampMixin):
    """How fast a customer earns points, and what a point is worth when spent.
    One row per organization; a missing or inactive row means loyalty is off —
    sales still work exactly the same, just without points."""

    __tablename__ = "loyalty_rules"
    __table_args__ = (UniqueConstraint("organization_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    # A customer earns 1 point per this many taka of net sale (before tax).
    points_per_taka: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # What redeeming 1 point is worth off a bill, in taka.
    redemption_value: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoyaltyEntry(Base, TimestampMixin):
    """One earn or redeem event. A running balance is this table's sum for the
    customer — an append-only ledger, the same discipline as `LedgerEntry`."""

    __tablename__ = "loyalty_entries"
    __table_args__ = (CheckConstraint("points_delta <> 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    points_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(String(20))  # earned | redeemed | adjusted
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SalesTarget(Base, TimestampMixin):
    """A sales quota for one person over one period (SRD Panel H05).

    Progress is never stored here -- it's computed on read from `SalesOrder` +
    `AuditLog` (who actually rang up each sale), so it can never drift from
    what the sales ledger says actually happened.
    """

    __tablename__ = "sales_targets"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "period_start"),
        CheckConstraint("period_end >= period_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class CommissionRule(Base, TimestampMixin):
    """A flat percentage of net sale revenue paid to whoever rang up the sale
    (SRD Panel H05). One row per organization, same pattern as `LoyaltyRule` --
    inactive until the owner turns it on, so sales work identically either way.
    """

    __tablename__ = "commission_rules"
    __table_args__ = (UniqueConstraint("organization_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class CommissionEntry(Base, TimestampMixin):
    """One earn or clawback event -- append-only, same discipline as `LoyaltyEntry`.
    A return/void of a commissioned sale clawbacks proportionally, it never
    rewrites the original earn row."""

    __tablename__ = "commission_entries"
    __table_args__ = (CheckConstraint("amount <> 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sales_order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str] = mapped_column(String(20))  # earned | clawback
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Delivery(Base, TimestampMixin):
    """A rider's assignment to deliver one invoiced sale (SRD Panels E04-E06).

    "Delivered" and "the business has the COD cash" are different facts, kept
    as different states here -- ``status="delivered"`` only means the package
    reached the customer; the money isn't counted until a `CODHandover` row
    exists for it.
    """

    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    sales_order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    rider_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="assigned", index=True)
    # assigned -> out_for_delivery -> delivered/failed
    cod_amount_expected: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cod_amount_collected: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    proof_note: Mapped[str | None] = mapped_column(String(300))
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class CODHandover(Base, TimestampMixin):
    """The rider physically gives collected cash to a cashier -- a separate,
    later fact from `Delivery.cod_amount_collected`, with a shortage computed
    rather than assumed to always match."""

    __tablename__ = "cod_handovers"
    __table_args__ = (UniqueConstraint("delivery_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    delivery_id: Mapped[str] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"), index=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("cashier_shifts.id"), index=True)
    handed_over_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    shortage_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    received_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class StaffAdvance(Base, TimestampMixin):
    """A cash advance issued to staff (SRD Panel H06), repaid over time.

    Standalone for now -- there is no payroll run yet to net it against
    automatically (CLAUDE.md: don't fake a feature that doesn't exist), so
    repayment here is recorded explicitly rather than deducted from a payslip.
    """

    __tablename__ = "staff_advances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="outstanding", index=True)  # outstanding/settled
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class StaffAdvanceRepayment(Base, TimestampMixin):
    __tablename__ = "staff_advance_repayments"
    __table_args__ = (CheckConstraint("amount > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    advance_id: Mapped[str] = mapped_column(ForeignKey("staff_advances.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class PayrollRun(Base, TimestampMixin):
    """One pay period's payroll (SRD Panel H06): draft -> approved -> paid.

    Once approved, `PayrollLine` rows are frozen -- a mistake found later is a
    new, separate run or an explicit adjustment, never a silent edit to a
    period someone has already been told their pay for.
    """

    __tablename__ = "payroll_runs"
    __table_args__ = (UniqueConstraint("organization_id", "period_start", "period_end"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft/approved/paid
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayrollLine(Base, TimestampMixin):
    """One person's pay within a `PayrollRun` -- a frozen snapshot once the run
    is approved, same discipline as a `SalesOrder` line after it's invoiced."""

    __tablename__ = "payroll_lines"
    __table_args__ = (UniqueConstraint("payroll_run_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    payroll_run_id: Mapped[str] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    advance_deduction: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class FiscalPeriod(Base, TimestampMixin):
    """One calendar month's accounting lock (SRD Panel F09).

    No row for a month means it's open -- periods aren't pre-created, only
    recorded when someone actually closes one. `post_journal` refuses any
    entry whose `occurred_at` falls in a closed month; reopening is a
    separate, audited, explicit action, never implicit.
    """

    __tablename__ = "fiscal_periods"
    __table_args__ = (UniqueConstraint("organization_id", "period_month"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    period_month: Mapped[date] = mapped_column(Date)  # always the 1st of the month
    status: Mapped[str] = mapped_column(String(10), default="closed")  # closed | reopened
    closed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reopened_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_reason: Mapped[str | None] = mapped_column(String(300))


class Reservation(Base, TimestampMixin):
    """Stock earmarked for one order line before it is invoiced (SRD Panel E02).

    Never touches `InventoryBalance.quantity` -- on-hand stays exactly what is
    physically there. Availability is computed as on-hand minus the sum of
    *other* active, unexpired reservations (see `reservations.py`), so a
    reservation makes stock unavailable to everyone else without ever lying
    about what is actually on the shelf.
    """

    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    sales_document_id: Mapped[str] = mapped_column(ForeignKey("sales_documents.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)  # active/released/fulfilled
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class ApprovalRule(Base, TimestampMixin):
    """A threshold an owner set: an action of this ``kind`` at or above ``threshold``
    needs someone holding ``approver_role`` (or higher) to sign off before it takes
    effect. One row per kind per organization; a missing row means no gate."""

    __tablename__ = "approval_rules"
    __table_args__ = (UniqueConstraint("organization_id", "kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    threshold: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    approver_role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalRequest(Base, TimestampMixin):
    """An action held back by an `ApprovalRule` until a qualified role decides it.

    ``payload`` is the original request as JSON (validated the same way the direct
    endpoint would validate it); approving replays it through the same code path
    that would have run immediately if no rule had applied, so an approved expense
    is indistinguishable from one nobody needed to approve."""

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payload: Mapped[str] = mapped_column(Text)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/approved/rejected
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(300))
    # Set once the approved action has actually been created (e.g. the Expense id),
    # so an approval can never be replayed twice.
    result_reference_id: Mapped[str | None] = mapped_column(String(36))


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "order_number"),
        CheckConstraint("total >= 0"),
        Index("ix_purchase_org_branch_time", "organization_id", "branch_id", "ordered_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(80))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ordered")
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class PurchaseOrderItem(Base, TimestampMixin):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND unit_cost >= 0"),
        CheckConstraint("received_quantity >= 0 AND received_quantity <= quantity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class PurchaseReturn(Base, TimestampMixin):
    """A supplier claim raised against goods that were actually received.

    Stock leaves only when the claim is dispatched.  The supplier balance is
    reduced later, when their credit note is accepted, so an unaccepted claim
    can never silently understate Accounts Payable.
    """

    __tablename__ = "purchase_returns"
    __table_args__ = (
        UniqueConstraint("organization_id", "return_number"),
        UniqueConstraint("organization_id", "supplier_id", "credit_note_number"),
        CheckConstraint("total >= 0"),
        CheckConstraint(
            "status in ('submitted','dispatched','settled','rejected')",
            name="ck_purchase_return_status",
        ),
        Index("ix_purchase_return_org_time", "organization_id", "submitted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    return_number: Mapped[str] = mapped_column(String(80))
    claim_type: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credit_note_number: Mapped[str | None] = mapped_column(String(100))
    supplier_note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[PurchaseReturnItem]] = relationship(back_populates="purchase_return", cascade="all, delete-orphan")


class PurchaseReturnItem(Base, TimestampMixin):
    __tablename__ = "purchase_return_items"
    __table_args__ = (CheckConstraint("quantity > 0 AND unit_cost >= 0 AND amount >= 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    purchase_return_id: Mapped[str] = mapped_column(ForeignKey("purchase_returns.id", ondelete="CASCADE"), index=True)
    purchase_order_item_id: Mapped[str] = mapped_column(ForeignKey("purchase_order_items.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    purchase_return: Mapped[PurchaseReturn] = relationship(back_populates="items")


class LedgerEntry(Base, TimestampMixin):
    """Signed subledger entry: positive creates a balance, negative settles it."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount_delta <> 0"),
        Index("ix_ledger_org_type_party_time", "organization_id", "ledger_type", "party_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    ledger_type: Mapped[str] = mapped_column(String(20))  # payable/receivable/expense
    party_type: Mapped[str | None] = mapped_column(String(20))
    party_id: Mapped[str | None] = mapped_column(String(36), index=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    amount_delta: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_method: Mapped[str | None] = mapped_column(String(30))
    reference_type: Mapped[str] = mapped_column(String(30))
    reference_id: Mapped[str] = mapped_column(String(36), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Account(Base, TimestampMixin):
    """One line of the shop's chart of accounts. Seeded automatically for every
    organization (``api/accounting.py::DEFAULT_ACCOUNTS``); an owner may add more
    but the seeded ones (``is_system``) may not be deleted — the posting code
    depends on their codes existing."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    # asset / liability / equity / revenue / expense — decides the trial balance's
    # normal side and which line of the P&L a revenue/expense account feeds.
    type: Mapped[str] = mapped_column(String(20))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class JournalEntry(Base, TimestampMixin):
    """One business event, in double-entry form. Never edited after posting —
    a mistake is corrected with a reversing entry, so the trail stays honest."""

    __tablename__ = "journal_entries"
    __table_args__ = (Index("ix_journal_org_time", "organization_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    memo: Mapped[str | None] = mapped_column(String(200))
    reference_type: Mapped[str] = mapped_column(String(30))
    reference_id: Mapped[str] = mapped_column(String(36), index=True)

    lines: Mapped[list[JournalLine]] = relationship(back_populates="entry", cascade="all, delete-orphan")


class JournalLine(Base, TimestampMixin):
    """A debit or a credit (never both) against one account. A line never stands
    alone — ``post_journal`` in ``api/accounting.py`` is the only way to create
    one, and it refuses an entry whose debits and credits do not match."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0"),
        CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)"),
        Index("ix_journal_line_account", "organization_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    journal_entry_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    party_type: Mapped[str | None] = mapped_column(String(20))
    party_id: Mapped[str | None] = mapped_column(String(36), index=True)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")


class SalesReturn(Base, TimestampMixin):
    __tablename__ = "sales_returns"
    __table_args__ = (UniqueConstraint("organization_id", "return_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), index=True)
    sales_order_id: Mapped[str] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    return_number: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(160))
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class SalesReturnItem(Base, TimestampMixin):
    __tablename__ = "sales_return_items"
    __table_args__ = (CheckConstraint("quantity > 0 AND amount >= 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sales_return_id: Mapped[str] = mapped_column(ForeignKey("sales_returns.id", ondelete="CASCADE"), index=True)
    sales_order_item_id: Mapped[str] = mapped_column(ForeignKey("sales_order_items.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    restock: Mapped[bool] = mapped_column(Boolean, default=True)


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"
    __table_args__ = (CheckConstraint("amount > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    sales_return_id: Mapped[str] = mapped_column(ForeignKey("sales_returns.id"), index=True)
    method: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference: Mapped[str | None] = mapped_column(String(120))
    refunded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_org_time", "organization_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("organization_id", "checksum_sha256"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_system: Mapped[str] = mapped_column(String(80), default="unknown")
    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    mapping_json: Mapped[str | None] = mapped_column(Text)
    validation_json: Mapped[str | None] = mapped_column(Text)


# ─────────────────────────────────────────────────────────────────────────────
# B-SMART architecture layers 9 and 10: owner decision, outcome and monitoring.
#
# Layers 1-8 end with a ranked, explained recommendation. Without the two
# tables below the loop is open: the system advises and never learns whether
# the advice was taken or whether it worked. These close it, and they are what
# any business-outcome claim in the thesis must be evidenced from.
# ─────────────────────────────────────────────────────────────────────────────


class Recommendation(Base, TimestampMixin):
    """One action emitted by B-SMART Algorithm 1 at a given cutoff.

    Persisted verbatim -- utility terms, the constraint verdicts and the
    explanation -- so a recommendation can still be audited after the model
    that produced it has been retrained or replaced.
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_reco_org_cutoff", "organization_id", "cutoff_date"),
        CheckConstraint("action_type in ('reorder','expiry','retention')", name="ck_reco_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(String(36), index=True)

    run_id: Mapped[str] = mapped_column(String(36), index=True)   # groups one R_t
    cutoff_date: Mapped[str] = mapped_column(String(10), index=True)
    rank_in_rt: Mapped[int] = mapped_column(Integer, default=0)

    action_type: Mapped[str] = mapped_column(String(20), index=True)
    target_sku: Mapped[str | None] = mapped_column(String(160))
    target_customer_id: Mapped[str | None] = mapped_column(String(64))
    division: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[int | None] = mapped_column(Integer)

    # Utility decomposition (layer 7) kept as separate columns so the terms can
    # be compared against realised outcome without re-parsing JSON.
    benefit_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    action_cost_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    risk_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    utility_bdt: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))

    confidence: Mapped[str] = mapped_column(String(20), default="baseline")
    feasible: Mapped[bool] = mapped_column(Boolean, default=True)
    infeasible_reason: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    explanation_json: Mapped[str | None] = mapped_column(Text)  # layer 8, verbatim
    model_version: Mapped[str | None] = mapped_column(String(80))

    decisions: Mapped[list["RecommendationDecision"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan")
    outcomes: Mapped[list["RecommendationOutcome"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan")


class RecommendationDecision(Base, TimestampMixin):
    """Layer 9 -- the owner is the final authority, so the decision is recorded.

    `modify` carries the owner's own quantity in `modified_quantity`: when a
    pharmacist consistently overrides the suggested amount, that gap is itself
    a measurable finding about the model.
    """

    __tablename__ = "recommendation_decisions"
    __table_args__ = (
        CheckConstraint("decision in ('accept','reject','modify','defer')", name="ck_decision"),
        Index("ix_decision_org_time", "organization_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(36))

    decision: Mapped[str] = mapped_column(String(20), index=True)
    modified_quantity: Mapped[int | None] = mapped_column(Integer)
    defer_until: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(Text)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="decisions")


class RecommendationOutcome(Base, TimestampMixin):
    """Layer 10 -- what actually happened after the decision.

    Deliberately stores realised quantities alongside what was predicted, so
    forecast error and business effect are both measurable. Every field is
    nullable: an outcome that has not been observed yet must read as unknown,
    never as zero.
    """

    __tablename__ = "recommendation_outcomes"
    __table_args__ = (Index("ix_outcome_org_time", "organization_id", "observed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True)

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    observation_window_days: Mapped[int] = mapped_column(Integer, default=30)

    action_taken: Mapped[bool | None] = mapped_column(Boolean)
    stockout_days_before: Mapped[int | None] = mapped_column(Integer)
    stockout_days_after: Mapped[int | None] = mapped_column(Integer)
    holding_cost_before_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    holding_cost_after_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    expired_value_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    customer_responded: Mapped[bool | None] = mapped_column(Boolean)

    predicted_quantity: Mapped[int | None] = mapped_column(Integer)
    realised_quantity: Mapped[int | None] = mapped_column(Integer)
    realised_benefit_bdt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    drift_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    # "manual" (owner-entered) or "ledger_auto" (api/outcome_measurement.py) --
    # a reader must be able to tell which without trusting the numbers equally.
    measured_by: Mapped[str] = mapped_column(String(12), default="manual", server_default="manual")

    recommendation: Mapped["Recommendation"] = relationship(back_populates="outcomes")


class TeamMessage(Base, TimestampMixin):
    """One organization-wide staff chat channel -- everyone with an active
    Membership in the org can read and post. Intentionally a single shared
    channel, not DMs or per-branch rooms: a small shop's whole team already
    sits in one WhatsApp group, this mirrors that rather than adding rooms
    nobody will organize. ``branch_id`` is optional context on a message
    (e.g. "posted from Mirpur branch"), not a separate channel."""

    __tablename__ = "team_messages"
    __table_args__ = (Index("ix_team_messages_org_time", "organization_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)


class SiteContent(Base, TimestampMixin):
    """Generic key/value store for public-site copy a platform admin can edit
    without a redeploy. Not a full CMS -- a small, deliberately generic table
    so new editable fields (a new FAQ, a changed headline) are a new `key`,
    never a new migration. `frontend/src/pages/PublicSite.jsx` fetches this
    once at `GET /api/site-content` (public, no auth) and overlays it onto its
    own hardcoded defaults; a missing key just means "use the default copy",
    so this table can start empty without breaking the site."""

    __tablename__ = "site_content"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
