"""Persistent customer address book, wishlist and per-store carts.

Revision ID: c5e7a1b2d3f4
Revises: b5f251025a01
Created: 2026-10-27

Additive migration. Existing customers, orders and store data are untouched.
"""
from __future__ import annotations

from alembic import op

revision = "c5e7a1b2d3f4"
down_revision = "b5f251025a01"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "store_customer_addresses",
    "store_customer_wishlist_items",
    "store_customer_cart_items",
)


def upgrade() -> None:
    from api.database import Base
    from api import domain_models  # noqa: F401
    from api import admin_models  # noqa: F401

    bind = op.get_bind()
    for name in NEW_TABLES:
        table = Base.metadata.tables.get(name)
        if table is None:
            raise RuntimeError("Expected customer commerce table missing: " + name)
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    raise RuntimeError(
        "Customer commerce data is non-destructive; restore a verified database "
        "snapshot instead of dropping saved addresses, carts or wishlists."
    )
