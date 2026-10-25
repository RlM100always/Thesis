"""SQLAlchemy engine and request-scoped database sessions."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_schema() -> None:
    # Import registers every mapped class with Base.metadata.
    from . import domain_models  # noqa: F401
    from . import admin_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _sqlite_migrations()


def _sqlite_migrations() -> None:
    """Add columns that were introduced after the initial create_all."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        _add_col_if_missing(conn, "sales_documents", "store_customer_id", "TEXT")
        _add_col_if_missing(conn, "stores", "delivery_inside_dhaka", "NUMERIC")
        _add_col_if_missing(conn, "stores", "delivery_outside_dhaka", "NUMERIC")
        _add_col_if_missing(conn, "stores", "delivery_free_above", "NUMERIC")
        _add_col_if_missing(conn, "stores", "allow_zone_restriction", "BOOLEAN DEFAULT 0")
        _add_col_if_missing(conn, "stores", "allowed_divisions", "TEXT")
        _add_col_if_missing(conn, "stores", "sslcz_store_id", "TEXT")
        _add_col_if_missing(conn, "stores", "sslcz_store_passwd", "TEXT")
        _add_col_if_missing(conn, "stores", "sslcz_is_live", "BOOLEAN DEFAULT 0")
        _add_col_if_missing(conn, "stores", "bkash_app_key", "TEXT")
        _add_col_if_missing(conn, "stores", "bkash_app_secret", "TEXT")
        _add_col_if_missing(conn, "stores", "bkash_username", "TEXT")
        _add_col_if_missing(conn, "stores", "bkash_password", "TEXT")
        _add_col_if_missing(conn, "stores", "bkash_is_live", "BOOLEAN DEFAULT 0")
        _add_col_if_missing(conn, "stores", "nagad_merchant_id", "TEXT")
        _add_col_if_missing(conn, "stores", "nagad_merchant_number", "TEXT")
        _add_col_if_missing(conn, "stores", "nagad_pub_key", "TEXT")
        _add_col_if_missing(conn, "stores", "nagad_priv_key", "TEXT")
        _add_col_if_missing(conn, "stores", "nagad_is_live", "BOOLEAN DEFAULT 0")
        _add_col_if_missing(conn, "sales_documents", "delivery_fee", "NUMERIC DEFAULT 0")
        _add_col_if_missing(conn, "sales_documents", "payment_status", "TEXT DEFAULT 'pending'")
        _add_col_if_missing(conn, "sales_documents", "payment_screenshot_url", "TEXT")
        _add_col_if_missing(conn, "sales_documents", "status_note", "TEXT")
        # Coupon / discount tracking on orders
        _add_col_if_missing(conn, "sales_documents", "coupon_code", "TEXT")
        _add_col_if_missing(conn, "sales_documents", "coupon_discount", "NUMERIC DEFAULT 0")
        # Flash sale fields on store products
        _add_col_if_missing(conn, "store_products", "sale_price", "NUMERIC")
        _add_col_if_missing(conn, "store_products", "sale_start", "TEXT")
        _add_col_if_missing(conn, "store_products", "sale_end", "TEXT")
        # Low-stock alert threshold on products
        _add_col_if_missing(conn, "products", "stock_alert_threshold", "INTEGER")
        # Referral on store customers
        _add_col_if_missing(conn, "store_customers", "referral_code", "TEXT")
        _add_col_if_missing(conn, "store_customers", "referred_by", "TEXT")
        # Variant selection stored per order line
        _add_col_if_missing(conn, "sales_document_lines", "variant_label", "TEXT")

def _add_col_if_missing(conn, table: str, column: str, col_type: str) -> None:
    from sqlalchemy import text
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    cols = {row[1] for row in result}
    if column not in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        conn.commit()
