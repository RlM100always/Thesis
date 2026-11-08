from pathlib import Path
import sqlite3


def _migrated_db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(Path("cloudflare/migrations").glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    return connection


def test_all_d1_migrations_apply_in_order_and_create_commerce_tables():
    db = _migrated_db()
    tables = {
        row["name"] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "commerce_customer_accounts",
        "commerce_customer_sessions",
        "commerce_customer_addresses",
        "commerce_customer_wishlist_items",
        "commerce_customer_cart_items",
        "commerce_product_reviews",
        "commerce_order_returns",
        "commerce_customer_messages",
        "commerce_platform_admin_audit",
        "commerce_inventory_movements",
    } <= tables
    product_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(commerce_products)")
    }
    assert {"description", "brand", "tags", "compare_at_price_bdt", "unit_label", "updated_at"} <= product_columns
    order_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(commerce_orders)")
    }
    assert {"account_id", "cancellation_reason", "status_note", "payment_status", "payment_received_at", "payment_received_by", "payment_note"} <= order_columns
    merchant_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(merchant_accounts)")
    }
    assert {
        "email_verified_at", "email_verification_token_hash",
        "email_verification_expires_at", "password_reset_token_hash",
        "password_reset_expires_at",
    } <= merchant_columns
    assert {"is_active", "role", "display_name", "email_verification_method"} <= merchant_columns
    owner_staff_tables = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "merchant_owner_invites",
        "merchant_staff_store_access",
        "merchant_staff_invites",
        "commerce_merchant_audit",
    } <= owner_staff_tables
    assert {
        "idx_owner_invites_pending_email",
        "idx_staff_invites_pending_email",
        "idx_merchant_staff_store_role",
        "idx_merchant_audit_store_time",
    } <= {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    staff_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(merchant_staff_store_access)")
    }
    assert {"account_id", "owner_id", "store_id", "role", "is_active", "last_login_at"} <= staff_columns
    product_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(commerce_products)")
    }
    assert "reorder_level" in product_columns
    assistant_tables = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "commerce_ai_rate_limits" in assistant_tables

    customer_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(commerce_customer_accounts)")
    }
    assert {"password_reset_token_hash", "password_reset_expires_at"} <= customer_columns
    customer_auth_tables = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "commerce_customer_auth_limits" in customer_auth_tables
    customer_auth_indexes = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "idx_customer_password_reset_token" in customer_auth_indexes
    order_columns = {row["name"] for row in db.execute("PRAGMA table_info(commerce_orders)")}
    assert {"coupon_code", "coupon_discount_bdt"} <= order_columns
    coupon_tables = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"commerce_coupons", "commerce_coupon_redemptions"} <= coupon_tables
    coupon_triggers = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    }
    assert {"commerce_coupon_total_limit", "commerce_coupon_customer_limit"} <= coupon_triggers
    db.close()


def test_coupon_redemption_triggers_enforce_total_and_per_customer_limits():
    db = _migrated_db()
    db.execute(
        "INSERT INTO commerce_stores(id,slug,name,is_demo,is_active) VALUES(?,?,?,?,?)",
        ("merchant-coupon", "coupon-shop", "Coupon Shop", 0, 1),
    )
    db.execute(
        "INSERT INTO commerce_coupons(id,store_id,code,discount_type,discount_value,usage_limit,per_customer_limit) VALUES(?,?,?,?,?,?,?)",
        ("coupon-total", "merchant-coupon", "ONCE", "percent", 10, 1, 1),
    )
    for index in (1, 2, 3, 4):
        db.execute(
            "INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method) VALUES(?,?,?,?,?,?,?,?)",
            (f"coupon-order-{index}", "merchant-coupon", f"ORD-COUPON-{index}", f"token-{index}", "placed", 1000, 900, "cod"),
        )
    db.execute(
        "INSERT INTO commerce_coupon_redemptions(id,coupon_id,store_id,order_id,customer_key_hash,discount_bdt) VALUES(?,?,?,?,?,?)",
        ("redemption-1", "coupon-total", "merchant-coupon", "coupon-order-1", "customer-a", 100),
    )
    try:
        db.execute(
            "INSERT INTO commerce_coupon_redemptions(id,coupon_id,store_id,order_id,customer_key_hash,discount_bdt) VALUES(?,?,?,?,?,?)",
            ("redemption-2", "coupon-total", "merchant-coupon", "coupon-order-2", "customer-b", 100),
        )
        assert False, "total usage trigger should reject the second redemption"
    except sqlite3.IntegrityError as exc:
        assert "COUPON_USAGE_LIMIT" in str(exc)

    db.execute(
        "INSERT INTO commerce_coupons(id,store_id,code,discount_type,discount_value,usage_limit,per_customer_limit) VALUES(?,?,?,?,?,?,?)",
        ("coupon-customer", "merchant-coupon", "ONEPER", "fixed", 100, 10, 1),
    )
    db.execute(
        "INSERT INTO commerce_coupon_redemptions(id,coupon_id,store_id,order_id,customer_key_hash,discount_bdt) VALUES(?,?,?,?,?,?)",
        ("redemption-3", "coupon-customer", "merchant-coupon", "coupon-order-3", "customer-a", 100),
    )
    try:
        db.execute(
            "INSERT INTO commerce_coupon_redemptions(id,coupon_id,store_id,order_id,customer_key_hash,discount_bdt) VALUES(?,?,?,?,?,?)",
            ("redemption-4", "coupon-customer", "merchant-coupon", "coupon-order-4", "customer-a", 100),
        )
        assert False, "per-customer usage trigger should reject the second redemption"
    except sqlite3.IntegrityError as exc:
        assert "COUPON_CUSTOMER_LIMIT" in str(exc)
    db.close()


