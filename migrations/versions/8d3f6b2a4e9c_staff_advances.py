"""staff advances and repayments

Revision ID: 8d3f6b2a4e9c
Revises: 2e8c4a7f9b1d
Create Date: 2026-10-01 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8d3f6b2a4e9c'
down_revision: Union[str, None] = '2e8c4a7f9b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'staff_advances',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('reason', sa.String(length=300), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='outstanding'),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_staff_advances_organization_id'), 'staff_advances', ['organization_id'], unique=False)
    op.create_index(op.f('ix_staff_advances_user_id'), 'staff_advances', ['user_id'], unique=False)
    op.create_index(op.f('ix_staff_advances_status'), 'staff_advances', ['status'], unique=False)

    op.create_table(
        'staff_advance_repayments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('advance_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('amount > 0'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['advance_id'], ['staff_advances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_staff_advance_repayments_organization_id'), 'staff_advance_repayments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_staff_advance_repayments_advance_id'), 'staff_advance_repayments', ['advance_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_staff_advance_repayments_advance_id'), table_name='staff_advance_repayments')
    op.drop_index(op.f('ix_staff_advance_repayments_organization_id'), table_name='staff_advance_repayments')
    op.drop_table('staff_advance_repayments')
    op.drop_index(op.f('ix_staff_advances_status'), table_name='staff_advances')
    op.drop_index(op.f('ix_staff_advances_user_id'), table_name='staff_advances')
    op.drop_index(op.f('ix_staff_advances_organization_id'), table_name='staff_advances')
    op.drop_table('staff_advances')
