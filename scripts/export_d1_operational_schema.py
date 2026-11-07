#!/usr/bin/env python3
"""Generate an additive SQLite/D1 schema from the complete SQLAlchemy model metadata.

This creates schema only. It never connects to or reads the live Render or
Cloudflare databases, and it never generates business rows.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from sqlalchemy import create_engine, text

from api.database import Base
from api import domain_models  # noqa: F401 - register operational tables
from api import admin_models  # noqa: F401 - register platform-control tables

EXPECTED_MODEL_TABLES = 114


def generate_schema_sql() -> tuple[str, list[str]]:
    """Compile all registered model tables and indexes with SQLite's dialect."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE type IN ('table','index') "
            "AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
            "ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name"
        )).all()

    tables = sorted(
        row.name for row in rows if row.type == "table"
    )
    if len(tables) != EXPECTED_MODEL_TABLES:
        raise RuntimeError(
            f"Expected {EXPECTED_MODEL_TABLES} operational/platform tables, "
            f"found {len(tables)}: {tables}"
        )

    statements: list[str] = []
    for row in rows:
        sql = row.sql.strip().rstrip(";")
        if row.type == "table":
            sql = re.sub(
                r"^CREATE TABLE\\s+",
                "CREATE TABLE IF NOT EXISTS ",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        elif row.type == "index":
            sql = re.sub(
                r"^CREATE (UNIQUE )?INDEX\\s+",
                lambda match: "CREATE " + (match.group(1) or "") + "INDEX IF NOT EXISTS ",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        statements.append(sql + ";")

    statements.extend([
        "CREATE TABLE IF NOT EXISTS operational_schema_meta ("
        "version INTEGER PRIMARY KEY, source TEXT NOT NULL, "
        "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);",
        "INSERT OR IGNORE INTO operational_schema_meta(version,source) "
        "VALUES (1,'api.domain_models+api.admin_models');",
    ])
    header = (
        "-- Generated from api.domain_models and api.admin_models.\n"
        "-- Schema only: no business records, users, stores, orders or payments.\n"
        f"-- Model tables: {len(tables)}. Existing commerce_* tables are not modified.\n"
        "-- Safe to reapply: table and index DDL use IF NOT EXISTS.\n\n"
    )
    return header + "\n".join(statements) + "\n", tables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sql, tables = generate_schema_sql()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql, encoding="utf-8")
    print(f"Generated {len(tables)} model tables / {len(sql)} SQL characters")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