def test_cancel_and_received_return_restore_stock_once():
    db = _migrated_db()
    db.execute(
        "INSERT INTO commerce_stores(id,slug,name,is_demo,is_active) VALUES(?,?,?,?,?)",
        ("merchant-test", "test-shop", "Test Shop", 1, 1),
    )
    db.execute(
        "INSERT INTO commerce_products(id,store_id,sku,name,price_bdt,stock_qty,is_listed) VALUES(?,?,?,?,?,?,?)",
        ("product-1", "merchant-test", "SKU-1", "Test item", 100, 10, 1),
    )
    db.execute(
        "INSERT INTO commerce_customer_accounts(id,display_name,email,phone,password_salt,password_hash) VALUES(?,?,?,?,?,?)",
        ("customer-1", "Test Buyer", "buyer@example.invalid", "01700000000", "salt", "hash"),
    )
    db.execute(
        "INSERT INTO commerce_customers(id,store_id,display_name) VALUES(?,?,?)",
        ("legacy-customer-1", "merchant-test", "Test Buyer"),
    )
    db.execute(
        "INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,customer_id,account_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("order-cancel", "merchant-test", "ORD-CANCEL", "cancel-token", "placed", 200, 200, "demo", "legacy-customer-1", "customer-1"),
    )
    db.execute(
        "INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)",
        ("order-cancel", "product-1", "Test item", 2, 100, 200),
    )
    assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='product-1'").fetchone()[0] == 8
    assert db.execute("SELECT payment_status FROM commerce_orders WHERE id='order-cancel'").fetchone()[0] == "demo_no_payment"
    db.execute("UPDATE commerce_orders SET status='cancelled' WHERE id='order-cancel'")
    assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='product-1'").fetchone()[0] == 10
    db.execute("UPDATE commerce_orders SET status='cancelled' WHERE id='order-cancel'")
    assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='product-1'").fetchone()[0] == 10

    db.execute(
        "INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,customer_id,account_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("order-return", "merchant-test", "ORD-RETURN", "return-token", "placed", 300, 300, "demo", "legacy-customer-1", "customer-1"),
    )
    db.execute(
        "INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)",
        ("order-return", "product-1", "Test item", 3, 100, 300),
    )
    db.execute("UPDATE commerce_orders SET status='fulfilled' WHERE id='order-return'")
    db.execute(
        "INSERT INTO commerce_order_returns(id,store_id,order_id,account_id,reason) VALUES(?,?,?,?,?)",
        ("return-1", "merchant-test", "order-return", "customer-1", "damaged"),
    )
    db.execute("UPDATE commerce_order_returns SET status='approved' WHERE id='return-1'")
    assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='product-1'").fetchone()[0] == 7
    db.execute("UPDATE commerce_order_returns SET status='received' WHERE id='return-1'")
    assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='product-1'").fetchone()[0] == 10
    db.execute("UPDATE commerce_order_returns SET status='closed_demo' WHERE id='return-1'")
    assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='product-1'").fetchone()[0] == 10
    db.close()


