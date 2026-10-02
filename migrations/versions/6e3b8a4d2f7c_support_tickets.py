"""support tickets and ticket messages

Revision ID: 6e3b8a4d2f7c
Revises: 4d7a2e9f1c6b
Create Date: 2026-10-01 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6e3b8a4d2f7c'
down_revision: Union[str, None] = '4d7a2e9f1c6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('customer_id', sa.String(length=36), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False, server_default='general'),
        sa.Column('priority', sa.String(length=10), nullable=False, server_default='normal'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_to_user_id', sa.String(length=36), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_support_tickets_organization_id'), 'support_tickets', ['organization_id'], unique=False)
    op.create_index(op.f('ix_support_tickets_branch_id'), 'support_tickets', ['branch_id'], unique=False)
    op.create_index(op.f('ix_support_tickets_customer_id'), 'support_tickets', ['customer_id'], unique=False)
    op.create_index(op.f('ix_support_tickets_status'), 'support_tickets', ['status'], unique=False)
    op.create_index(op.f('ix_support_tickets_assigned_to_user_id'), 'support_tickets', ['assigned_to_user_id'], unique=False)

    op.create_table(
        'ticket_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('author_user_id', sa.String(length=36), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('internal', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ticket_messages_ticket_id'), 'ticket_messages', ['ticket_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ticket_messages_ticket_id'), table_name='ticket_messages')
    op.drop_table('ticket_messages')
    op.drop_index(op.f('ix_support_tickets_assigned_to_user_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_status'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_customer_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_branch_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_organization_id'), table_name='support_tickets')
    op.drop_table('support_tickets')
