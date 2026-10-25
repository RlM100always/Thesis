"""Restored storefront/account/checkout schema on existing PostgreSQL installations.

Revision ID: b5f251025a01
Revises: d53fb071825, a1c2e4f9b7d3
Created: 2026-10-25

Data-preserving additive migration. Run only after snapshotting the database.
Do NOT confuse this with re-seeding operational stores or customers.
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "b5f251025a01"
down_revision = ("d53fb071825", "a1c2e4f9b7d3")
branch_labels = None
depends_on = None

NEW_TABLES = (
    "store_customers",
    "store_messages",
    "store_coupons",
    "product_variants",
    "product_reviews",
)
CHANGED_TABLES = (
    "stores",
    "store_products",
    "sales_documents",
    "sales_document_lines",
    "products",
)
DEFAULTS = {
    ("stores", "allow_zone_restriction"): "false",
    ("stores", "sslcz_is_live"): "false",
    ("stores", "bkash_is_live"): "false",
    ("stores", "nagad_is_live"): "false",
    ("sales_documents", "payment_status"): "'pending'",
    ("sales_documents", "delivery_fee"): "0",
    ("sales_documents", "coupon_discount"): "0",
}


def upgrade() -> None:
    bind = op.get_bind()
    from api.database import Base
    from api import domain_models  # noqa: F401
    from api import admin_models  # noqa: F401

    for name in NEW_TABLES:
        table = Base.metadata.tables.get(name)
        if table is None:
            raise RuntimeError("Expected storefront model table missing: " + name)
        table.create(bind, checkfirst=True)

    for name in CHANGED_TABLES:
        if not sa.inspect(bind).has_table(name):
            raise RuntimeError("Expected pre-existing operational table missing: " + name)
        actual = {row["name"] for row in sa.inspect(bind).get_columns(name)}
        for source in Base.metadata.tables[name].columns:
            if source.name in actual:
                continue
            foreign_keys = [
                sa.ForeignKey(fk.target_fullname)
                for fk in source.foreign_keys
            ]
            default = DEFAULTS.get((name, source.name))
            new_column = sa.Column(
                source.name,
                source.type,
                *foreign_keys,
                nullable=True,
                server_default=sa.text(default) if default else None,
            )
            op.add_column(name, new_column)
            actual.add(source.name)


def downgrade() -> None:
    raise RuntimeError(
        "The store recovery migration is intentionally non-destructive. "
        "Restore a verified pre-upgrade database snapshot instead of dropping "
        "customer/order data."
    )
