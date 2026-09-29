"""backfill purchase amount approval rule

Revision ID: c6ec9372b08e
Revises: 4a2cf9d883e4
Create Date: 2026-09-29 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c6ec9372b08e'
down_revision: Union[str, None] = '4a2cf9d883e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only: adds the purchase_amount approval rule for every organization
    # created before this revision that does not already have one. New
    # organizations get it at creation via api.approvals.seed_default_rules.
    import uuid
    from datetime import datetime, timezone

    connection = op.get_bind()
    has_rule = {row[0] for row in connection.execute(
        sa.text("SELECT organization_id FROM approval_rules WHERE kind = 'purchase_amount'"))}
    org_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM organizations"))]
    now = datetime.now(timezone.utc)
    rules_table = sa.table(
        "approval_rules", sa.column("id", sa.String), sa.column("organization_id", sa.String),
        sa.column("kind", sa.String), sa.column("threshold", sa.Numeric), sa.column("approver_role", sa.String),
        sa.column("active", sa.Boolean), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    rows = [
        {
            "id": str(uuid.uuid4()), "organization_id": org_id, "kind": "purchase_amount",
            "threshold": 20000, "approver_role": "owner", "active": True, "created_at": now, "updated_at": now,
        }
        for org_id in org_ids if org_id not in has_rule
    ]
    if rows:
        connection.execute(rules_table.insert(), rows)


def downgrade() -> None:
    op.execute("DELETE FROM approval_rules WHERE kind = 'purchase_amount'")
