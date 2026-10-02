"""sales targets

Revision ID: 6a3e9f5c1d7b
Revises: 1f6b3d8a2c5e
Create Date: 2026-10-01 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6a3e9f5c1d7b'
down_revision: Union[str, None] = '1f6b3d8a2c5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sales_targets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('target_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('period_end >= period_start'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', 'period_start'),
    )
    op.create_index(op.f('ix_sales_targets_organization_id'), 'sales_targets', ['organization_id'], unique=False)
    op.create_index(op.f('ix_sales_targets_user_id'), 'sales_targets', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sales_targets_user_id'), table_name='sales_targets')
    op.drop_index(op.f('ix_sales_targets_organization_id'), table_name='sales_targets')
    op.drop_table('sales_targets')
