"""organization operational settings

Revision ID: e6bd512f667a
Revises: d070d4b898b9
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e6bd512f667a"
down_revision: Union[str, None] = "d070d4b898b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("business_mode", sa.String(length=20), nullable=False),
        sa.Column("payment_methods_json", sa.Text(), nullable=False),
        sa.Column("sales_channels_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("organization_settings")
