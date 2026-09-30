"""outbound message outbox

Revision ID: d53fb071825
Revises: c42eaf960714
Create Date: 2026-09-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d53fb071825"
down_revision: Union[str, None] = "c42eaf960714"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("outbound_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(40), nullable=False),
        sa.Column("template", sa.String(80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider_message_id", sa.String(160), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("requested_by_user_id", sa.String(36), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "idempotency_key"))
    for col in ("organization_id", "channel", "idempotency_key", "status"):
        op.create_index(f"ix_outbound_messages_{col}", "outbound_messages", [col])

def downgrade() -> None:
    op.drop_table("outbound_messages")
