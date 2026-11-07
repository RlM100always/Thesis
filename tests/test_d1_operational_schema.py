from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.export_d1_operational_schema import generate_schema_sql


def test_operational_schema_generates_and_coexists_with_existing_commerce_tables():
    sql, tables = generate_schema_sql()
    assert len(tables) == 122
    assert len(set(tables)) == 114
    assert {"organizations", "users", "branches", "products", "sales_documents",
            "inventory_balances", "purchase_orders", "journal_entries",
            "payroll_runs", "admin_mission_items", "provider_credentials",
            "model_registry_entries"} <= set(tables)

    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    # Apply the actual current commerce migrations first, then verify the
    # operational schema is additive and does not collide with live D1 tables.
    for migration in sorted(Path("cloudflare/migrations").glob("*.sql")):
        db.executescript(migration.read_text(encoding="utf-8"))
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
    ).fetchone()[0] == 123
    db.close()
