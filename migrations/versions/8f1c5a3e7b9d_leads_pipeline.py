"""leads and lead activities (CRM pipeline)

Revision ID: 8f1c5a3e7b9d
Revises: 6e3b8a4d2f7c
Create Date: 2026-10-01 05:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8f1c5a3e7b9d'
down_revision: Union[str, None] = '6e3b8a4d2f7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('phone_hash', sa.String(length=128), nullable=True),
        sa.Column('source', sa.String(length=60), nullable=True),
        sa.Column('stage', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('estimated_value', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('owner_user_id', sa.String(length=36), nullable=True),
        sa.Column('lost_reason', sa.String(length=200), nullable=True),
        sa.Column('converted_customer_id', sa.String(length=36), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['converted_customer_id'], ['customers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_leads_organization_id'), 'leads', ['organization_id'], unique=False)
    op.create_index(op.f('ix_leads_phone_hash'), 'leads', ['phone_hash'], unique=False)
    op.create_index(op.f('ix_leads_stage'), 'leads', ['stage'], unique=False)
    op.create_index(op.f('ix_leads_owner_user_id'), 'leads', ['owner_user_id'], unique=False)

    op.create_table(
        'lead_activities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('author_user_id', sa.String(length=36), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_lead_activities_lead_id'), 'lead_activities', ['lead_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lead_activities_lead_id'), table_name='lead_activities')
    op.drop_table('lead_activities')
    op.drop_index(op.f('ix_leads_owner_user_id'), table_name='leads')
    op.drop_index(op.f('ix_leads_stage'), table_name='leads')
    op.drop_index(op.f('ix_leads_phone_hash'), table_name='leads')
    op.drop_index(op.f('ix_leads_organization_id'), table_name='leads')
    op.drop_table('leads')
