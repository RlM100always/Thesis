"""commission rules and entries

Revision ID: 1f6b3d8a2c5e
Revises: 4c8e1a6d9f3b
Create Date: 2026-10-01 11:00:00.000000
"""
from typing import Sequence, Union

import uuid

from alembic import op
import sqlalchemy as sa


revision: str = '1f6b3d8a2c5e'
down_revision: Union[str, None] = '4c8e1a6d9f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'commission_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('rate_percent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index(op.f('ix_commission_rules_organization_id'), 'commission_rules', ['organization_id'], unique=False)

    op.create_table(
        'commission_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('sales_order_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('reason', sa.String(length=20), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('amount <> 0'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_commission_entries_organization_id'), 'commission_entries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_commission_entries_user_id'), 'commission_entries', ['user_id'], unique=False)
    op.create_index(op.f('ix_commission_entries_sales_order_id'), 'commission_entries', ['sales_order_id'], unique=False)
    op.create_index(op.f('ix_commission_entries_occurred_at'), 'commission_entries', ['occurred_at'], unique=False)

    # Backfill: every organization that existed before this feature gets an
    # inactive default rule, the same bootstrap `seed_default_rule` gives a
    # brand-new one -- so "rule not found" is never a state a real org is in.
    connection = op.get_bind()
    org_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM organizations")).fetchall()]
    for org_id in org_ids:
        existing = connection.execute(
            sa.text("SELECT 1 FROM commission_rules WHERE organization_id = :org_id"), {"org_id": org_id},
        ).fetchone()
        if existing:
            continue
        connection.execute(sa.text(
            "INSERT INTO commission_rules (id, organization_id, rate_percent, active, created_at, updated_at) "
            "VALUES (:id, :org_id, :rate, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"id": str(uuid.uuid4()), "org_id": org_id, "rate": "2.00"})


def downgrade() -> None:
    op.drop_index(op.f('ix_commission_entries_occurred_at'), table_name='commission_entries')
    op.drop_index(op.f('ix_commission_entries_sales_order_id'), table_name='commission_entries')
    op.drop_index(op.f('ix_commission_entries_user_id'), table_name='commission_entries')
    op.drop_index(op.f('ix_commission_entries_organization_id'), table_name='commission_entries')
    op.drop_table('commission_entries')
    op.drop_index(op.f('ix_commission_rules_organization_id'), table_name='commission_rules')
    op.drop_table('commission_rules')
