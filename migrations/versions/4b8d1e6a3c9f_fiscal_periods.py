"""fiscal periods (accounting close/reopen)

Revision ID: 4b8d1e6a3c9f
Revises: 9c5e2a8d4f1b
Create Date: 2026-10-01 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4b8d1e6a3c9f'
down_revision: Union[str, None] = '9c5e2a8d4f1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fiscal_periods',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('period_month', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='closed'),
        sa.Column('closed_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reopened_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reopen_reason', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reopened_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'period_month'),
    )
    op.create_index(op.f('ix_fiscal_periods_organization_id'), 'fiscal_periods', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fiscal_periods_organization_id'), table_name='fiscal_periods')
    op.drop_table('fiscal_periods')
