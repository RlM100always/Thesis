"""offline sync operation receipts

Revision ID: c42eaf960714
Revises: b31d9e85f603
Create Date: 2026-09-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c42eaf960714"
down_revision: Union[str, None] = "b31d9e85f603"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("operation_id", sa.String(100), nullable=False),
        sa.Column("operation_type", sa.String(30), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "operation_id"),
    )
    for column in ("organization_id", "operation_id", "operation_type", "entity_id"):
        op.create_index(f"ix_sync_operations_{column}", "sync_operations", [column])


def downgrade() -> None:
    op.drop_table("sync_operations")