def test_cod_payment_state_is_persisted_and_cancellation_is_not_marked_paid():
    db = _migrated_db()
    db.execute(
        "INSERT INTO commerce_stores(id,slug,name,is_demo,is_active) VALUES(?,?,?,?,?)",
        ("merchant-cod", "cod-shop", "COD Shop", 0, 1),
    )
    db.execute(
        "INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method) VALUES(?,?,?,?,?,?,?,?)",
        ("cod-pending", "merchant-cod", "ORD-COD-1", "cod-token-1", "placed", 500, 500, "cod"),
    )
    assert db.execute("SELECT payment_status FROM commerce_orders WHERE id='cod-pending'").fetchone()[0] == "pending_cod"
    db.execute("UPDATE commerce_orders SET status='cancelled' WHERE id='cod-pending'")
    assert db.execute("SELECT payment_status FROM commerce_orders WHERE id='cod-pending'").fetchone()[0] == "cancelled_no_payment"

    db.execute(
        "INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method) VALUES(?,?,?,?,?,?,?,?)",
        ("cod-paid", "merchant-cod", "ORD-COD-2", "cod-token-2", "delivered", 800, 800, "cod"),
    )
    assert db.execute("SELECT payment_status FROM commerce_orders WHERE id='cod-paid'").fetchone()[0] == "pending_cod"
    db.execute(
        "UPDATE commerce_orders SET payment_status='paid',payment_received_at=CURRENT_TIMESTAMP,payment_received_by='owner@example.invalid',payment_note='Collected at delivery' WHERE id='cod-paid' AND payment_status='pending_cod'"
    )
    row = db.execute("SELECT payment_status,payment_received_at,payment_received_by,payment_note FROM commerce_orders WHERE id='cod-paid'").fetchone()
    assert row["payment_status"] == "paid"
    assert row["payment_received_at"]
    assert row["payment_received_by"] == "owner@example.invalid"
    assert row["payment_note"] == "Collected at delivery"
    db.close()


def test_owner_and_staff_access_records_are_unique_and_role_scoped():
    db = _migrated_db()
    db.execute(
        "INSERT INTO merchant_accounts(id,email,password_hash,password_salt,role,is_active) VALUES(?,?,?,?,?,1)",
        ("owner-1", "owner@example.invalid", "hash", "salt", "owner"),
    )
    db.execute(
        "INSERT INTO commerce_stores(id,slug,name,is_demo,is_active,owner_id) VALUES(?,?,?,?,?,?)",
        ("store-1", "owner-shop", "Owner Shop", 0, 0, "owner-1"),
    )
    db.execute(
        "INSERT INTO merchant_owner_invites(id,email,owner_name,store_name,category,area,token_hash,expires_at,identity_confirmed) VALUES(?,?,?,?,?,?,?,?,1)",
        ("owner-invite-1", "new-owner@example.invalid", "New Owner", "New Shop", "retail", "Dhaka", "a" * 64, "2099-01-01T00:00:00Z"),
    )
    try:
        db.execute(
            "INSERT INTO merchant_owner_invites(id,email,owner_name,store_name,category,area,token_hash,expires_at,identity_confirmed) VALUES(?,?,?,?,?,?,?,?,1)",
            ("owner-invite-2", "new-owner@example.invalid", "New Owner", "New Shop", "retail", "Dhaka", "b" * 64, "2099-01-01T00:00:00Z"),
        )
        assert False, "a second pending owner invitation for the same email must be rejected"
    except sqlite3.IntegrityError:
        pass

    db.execute(
        "INSERT INTO merchant_accounts(id,email,password_hash,password_salt,role,is_active) VALUES(?,?,?,?,?,1)",
        ("staff-1", "staff@example.invalid", "hash", "salt", "staff"),
    )
    db.execute(
        "INSERT INTO merchant_staff_store_access(account_id,owner_id,store_id,role,is_active) VALUES(?,?,?,?,1)",
        ("staff-1", "owner-1", "store-1", "inventory"),
    )
    row = db.execute(
        "SELECT x.role,s.owner_id FROM merchant_staff_store_access x JOIN commerce_stores s ON s.id=x.store_id WHERE x.account_id=?",
        ("staff-1",),
    ).fetchone()
    assert row["role"] == "inventory"
    assert row["owner_id"] == "owner-1"
    db.execute(
        "INSERT INTO merchant_accounts(id,email,password_hash,password_salt,role,is_active) VALUES(?,?,?,?,?,1)",
        ("staff-2", "staff2@example.invalid", "hash", "salt", "staff"),
    )
    try:
        db.execute(
            "INSERT INTO merchant_staff_store_access(account_id,owner_id,store_id,role,is_active) VALUES(?,?,?,?,1)",
            ("staff-2", "owner-1", "store-1", "superadmin"),
        )
        assert False, "unknown staff roles must be rejected"
    except sqlite3.IntegrityError:
        pass
    version = db.execute("SELECT value FROM commerce_meta WHERE key='schema_version'").fetchone()[0]
    assert version == "14"
    db.close()
