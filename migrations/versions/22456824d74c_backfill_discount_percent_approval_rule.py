"""backfill discount percent approval rule

Revision ID: 22456824d74c
Revises: c2dbdeb880b7
Create Date: 2026-09-29 09:36:36.291111
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '22456824d74c'
down_revision: Union[str, None] = 'c2dbdeb880b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only: adds the discount_percent approval rule for every organization
    # created before this revision that does not already have one. New
    # organizations get it at creation via api.approvals.seed_default_rules.
    import uuid
    from datetime import datetime, timezone

    connection = op.get_bind()
    has_rule = {row[0] for row in connection.execute(
        sa.text("SELECT organization_id FROM approval_rules WHERE kind = 'discount_percent'"))}
    org_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM organizations"))]
    now = datetime.now(timezone.utc)
    rules_table = sa.table(
        "approval_rules", sa.column("id", sa.String), sa.column("organization_id", sa.String),
        sa.column("kind", sa.String), sa.column("threshold", sa.Numeric), sa.column("approver_role", sa.String),
        sa.column("active", sa.Boolean), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    rows = [
        {
            "id": str(uuid.uuid4()), "organization_id": org_id, "kind": "discount_percent",
            "threshold": 10, "approver_role": "manager", "active": True, "created_at": now, "updated_at": now,
        }
        for org_id in org_ids if org_id not in has_rule
    ]
    if rows:
        connection.execute(rules_table.insert(), rows)


def downgrade() -> None:
    op.execute("DELETE FROM approval_rules WHERE kind = 'discount_percent'")
