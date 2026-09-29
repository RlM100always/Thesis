"""credit limit price tier wholesale

Revision ID: 94e975618b25
Revises: 97f321479bd6
Create Date: 2026-09-28 17:21:21.677774
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '94e975618b25'
down_revision: Union[str, None] = '97f321479bd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plain ADD COLUMN: safe on populated SQLite tables (no table rebuild) and on Postgres.
    op.add_column("customers", sa.Column("credit_limit", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column("customers", sa.Column("price_tier", sa.String(length=20), server_default="retail", nullable=False))
    op.add_column("products", sa.Column("wholesale_price", sa.Numeric(precision=14, scale=2), nullable=True))


def downgrade() -> None:
    raise NotImplementedError("Dropping columns needs a table rebuild on SQLite; restore from backup instead.")
