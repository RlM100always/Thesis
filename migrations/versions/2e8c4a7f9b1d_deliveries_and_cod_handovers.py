"""deliveries and COD handovers

Revision ID: 2e8c4a7f9b1d
Revises: 6a3e9f5c1d7b
Create Date: 2026-10-01 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2e8c4a7f9b1d'
down_revision: Union[str, None] = '6a3e9f5c1d7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deliveries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('sales_order_id', sa.String(length=36), nullable=False),
        sa.Column('rider_user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='assigned'),
        sa.Column('cod_amount_expected', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('cod_amount_collected', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('proof_note', sa.String(length=300), nullable=True),
        sa.Column('failure_reason', sa.String(length=300), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id']),
        sa.ForeignKeyConstraint(['rider_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deliveries_organization_id'), 'deliveries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_deliveries_branch_id'), 'deliveries', ['branch_id'], unique=False)
    op.create_index(op.f('ix_deliveries_sales_order_id'), 'deliveries', ['sales_order_id'], unique=False)
    op.create_index(op.f('ix_deliveries_rider_user_id'), 'deliveries', ['rider_user_id'], unique=False)
    op.create_index(op.f('ix_deliveries_status'), 'deliveries', ['status'], unique=False)

    op.create_table(
        'cod_handovers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('delivery_id', sa.String(length=36), nullable=False),
        sa.Column('shift_id', sa.String(length=36), nullable=False),
        sa.Column('handed_over_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('shortage_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('received_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['delivery_id'], ['deliveries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shift_id'], ['cashier_shifts.id']),
        sa.ForeignKeyConstraint(['received_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('delivery_id'),
    )
    op.create_index(op.f('ix_cod_handovers_organization_id'), 'cod_handovers', ['organization_id'], unique=False)
    op.create_index(op.f('ix_cod_handovers_delivery_id'), 'cod_handovers', ['delivery_id'], unique=False)
    op.create_index(op.f('ix_cod_handovers_shift_id'), 'cod_handovers', ['shift_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cod_handovers_shift_id'), table_name='cod_handovers')
    op.drop_index(op.f('ix_cod_handovers_delivery_id'), table_name='cod_handovers')
    op.drop_index(op.f('ix_cod_handovers_organization_id'), table_name='cod_handovers')
    op.drop_table('cod_handovers')
    op.drop_index(op.f('ix_deliveries_status'), table_name='deliveries')
    op.drop_index(op.f('ix_deliveries_rider_user_id'), table_name='deliveries')
    op.drop_index(op.f('ix_deliveries_sales_order_id'), table_name='deliveries')
    op.drop_index(op.f('ix_deliveries_branch_id'), table_name='deliveries')
    op.drop_index(op.f('ix_deliveries_organization_id'), table_name='deliveries')
    op.drop_table('deliveries')
