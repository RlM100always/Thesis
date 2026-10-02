"""payroll runs and lines, membership base_salary

Revision ID: 9c5e2a8d4f1b
Revises: 8d3f6b2a4e9c
Create Date: 2026-10-01 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c5e2a8d4f1b'
down_revision: Union[str, None] = '8d3f6b2a4e9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('memberships', sa.Column('base_salary', sa.Numeric(precision=14, scale=2), nullable=True))

    op.create_table(
        'payroll_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('approved_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'period_start', 'period_end'),
    )
    op.create_index(op.f('ix_payroll_runs_organization_id'), 'payroll_runs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_payroll_runs_status'), 'payroll_runs', ['status'], unique=False)

    op.create_table(
        'payroll_lines',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('payroll_run_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('base_salary', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('commission_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('advance_deduction', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('net_pay', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payroll_run_id'], ['payroll_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payroll_run_id', 'user_id'),
    )
    op.create_index(op.f('ix_payroll_lines_organization_id'), 'payroll_lines', ['organization_id'], unique=False)
    op.create_index(op.f('ix_payroll_lines_payroll_run_id'), 'payroll_lines', ['payroll_run_id'], unique=False)
    op.create_index(op.f('ix_payroll_lines_user_id'), 'payroll_lines', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payroll_lines_user_id'), table_name='payroll_lines')
    op.drop_index(op.f('ix_payroll_lines_payroll_run_id'), table_name='payroll_lines')
    op.drop_index(op.f('ix_payroll_lines_organization_id'), table_name='payroll_lines')
    op.drop_table('payroll_lines')
    op.drop_index(op.f('ix_payroll_runs_status'), table_name='payroll_runs')
    op.drop_index(op.f('ix_payroll_runs_organization_id'), table_name='payroll_runs')
    op.drop_table('payroll_runs')
    op.drop_column('memberships', 'base_salary')
