"""Core multi-tenant operational schema for Bangladeshi retail SMEs.

All business-owned records carry ``organization_id``. Inventory is an
append-only movement ledger; balances are derived rather than overwritten.
Amounts use Decimal-backed NUMERIC columns and timestamps are stored in UTC.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint,
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
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="cashier")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


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


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    typical_lead_days: Mapped[int] = mapped_column(Integer, default=0)


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
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
