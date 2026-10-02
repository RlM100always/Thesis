"""customer feedback / NPS entries

Revision ID: 3a9d7c2e5f1b
Revises: 8f1c5a3e7b9d
Create Date: 2026-10-01 06:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a9d7c2e5f1b'
down_revision: Union[str, None] = '8f1c5a3e7b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feedback_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=True),
        sa.Column('sales_order_id', sa.String(length=36), nullable=True),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('follow_up_ticket_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('score >= 0 AND score <= 10'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id']),
        sa.ForeignKeyConstraint(['follow_up_ticket_id'], ['support_tickets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feedback_entries_organization_id'), 'feedback_entries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_feedback_entries_customer_id'), 'feedback_entries', ['customer_id'], unique=False)
    op.create_index(op.f('ix_feedback_entries_sales_order_id'), 'feedback_entries', ['sales_order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_feedback_entries_sales_order_id'), table_name='feedback_entries')
    op.drop_index(op.f('ix_feedback_entries_customer_id'), table_name='feedback_entries')
    op.drop_index(op.f('ix_feedback_entries_organization_id'), table_name='feedback_entries')
    op.drop_table('feedback_entries')
