"""Adapters: map real public datasets into ml/real_pipeline.py's canonical
sales schema (branch_id, invoice_id, line_id, sold_at, customer_pseudo_id,
sku, quantity, unit_price, discount_amount, line_total).

These are NOT Bangladeshi SME transaction data — see docs/REAL_DATA_SOURCES.md
for what each dataset can and cannot support. This module only adapts column
names/types; ml.real_pipeline.validate_sales does the actual validation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ONLINE_RETAIL_II_PATH = Path("data/real_public/online_retail_II.csv")
BD_RETAILER_DEMAND_PATH = Path("data/real_public/bd_retailer_demand.xlsx")


def load_online_retail_ii(path: Path = ONLINE_RETAIL_II_PATH) -> pd.DataFrame:
    """Real invoice-level transactions from a UK gift retailer (UCI, CC BY 4.0).

    Genuine transaction-level data — real quantities, prices, dates, and
    customer IDs — which is exactly what this project could not find for any
    Bangladeshi source. It is NOT Bangladeshi; report it only as a
    cross-context validation of the modelling method, never as evidence about
    Bangladeshi customer behaviour.

    Cancelled/returned lines (negative quantity, or an Invoice recorded as
    starting with "C") are dropped — ml.real_pipeline trains a forward
    demand/churn model, not a returns model, and validate_sales requires
    quantity > 0. This is data cleaning, not fabrication: every dropped row
    is a real cancellation, still counted and reported.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Download the UCI 'Online Retail II' dataset (CC BY 4.0), "
            "combine both year sheets, and save as CSV at that path — the raw .xlsx (2 "
            "sheets, ~1M rows) is too memory-heavy for openpyxl to parse directly on a "
            "constrained machine; converting once via openpyxl's read_only streaming "
            "mode avoids that."
        )
    # dtype hints avoid pandas' float64 default for large integer-like columns,
    # which roughly halves peak memory on a ~1M-row file.
    frame = pd.read_csv(
        path,
        dtype={"Invoice": str, "StockCode": str, "Quantity": "int32", "Price": "float32"},
        parse_dates=["InvoiceDate"],
    )

    before = len(frame)
    is_cancelled = frame["Invoice"].astype(str).str.startswith("C")
    frame = frame[~is_cancelled & (frame["Quantity"] > 0) & (frame["Price"] >= 0)]
    cancelled_dropped = int(before - len(frame))

    frame = frame.dropna(subset=["Customer ID"])
    line_total = frame["Quantity"] * frame["Price"]

    canonical = pd.DataFrame({
        "branch_id": "MAIN",
        "invoice_id": frame["Invoice"].astype(str),
        "line_id": [f"OR2-{i}" for i in range(len(frame))],
        "sold_at": frame["InvoiceDate"],
        "customer_pseudo_id": frame["Customer ID"].astype(int).astype(str),
        "sku": frame["StockCode"].astype(str),
        "quantity": frame["Quantity"].astype(float),
        "unit_price": frame["Price"].astype(float),
        "discount_amount": 0.0,
        "line_total": line_total.astype(float),
    })
    canonical.attrs["source"] = "UCI Online Retail II (UK, real transactions, CC BY 4.0)"
    canonical.attrs["cancelled_rows_dropped"] = cancelled_dropped
    canonical.attrs["source_rows"] = before
    return canonical.sort_values("sold_at").reset_index(drop=True)


def load_bd_retailer_demand(path: Path = BD_RETAILER_DEMAND_PATH) -> pd.DataFrame:
    """Real daily demand for one product from an actual Bangladeshi retailer
    (Mendeley DOI 10.17632/xwmbk7n3c8.1, Khulna University of Engineering and
    Technology, CC BY 4.0). 1,826 days, 2013-01-01 to 2017-12-31.

    Only two real fields exist: date and quantity sold. Every other canonical
    column below is a required placeholder, NOT a measurement:
      - customer_pseudo_id is always "ANONYMOUS" — there is no customer field
        in the source, so no churn/RFM analysis is possible on this dataset.
      - unit_price is a constant 1.0 — there is no price field in the source,
        so line_total is a proxy for quantity only, never a revenue figure.
    Use this dataset ONLY for demand-forecasting validation on real
    Bangladeshi data; never report a "revenue" or "customer" number from it.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Download from https://data.mendeley.com/datasets/xwmbk7n3c8/1 "
            "(CC BY 4.0) and place it there."
        )
    frame = pd.read_excel(path)
    date_col = "date" if "date" in frame.columns else frame.columns[1]
    qty_col = "sales" if "sales" in frame.columns else frame.columns[2]

    canonical = pd.DataFrame({
        "branch_id": "MAIN",
        "invoice_id": [f"BD-{i}" for i in range(len(frame))],
        "line_id": [f"BD-{i}" for i in range(len(frame))],
        "sold_at": pd.to_datetime(frame[date_col], utc=True),
        "customer_pseudo_id": "ANONYMOUS",
        "sku": "PRODUCT-1",
        "quantity": frame[qty_col].astype(float),
        "unit_price": 1.0,
        "discount_amount": 0.0,
        "line_total": frame[qty_col].astype(float),
    })
    canonical.attrs["source"] = (
        "Mendeley 10.17632/xwmbk7n3c8.1 — real Bangladeshi retailer, quantity only"
    )
    return canonical.sort_values("sold_at").reset_index(drop=True)
