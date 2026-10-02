"""user profile: phone and inline avatar

Revision ID: a1b2c3d4e5f6
Revises: 5f1a8e3c7d2b
Create Date: 2026-10-01 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5f1a8e3c7d2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('avatar_data_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'avatar_data_url')
    op.drop_column('users', 'phone')
