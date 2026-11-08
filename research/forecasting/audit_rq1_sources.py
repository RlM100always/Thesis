"""Audit RQ1 source joins, daily panels and inventory exposure.

Raw business files are read from a controlled local folder and are never copied
into the repository. Outputs contain aggregate diagnostics only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(root: Path, name: str, dates: list[str] | None = None) -> pd.DataFrame:
    path = root / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Required source file is missing: {path}")
    return pd.read_csv(path, parse_dates=dates or [])


def add(rows, item, value, unit, detail):
    rows.append({"audit_item": item, "value": value, "unit": unit, "detail": detail})


def audit(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    current_claim = str(manifest.get("dataset_nature", "Real SME dataset supplied by the researcher"))
    evidence_status = "real_user_provided"
    sku = read_csv(root, "rq1_daily_sku_sales_observed", ["date"])
    shopcat = read_csv(root, "rq1_daily_shop_category", ["date"])
    orders = read_csv(root, "sales_orders", ["order_datetime"])
    lines = read_csv(root, "sales_lines")
    products = read_csv(root, "products")
    movements = read_csv(root, "inventory_movements", ["movement_datetime"])
    purchase_orders = read_csv(root, "purchase_orders")
    purchase_lines = read_csv(root, "purchase_lines")

    rows = []
    add(rows, "sales_orders", len(orders), "rows", "source order table")
    add(rows, "sales_lines", len(lines), "rows", "source transaction-line table")
    add(rows, "sku_daily_observed", len(sku), "rows", "prepared positive-sale daily SKU table")
    add(rows, "shop_category_panel", len(shopcat), "rows", "prepared complete shop-category daily panel")

    # Order-line referential integrity and shop consistency.
    joined = lines.merge(
        orders[["order_id", "order_datetime", "shop_id"]],
        on="order_id", how="left", validate="many_to_one", indicator=True,
        suffixes=("", "_order")
    )
    missing_order = int(joined["_merge"].ne("both").sum())
    shop_mismatch = int(joined["shop_id"].ne(joined["shop_id_order"]).sum())
    add(rows, "sales_lines_without_order", missing_order, "rows", "must be zero")
    add(rows, "sales_line_shop_mismatch", shop_mismatch, "rows", "must be zero")

    joined["date"] = joined["order_datetime"].dt.normalize()
    sku_daily = joined.groupby(["shop_id", "sku_id", "date"], as_index=False).agg(
        units_from_lines=("quantity", "sum"),
        value_from_lines=("net_sales_bdt", "sum")
    )
    sku_compare = sku.merge(
        sku_daily, on=["shop_id", "sku_id", "date"], how="outer",
        indicator=True, suffixes=("_sheet", "_lines")
    )
    unmatched_sku = int(sku_compare["_merge"].ne("both").sum())
    quantity_mismatch = int(
        (sku_compare.loc[sku_compare["_merge"].eq("both"), "units_sold_observed"]
         != sku_compare.loc[sku_compare["_merge"].eq("both"), "units_from_lines"]).sum()
    )
    value_diff = (
        sku_compare.loc[sku_compare["_merge"].eq("both"), "sales_value_bdt_observed"]
        - sku_compare.loc[sku_compare["_merge"].eq("both"), "value_from_lines"]
    ).abs()
    max_value_difference = float(value_diff.max()) if len(value_diff) else None
    add(rows, "sku_daily_unmatched_keys", unmatched_sku, "rows", "outer join of source-line aggregate and prepared SKU table")
    add(rows, "sku_daily_quantity_mismatches", quantity_mismatch, "rows", "must be zero for exact reconciliation")
    add(rows, "sku_daily_value_max_abs_difference", max_value_difference, "BDT", "floating-point reconciliation tolerance")

    # SKU-to-category aggregation. Zero category rows may be absent from the sparse SKU export.
    sku_category = sku.merge(products[["sku_id", "category"]], on="sku_id", how="left", validate="many_to_one")
    missing_category = int(sku_category["category"].isna().sum())
    category_daily = sku_category.groupby(["shop_id", "category", "date"], as_index=False).units_sold_observed.sum()
    category_compare = shopcat.merge(
        category_daily, on=["shop_id", "category", "date"], how="left",
        suffixes=("_panel", "_sku")
    )
    has_sku_sale = category_compare["units_sold_observed_sku"].notna()
    category_positive_mismatch = int(
        ((category_compare["units_sold_observed_panel"] > 0) &
         (~has_sku_sale | (category_compare["units_sold_observed_panel"] != category_compare["units_sold_observed_sku"]))).sum()
    )
    category_zero_rows = int((shopcat["units_sold_observed"] == 0).sum())
    add(rows, "sku_rows_without_product_category", missing_category, "rows", "must be zero")
    add(rows, "positive_shop_category_mismatches", category_positive_mismatch, "rows", "must be zero")
    add(rows, "shop_category_zero_rows", category_zero_rows, "rows", "complete category panel zeros; do not fill sparse SKU dates blindly")

    # Inventory movement reconciliation and daily intraday availability.
    required_mov = {"movement_id", "movement_datetime", "shop_id", "sku_id", "lot_id", "movement_type", "quantity_delta", "reference_id"}
    missing_mov = required_mov - set(movements.columns)
    if missing_mov:
        raise ValueError(f"Inventory movement columns missing: {sorted(missing_mov)}")
    sale_mov = movements[movements["movement_type"].eq("SALE")].copy()
    sale_mov["sold_quantity"] = -sale_mov["quantity_delta"]
    sale_check = lines.merge(
        sale_mov[["reference_id", "shop_id", "sku_id", "lot_id", "sold_quantity"]],
        left_on=["order_id", "shop_id", "sku_id", "lot_id"],
        right_on=["reference_id", "shop_id", "sku_id", "lot_id"],
        how="outer", indicator=True, validate="one_to_one"
    )
    sale_unmatched = int(sale_check["_merge"].ne("both").sum())
    sale_qty_mismatch = int(
        (sale_check.loc[sale_check["_merge"].eq("both"), "quantity"]
         != sale_check.loc[sale_check["_merge"].eq("both"), "sold_quantity"]).sum()
    )
    add(rows, "sale_movement_unmatched", sale_unmatched, "rows", "must be zero for exact ledger-to-sales match")
    add(rows, "sale_movement_quantity_mismatch", sale_qty_mismatch, "rows", "must be zero")

    # Purchase movements must match only received PO/SKU quantities.
    po_lines = purchase_lines.merge(
        purchase_orders[["purchase_order_id", "shop_id"]],
        on="purchase_order_id", how="left", validate="many_to_one"
    )
    received = po_lines.dropna(subset=["quantity_received_final"]).groupby(
        ["purchase_order_id", "shop_id", "sku_id"], as_index=False
    ).quantity_received_final.sum()
    purchase_mov = movements[movements["movement_type"].eq("PURCHASE")].groupby(
        ["reference_id", "shop_id", "sku_id"], as_index=False
    ).quantity_delta.sum()
    purchase_check = received.merge(
        purchase_mov, left_on=["purchase_order_id", "shop_id", "sku_id"],
        right_on=["reference_id", "shop_id", "sku_id"], how="outer", indicator=True
    )
    purchase_unmatched = int(purchase_check["_merge"].ne("both").sum())
    purchase_qty_mismatch = int(
        (purchase_check.loc[purchase_check["_merge"].eq("both"), "quantity_received_final"]
         != purchase_check.loc[purchase_check["_merge"].eq("both"), "quantity_delta"]).sum()
    )
    add(rows, "purchase_movement_unmatched", purchase_unmatched, "groups", "received PO/SKU groups")
    add(rows, "purchase_movement_quantity_mismatch", purchase_qty_mismatch, "groups", "must be zero")
    add(rows, "unreceived_purchase_lines", int(purchase_lines["quantity_received_final"].isna().sum()), "rows", "not treated as received stock")

    # Intraday cumulative balance: flag every movement where stock becomes negative.
    movement_order = movements.sort_values(
        ["shop_id", "sku_id", "movement_datetime", "movement_id"]
    ).copy()
    movement_order["running_balance"] = movement_order.groupby(
        ["shop_id", "sku_id"], sort=False
    )["quantity_delta"].cumsum()
    negative_events = movement_order[movement_order["running_balance"] < 0]
    negative_series = int(negative_events.groupby(["shop_id", "sku_id"]).ngroups)
    movement_order["day"] = movement_order["movement_datetime"].dt.normalize()
    movement_order["day_running_min"] = movement_order.groupby(
        ["shop_id", "sku_id", "day"], sort=False
    )["running_balance"].cummin()
    daily_min = movement_order.groupby(
        ["shop_id", "sku_id", "day"], as_index=False
    ).day_running_min.min()
    positive_sku_days = sku.groupby(["shop_id", "sku_id", "date"], as_index=False).units_sold_observed.sum()
    positive_sku_days = positive_sku_days[positive_sku_days["units_sold_observed"] > 0]
    sale_availability = positive_sku_days.merge(
        daily_min, left_on=["shop_id", "sku_id", "date"],
        right_on=["shop_id", "sku_id", "day"], how="left"
    )
    positive_sale_nonpositive_stock = int((sale_availability["day_running_min"] <= 0).sum())
    add(rows, "negative_stock_movement_events", int((movement_order["running_balance"] < 0).sum()), "events", "must be investigated before SKU exposure labels")
    add(rows, "negative_stock_shop_sku_combinations", negative_series, "combinations", "series containing a negative balance event")
    add(rows, "positive_sale_days_nonpositive_intraday_stock", positive_sale_nonpositive_stock, "days", "quarantine from SKU in-stock supervised targets")

    # Check whether any category zero day has no SKU with positive intraday stock.
    # The dense matrix is limited to the 13k inventory-tracked combinations x 1096 days.
    start, end = shopcat["date"].min(), shopcat["date"].max()
    dates = pd.date_range(start, end, freq="D")
    keys = movements[["shop_id", "sku_id"]].drop_duplicates().reset_index(drop=True)
    key_index = pd.MultiIndex.from_frame(keys)
    mov = movements.copy()
    mov["day"] = mov["movement_datetime"].dt.normalize()
    mov["sid"] = key_index.get_indexer(pd.MultiIndex.from_frame(mov[["shop_id", "sku_id"]]))
    mov["day_idx"] = (mov["day"] - start).dt.days
    before = mov[mov["day"] < start].groupby("sid").quantity_delta.sum()
    n_series, n_days = len(keys), len(dates)
    opening = np.zeros(n_series, dtype=np.float32)
    opening[before.index.to_numpy()] = before.to_numpy(dtype=np.float32)
    during = mov[(mov["day_idx"] >= 0) & (mov["day_idx"] < n_days)].sort_values(
        ["sid", "day_idx", "movement_datetime", "movement_id"]
    ).copy()
    during["intra_cum"] = during.groupby(["sid", "day_idx"], sort=False).quantity_delta.cumsum()
    daily = during.groupby(["sid", "day_idx"], sort=False).agg(
        delta=("quantity_delta", "sum"), min_prefix=("intra_cum", "min")
    ).reset_index()
    delta_matrix = np.zeros((n_series, n_days), dtype=np.float32)
    min_matrix = np.zeros((n_series, n_days), dtype=np.float32)
    np.add.at(delta_matrix, (daily.sid.to_numpy(), daily.day_idx.to_numpy()), daily.delta.to_numpy(np.float32))
    min_matrix[daily.sid.to_numpy(), daily.day_idx.to_numpy()] = daily.min_prefix.to_numpy(np.float32)
    closing = opening[:, None] + np.cumsum(delta_matrix, axis=1)
    opening_day = closing - delta_matrix
    minimum_balance = opening_day + min_matrix
    in_stock = minimum_balance > 0
    add(rows, "reconstructed_in_stock_days", int(in_stock.sum()), "shop-SKU-days", "derived from movement ledger; not external stock audit")
    add(rows, "reconstructed_censored_days", int((~in_stock).sum()), "shop-SKU-days", "non-positive intraday balance")

    product_category = products.set_index("sku_id")["category"].to_dict()
    category_keys = shopcat[["shop_id", "category"]].drop_duplicates().sort_values(
        ["shop_id", "category"]
    ).reset_index(drop=True)
    category_index = pd.MultiIndex.from_frame(category_keys)
    sid_categories = [product_category.get(sku_id) for sku_id in keys["sku_id"]]
    category_codes = category_index.get_indexer(
        pd.MultiIndex.from_arrays([keys["shop_id"].to_numpy(), np.asarray(sid_categories)])
    )
    available_category = np.zeros((len(category_keys), n_days), dtype=np.int16)
    for sid, category_code in enumerate(category_codes):
        if category_code >= 0:
            available_category[category_code] += in_stock[sid].astype(np.int16)
    panel_sorted = shopcat.sort_values(["shop_id", "category", "date"]).reset_index(drop=True)
    zero_matrix = (panel_sorted["units_sold_observed"].to_numpy() == 0).reshape(len(category_keys), n_days)
    zero_category_no_stock = int((zero_matrix & (available_category == 0)).sum())
    add(rows, "category_zero_days_with_no_in_stock_sku", zero_category_no_stock, "rows", "zero category days with no recorded SKU in stock")

    add(rows, "dataset_nature", current_claim, "source declaration", "Drive manifest")

    summary = {
        "audit_version": "1.1.0",
        "evidence_status": evidence_status,
        "dataset_nature": current_claim,
        "manifest_sha256": sha256(manifest_path) if manifest_path.exists() else None,
        "source_files": {
            name: {"rows": int(len(frame)), "columns": list(frame.columns), "sha256": sha256(root / f"{name}.csv")}
            for name, frame in {
                "sales_orders": orders, "sales_lines": lines,
                "rq1_daily_sku_sales_observed": sku,
                "rq1_daily_shop_category": shopcat,
                "inventory_movements": movements
            }.items()
        },
        "shop_count": int(shopcat["shop_id"].nunique()),
        "category_count": int(shopcat["category"].nunique()),
        "shop_category_series": int(shopcat.groupby(["shop_id", "category"]).ngroups),
        "shop_category_rows": int(len(shopcat)),
        "shop_category_units": int(shopcat["units_sold_observed"].sum()),
        "shop_category_zero_ratio": float((shopcat["units_sold_observed"] == 0).mean()),
        "sales_line_order_unmatched": missing_order,
        "sales_line_shop_mismatch": shop_mismatch,
        "sku_daily_unmatched_keys": unmatched_sku,
        "sku_daily_quantity_mismatches": quantity_mismatch,
        "sku_daily_value_max_abs_difference": max_value_difference,
        "positive_shop_category_mismatches": category_positive_mismatch,
        "sale_movement_unmatched": sale_unmatched,
        "sale_movement_quantity_mismatch": sale_qty_mismatch,
        "purchase_movement_unmatched": purchase_unmatched,
        "purchase_movement_quantity_mismatch": purchase_qty_mismatch,
        "negative_stock_movement_events": int((movement_order["running_balance"] < 0).sum()),
        "negative_stock_shop_sku_combinations": negative_series,
        "positive_sale_days_nonpositive_intraday_stock": positive_sale_nonpositive_stock,
        "reconstructed_in_stock_days": int(in_stock.sum()),
        "reconstructed_censored_days": int((~in_stock).sum()),
        "category_zero_days_with_no_in_stock_sku": zero_category_no_stock,
        "raw_data_committed": False
    }
    pd.DataFrame(rows).to_csv(output / "source_reconciliation.csv", index=False)
    (output / "audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = audit(args.data_dir, args.output_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
