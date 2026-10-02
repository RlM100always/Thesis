"""attendance records (check-in/out)

Revision ID: 9e4f7b2a8d1c
Revises: 5b2e8f4a1c6d
Create Date: 2026-10-01 08:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9e4f7b2a8d1c'
down_revision: Union[str, None] = '5b2e8f4a1c6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'attendance_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('check_in_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('check_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='device'),
        sa.Column('corrects_record_id', sa.String(length=36), nullable=True),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['corrects_record_id'], ['attendance_records.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_attendance_records_organization_id'), 'attendance_records', ['organization_id'], unique=False)
    op.create_index(op.f('ix_attendance_records_branch_id'), 'attendance_records', ['branch_id'], unique=False)
    op.create_index(op.f('ix_attendance_records_user_id'), 'attendance_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_attendance_records_check_in_at'), 'attendance_records', ['check_in_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attendance_records_check_in_at'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_user_id'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_branch_id'), table_name='attendance_records')
    op.drop_index(op.f('ix_attendance_records_organization_id'), table_name='attendance_records')
    op.drop_table('attendance_records')
