"""reservations (available-to-promise stock hold)

Revision ID: 5f1a8e3c7d2b
Revises: 4b8d1e6a3c9f
Create Date: 2026-10-01 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f1a8e3c7d2b'
down_revision: Union[str, None] = '4b8d1e6a3c9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reservations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=False),
        sa.Column('sales_document_id', sa.String(length=36), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='active'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['sales_document_id'], ['sales_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reservations_organization_id'), 'reservations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_reservations_branch_id'), 'reservations', ['branch_id'], unique=False)
    op.create_index(op.f('ix_reservations_product_id'), 'reservations', ['product_id'], unique=False)
    op.create_index(op.f('ix_reservations_sales_document_id'), 'reservations', ['sales_document_id'], unique=False)
    op.create_index(op.f('ix_reservations_status'), 'reservations', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reservations_status'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_sales_document_id'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_product_id'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_branch_id'), table_name='reservations')
    op.drop_index(op.f('ix_reservations_organization_id'), table_name='reservations')
    op.drop_table('reservations')
