"""B-SMART Research Portal: real, versioned previews of *synthetic* 32-shop data.

Never assert that the simulated transactions have been imported to tenant DB.
Shop totals, three-year aggregates and one representative invoice were derived
from the generated ZIP and reconciled with the original CSV. Old trained models
and historical benchmark results remain deliberately retired.
"""
from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from . import r2_store

router = APIRouter(prefix="/api/research/portal", tags=["research"])
SOURCE_ROOT = Path(__file__).resolve().parent.parent / "research" / "new_dataset"
SUMMARY = SOURCE_ROOT / "shops_overview.psv"
EXAMPLES = SOURCE_ROOT / "shop_examples.psv"

INT_FIELDS = {
    "orders", "unique_buyers", "registered_customers", "sales_lines",
    "units_sold", "purchase_orders", "stock_movements", "stock_units_end",
    "returns", "unmet_events", "orders_2023", "orders_2024", "orders_2025",
}
FLOAT_FIELDS = {"net_sales_bdt", "sales_2023_bdt", "sales_2024_bdt", "sales_2025_bdt"}

@lru_cache(maxsize=1)
def _all_shops():
    if not SUMMARY.is_file():
        return []
    with SUMMARY.open(encoding="utf-8-sig", newline="") as fd:
        shops = list(csv.DictReader(fd, delimiter="|"))
    expected = {f"SH{i:03d}" for i in range(1, 33)}
    if {s["shop_id"] for s in shops} != expected:
        raise RuntimeError("Incomplete or corrupted synthetic shops preview")
    examples = {}
    if EXAMPLES.is_file():
        with EXAMPLES.open(encoding="utf-8-sig", newline="") as fd:
            examples = {e["shop_id"]: e for e in csv.DictReader(fd, delimiter="|")}
    for row in shops:
        for field in INT_FIELDS:
            row[field] = int(row[field])
        for field in FLOAT_FIELDS:
            row[field] = float(row[field])
        row["years"] = [
            {"year": y, "net_sales_bdt": row[f"sales_{y}_bdt"], "orders": row[f"orders_{y}"]}
            for y in (2023, 2024, 2025)
        ]
        ex = examples.get(row["shop_id"])
        if ex:
            row["recent_invoice_example"] = {
                "order_id": ex["recent_order_id"],
                "date": ex["recent_order_date"],
                "customer_id": ex["recent_order_customer_id"] or None,
                "amount_bdt": float(ex["recent_order_bdt"]),
                "status": ex["recent_order_status"],
            }
            row["top_sku_example"] = {
                "sku_id": ex["top_sku_id"],
                "name": ex["top_sku_name"],
                "units": int(ex["top_sku_units"]),
                "revenue_bdt": float(ex["top_sku_revenue_bdt"]),
            }
        row["evidence_tier"] = "synthetic_simulation"
    if sum(s["orders"] for s in shops) != 365447:
        raise RuntimeError("Shop transaction summary does not reconcile to generated source")
    return shops

def _preview_ready() -> bool:
    try:
        return len(_all_shops()) == 32
    except (OSError, ValueError, RuntimeError):
        return False

@router.get("/datasets")
def datasets():
    preview = _preview_ready()
    return {"datasets": [{
        "vertical": "bangladesh_fmcg",
        "name": "B-SMART Bangladesh SME Integrated Simulation v1",
        "description": "32 fictional Bangladesh FMCG shops, with real generated aggregate summaries",
        "available": preview,
        "preview_available": preview,
        "installed": False,
        "rows": 365447 if preview else 0,
        "evidence_tier": "synthetic_simulation",
        "status": "shop_preview_ready_full_dataset_import_pending" if preview else "awaiting_import",
        "download_path": None,
    }]}

@router.get("/shops")
def shops(search: str = Query("", max_length=120), division: str = Query("", max_length=60)):
    result = _all_shops()
    if search:
        needle = search.casefold().strip()
        result = [s for s in result if needle in
                  (" ".join(str(s.get(k, "")) for k in ("shop_id", "shop_name", "district", "division"))).casefold()]
    if division:
        result = [s for s in result if s["division"].casefold() == division.casefold()]
    return {
        "shops": result,
        "count": len(result),
        "total_shops": len(_all_shops()),
        "total_orders_all": 365447,
        "source": "research/new_dataset/shops_overview.psv",
        "synthetic": True,
        "full_dataset_imported": False,
        "preview_only": True,
    }

@router.get("/shops/{shop_id}")
def shop_detail(shop_id: str):
    row = next((s for s in _all_shops() if s["shop_id"] == shop_id), None)
    if row is None:
        raise HTTPException(404, "No synthetic shop matches this identifier")
    return {"shop": row, "preview_only": True, "full_dataset_imported": False}

@router.get("/vertical-schema")
def schema():
    return {"bangladesh_fmcg": {
        "description": "Bangladesh-context multi-table FMCG simulation",
        "universal_columns": ["order_id","shop_id","customer_id","sku_id","order_datetime","quantity"],
        "vertical_columns": {},
        "vertical_analyses": ["rq1_forecasting","rq2_inactivity","rq3_policy_simulation","rq4_explainability"],
    }}

@router.get("/storage-status")
def storage():
    ok = r2_store.configured()
    return {"r2_configured": ok, "object_storage": "Cloudflare R2" if ok else "not_configured",
            "permanent_uploads_enabled": ok, "models_reset": True, "new_dataset_installed": False,
            "shop_preview_available": _preview_ready()}

@router.get("/experiments")
def experiments(): return {"experiments": []}

@router.get("/datasets/{vertical}/preview")
@router.get("/datasets/{vertical}/download")
def unavailable_dataset(vertical: str):
    raise HTTPException(404, "Full relational research dataset has not been imported. Browse /shops for the aggregate preview.")

@router.get("/experiments/{exp_id}")
@router.get("/experiments/{exp_id}/status")
def unavailable_experiment(exp_id: str):
    raise HTTPException(404, "No new experiment exists after research reset")

@router.post("/experiments")
def create_experiment(body: dict):
    raise HTTPException(503, "New dataset-specific training pipeline has not been installed")

@router.post("/experiments/{exp_id}/run")
def run_experiment(exp_id: str):
    raise HTTPException(503, "New dataset-specific training pipeline has not been installed")

@router.delete("/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    raise HTTPException(404, "No new experiment exists after research reset")

@router.post("/compare")
def compare(body: dict):
    raise HTTPException(422, "There are no completed new experiments")

@router.post("/upload-dataset")
async def upload_dataset():
    raise HTTPException(503, "Full multi-table ZIP importer has not been implemented yet")
