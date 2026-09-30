"""Bangladesh reference data

Revision ID: b31d9e85f603
Revises: a29c8d74e5f2
Create Date: 2026-09-30
"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

from api.bangladesh_reference import rows

revision: str = "b31d9e85f603"
down_revision: Union[str, None] = "a29c8d74e5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reference_values",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("parent_code", sa.String(50), nullable=True),
        sa.Column("label_en", sa.String(120), nullable=False),
        sa.Column("label_bn", sa.String(120), nullable=False),
        sa.Column("details", sa.String(240), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("verified_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "code"),
    )
    op.create_index("ix_reference_values_kind", "reference_values", ["kind"])
    op.create_index("ix_reference_values_parent_code", "reference_values", ["parent_code"])
    op.create_index("ix_reference_kind_parent", "reference_values", ["kind", "parent_code"])
    table = sa.table(
        "reference_values", sa.column("id", sa.String), sa.column("code", sa.String),
        sa.column("kind", sa.String), sa.column("parent_code", sa.String),
        sa.column("label_en", sa.String), sa.column("label_bn", sa.String),
        sa.column("details", sa.String), sa.column("source_url", sa.String),
        sa.column("verified_on", sa.Date), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(table, [{"id": str(uuid.uuid4()), "created_at": now, "updated_at": now, **row} for row in rows()])


def downgrade() -> None:
    op.drop_table("reference_values")
