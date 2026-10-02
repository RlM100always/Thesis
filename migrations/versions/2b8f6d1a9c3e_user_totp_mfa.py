"""user TOTP MFA fields

Revision ID: 2b8f6d1a9c3e
Revises: 7a1d9e2c4f5b
Create Date: 2026-10-01 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2b8f6d1a9c3e'
down_revision: Union[str, None] = '7a1d9e2c4f5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('mfa_totp_secret', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('mfa_recovery_codes_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'mfa_recovery_codes_json')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_totp_secret')
