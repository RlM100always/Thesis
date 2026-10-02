"""audit_logs append-only at the database level

Revision ID: 4d7a2e9f1c6b
Revises: 2b8f6d1a9c3e
Create Date: 2026-10-01 03:00:00.000000

Until now ``AuditLog`` rows were append-only only by application convention
(no route ever updates or deletes one). SRD 15.1 wants that enforced where a
bug or a direct DB session cannot bypass it, so these triggers make SQLite
itself refuse UPDATE/DELETE on this table.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '4d7a2e9f1c6b'
down_revision: Union[str, None] = '2b8f6d1a9c3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        # Profile B (Postgres): the equivalent is a REVOKE UPDATE/DELETE grant
        # plus a BEFORE trigger using a PL/pgSQL function -- an operator task
        # for that deployment, not SQLite DDL blindly replayed against it.
        return
    op.execute("""
        CREATE TRIGGER trg_audit_logs_no_update
        BEFORE UPDATE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit_logs is append-only: rows cannot be updated');
        END;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_logs_no_delete
        BEFORE DELETE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit_logs is append-only: rows cannot be deleted');
        END;
    """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_no_delete;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_no_update;")
