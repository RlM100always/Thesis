from __future__ import annotations

import sqlite3

from scripts.export_d1_operational_schema import generate_schema_sql


def test_operational_schema_generates_and_coexists_with_existing_commerce_tables():
    sql, tables = generate_schema_sql()
    assert len(tables) == 114
    assert len(set(tables)) == 114
    assert {"organizations", "users", "branches", "products", "sales_documents",
            "inventory_balances", "purchase_orders", "journal_entries",
            "payroll_runs", "admin_mission_items", "provider_credentials",
            "model_registry_entries"} <= set(tables)

    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    # Existing commerce schema is intentionally represented by independent
    # names; the operational migration must not alter it.
    db.execute("CREATE TABLE commerce_stores (id TEXT PRIMARY KEY, is_demo INTEGER NOT NULL)")
    db.execute("CREATE TABLE commerce_products (id TEXT PRIMARY KEY, store_id TEXT NOT NULL)")
    db.executescript(sql)

    actual = {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert set(tables) <= actual
    assert {"commerce_stores", "commerce_products", "operational_schema_meta"} <= actual
    assert db.execute("SELECT version FROM operational_schema_meta").fetchone()[0] == 1
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()


def test_generated_operational_schema_is_idempotent():
    sql, _ = generate_schema_sql()
    db = sqlite3.connect(":memory:")
    db.executescript(sql)
    db.executescript(sql)
    assert db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0] == 115
    db.close()
