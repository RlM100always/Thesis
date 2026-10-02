"""warehouses and membership branch scoping

Revision ID: 7a1d9e2c4f5b
Revises: 9c3e4f6a1b2d
Create Date: 2026-10-01 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1d9e2c4f5b'
down_revision: Union[str, None] = '9c3e4f6a1b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'warehouses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('branch_id', 'code'),
    )
    op.create_index(op.f('ix_warehouses_organization_id'), 'warehouses', ['organization_id'], unique=False)
    op.create_index(op.f('ix_warehouses_branch_id'), 'warehouses', ['branch_id'], unique=False)

    op.create_table(
        'membership_branches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('membership_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('membership_id', 'branch_id'),
    )
    op.create_index(op.f('ix_membership_branches_membership_id'), 'membership_branches', ['membership_id'], unique=False)
    op.create_index(op.f('ix_membership_branches_branch_id'), 'membership_branches', ['branch_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_membership_branches_branch_id'), table_name='membership_branches')
    op.drop_index(op.f('ix_membership_branches_membership_id'), table_name='membership_branches')
    op.drop_table('membership_branches')
    op.drop_index(op.f('ix_warehouses_branch_id'), table_name='warehouses')
    op.drop_index(op.f('ix_warehouses_organization_id'), table_name='warehouses')
    op.drop_table('warehouses')
