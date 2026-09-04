"""Reproducible, explicitly synthetic scalability benchmark.

This measures data-path engineering only; its rows must never be mixed with
real-business accuracy results. Example:
    python -m ml.scalability_benchmark --scales 100 500 1000 10000
    python -m ml.scalability_benchmark --scales 100000 1000000 --output artifacts/scalability.csv
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd


def timed(callable_):
    start = time.perf_counter()
    value = callable_()
    return value, time.perf_counter() - start


def make_rows(size: int) -> pd.DataFrame:
    rng = np.random.default_rng(42 + size)
    start = np.datetime64("2024-01-01")
    return pd.DataFrame({
        "organization_id": "SYNTHETIC-SCALABILITY-ONLY",
        "branch_id": rng.choice(["B1", "B2", "B3"], size),
        "invoice_id": [f"INV-{i // 3:09d}" for i in range(size)],
        "line_id": [f"LINE-{i:09d}" for i in range(size)],
        "sold_at": start + rng.integers(0, 730, size).astype("timedelta64[D]"),
        "customer_pseudo_id": [f"C-{i % max(10, size // 8):07d}" for i in range(size)],
        "sku": [f"SKU-{i % max(10, min(5000, size // 5)):05d}" for i in range(size)],
        "quantity": rng.integers(1, 6, size),
        "unit_price": rng.integers(20, 3000, size).astype(float),
        "discount_amount": rng.choice([0, 0, 0, 5, 10], size).astype(float),
    }).assign(line_total=lambda x: x.quantity * x.unit_price - x.discount_amount)


def benchmark(size: int) -> dict:
    tracemalloc.start()
    frame, generate_s = timed(lambda: make_rows(size))
    with tempfile.TemporaryDirectory(prefix="bsmart-scale-") as folder:
        csv_path = Path(folder) / "synthetic.csv"
        _, csv_write_s = timed(lambda: frame.to_csv(csv_path, index=False))
        loaded, csv_read_s = timed(lambda: pd.read_csv(csv_path, parse_dates=["sold_at"]))
        daily, preprocess_s = timed(lambda: loaded.groupby(
            ["branch_id", "sku", loaded.sold_at.dt.floor("D")], as_index=False
        ).agg(quantity=("quantity", "sum"), revenue=("line_total", "sum")))
        connection = sqlite3.connect(":memory:")
        _, db_insert_s = timed(lambda: loaded.to_sql("sales", connection, index=False, if_exists="replace"))
        query, db_query_s = timed(lambda: pd.read_sql_query(
            "SELECT branch_id, sku, SUM(quantity) quantity, SUM(line_total) revenue "
            "FROM sales GROUP BY branch_id, sku ORDER BY revenue DESC LIMIT 100", connection
        ))
        connection.close()
        peak_mb = tracemalloc.get_traced_memory()[1] / 1024 / 1024
        csv_size_mb = csv_path.stat().st_size / 1024 / 1024
    tracemalloc.stop()
    return {
        "data_class": "synthetic_scalability_only", "rows": size,
        "generated_rows_per_second": round(size / generate_s, 2),
        "csv_write_seconds": round(csv_write_s, 6), "csv_import_seconds": round(csv_read_s, 6),
        "preprocess_seconds": round(preprocess_s, 6), "prepared_rows": len(daily),
        "database_insert_seconds": round(db_insert_s, 6), "database_query_seconds": round(db_query_s, 6),
        "query_result_rows": len(query), "peak_memory_mb": round(peak_mb, 2),
        "csv_size_mb": round(csv_size_mb, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scales", nargs="+", type=int, default=[100, 500, 1000, 10_000])
    parser.add_argument("--output", type=Path, default=Path("artifacts/scalability.csv"))
    args = parser.parse_args()
    if any(size <= 0 for size in args.scales):
        parser.error("Every scale must be positive")
    results = []
    for size in args.scales:
        result = benchmark(size)
        results.append(result)
        print(json.dumps(result))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(args.output, index=False)
    print(f"Saved clearly-labelled synthetic benchmark: {args.output}")


if __name__ == "__main__":
    main()
