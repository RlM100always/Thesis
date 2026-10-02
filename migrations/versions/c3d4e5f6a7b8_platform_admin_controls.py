"""platform admin controls: org suspend/feature-flags, site content

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-01 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('organizations', sa.Column('suspended_reason', sa.String(length=300), nullable=True))
    op.add_column('organizations', sa.Column('feature_flags_json', sa.Text(), nullable=True))

    op.create_table(
        'site_content',
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('value_json', sa.Text(), nullable=False),
        sa.Column('updated_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('site_content')
    op.drop_column('organizations', 'feature_flags_json')
    op.drop_column('organizations', 'suspended_reason')
    op.drop_column('organizations', 'suspended_at')
