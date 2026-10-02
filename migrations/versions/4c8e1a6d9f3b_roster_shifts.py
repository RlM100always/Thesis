"""roster shifts

Revision ID: 4c8e1a6d9f3b
Revises: 7d2a9c5e3f8b
Create Date: 2026-10-01 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c8e1a6d9f3b'
down_revision: Union[str, None] = '7d2a9c5e3f8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'roster_shifts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.String(length=5), nullable=False),
        sa.Column('end_time', sa.String(length=5), nullable=False),
        sa.Column('station', sa.String(length=60), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('end_time > start_time'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_roster_shifts_organization_id'), 'roster_shifts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_roster_shifts_branch_id'), 'roster_shifts', ['branch_id'], unique=False)
    op.create_index(op.f('ix_roster_shifts_user_id'), 'roster_shifts', ['user_id'], unique=False)
    op.create_index(op.f('ix_roster_shifts_shift_date'), 'roster_shifts', ['shift_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_roster_shifts_shift_date'), table_name='roster_shifts')
    op.drop_index(op.f('ix_roster_shifts_user_id'), table_name='roster_shifts')
    op.drop_index(op.f('ix_roster_shifts_branch_id'), table_name='roster_shifts')
    op.drop_index(op.f('ix_roster_shifts_organization_id'), table_name='roster_shifts')
    op.drop_table('roster_shifts')
