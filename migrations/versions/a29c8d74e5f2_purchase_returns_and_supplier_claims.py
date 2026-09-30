"""purchase returns and supplier claims

Revision ID: a29c8d74e5f2
Revises: f18a7b42d901
Create Date: 2026-09-29
"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "a29c8d74e5f2"
down_revision: Union[str, None] = "f18a7b42d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), nullable=False),
        sa.Column("supplier_id", sa.String(36), nullable=False),
        sa.Column("return_number", sa.String(80), nullable=False),
        sa.Column("claim_type", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credit_note_number", sa.String(100), nullable=True),
        sa.Column("supplier_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total >= 0"),
        sa.CheckConstraint("status in ('submitted','dispatched','settled','rejected')", name="ck_purchase_return_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.UniqueConstraint("organization_id", "return_number"),
        sa.UniqueConstraint("organization_id", "supplier_id", "credit_note_number"),
    )
    op.create_index("ix_purchase_return_org_time", "purchase_returns", ["organization_id", "submitted_at"])
    for column in ("organization_id", "branch_id", "purchase_order_id", "supplier_id", "status", "submitted_at"):
        op.create_index(f"ix_purchase_returns_{column}", "purchase_returns", [column])

    op.create_table(
        "purchase_return_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("purchase_return_id", sa.String(36), nullable=False),
        sa.Column("purchase_order_item_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0 AND unit_cost >= 0 AND amount >= 0"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_return_id"], ["purchase_returns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_order_item_id"], ["purchase_order_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
    )
    for column in ("organization_id", "purchase_return_id", "purchase_order_item_id", "product_id", "batch_id"):
        op.create_index(f"ix_purchase_return_items_{column}", "purchase_return_items", [column])

    # Existing organizations need the same system account that newly created
    # organizations receive from seed_default_accounts().
    connection = op.get_bind()
    account = sa.table(
        "accounts",
        sa.column("id", sa.String), sa.column("organization_id", sa.String),
        sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("type", sa.String), sa.column("is_system", sa.Boolean),
        sa.column("active", sa.Boolean), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    organizations = sa.table("organizations", sa.column("id", sa.String))
    existing = set(connection.execute(sa.select(account.c.organization_id).where(account.c.code == "1250")).scalars())
    now = datetime.now(timezone.utc)
    rows = [{
        "id": str(uuid.uuid4()), "organization_id": org_id, "code": "1250",
        "name": "Supplier Claims", "type": "asset", "is_system": True,
        "active": True, "created_at": now, "updated_at": now,
    } for org_id in connection.execute(sa.select(organizations.c.id)).scalars() if org_id not in existing]
    if rows:
        op.bulk_insert(account, rows)


def downgrade() -> None:
    op.drop_table("purchase_return_items")
    op.drop_table("purchase_returns")
    op.execute("DELETE FROM accounts WHERE code = '1250' AND is_system = 1")
