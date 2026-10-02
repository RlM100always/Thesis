"""online order checkout fields on sales_documents

Revision ID: a1c2e4f9b7d3
Revises: c3d4e5f6a7b8
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1c2e4f9b7d3"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales_documents", sa.Column("shipping_name", sa.String(160), nullable=True))
    op.add_column("sales_documents", sa.Column("shipping_phone", sa.String(32), nullable=True))
    op.add_column("sales_documents", sa.Column("shipping_address", sa.Text(), nullable=True))
    op.add_column("sales_documents", sa.Column("access_token", sa.String(64), nullable=True))
    # A unique index enforces the same constraint as a named UNIQUE constraint
    # on SQLite, without needing batch mode's copy-and-move table rebuild.
    op.create_index("ix_sales_documents_access_token", "sales_documents", ["access_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_sales_documents_access_token", table_name="sales_documents")
    op.drop_column("sales_documents", "access_token")
    op.drop_column("sales_documents", "shipping_address")
    op.drop_column("sales_documents", "shipping_phone")
    op.drop_column("sales_documents", "shipping_name")
