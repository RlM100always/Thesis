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
