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


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
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

    recommendation: Mapped["Recommendation"] = relationship(back_populates="outcomes")
