"""Research Portal — clean October 2026 restart, no legacy experiments.

The single new research dataset is a Bangladesh-context SYNTHETIC simulation.
It has not been deployed or trained in this repository yet. Until a proper
multi-table import and experiment pipeline exists, endpoints fail closed.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from . import r2_store

router = APIRouter(prefix="/api/research/portal", tags=["research"])
DATASET = {
    "vertical": "bangladesh_fmcg",
    "name": "B-SMART Bangladesh SME Integrated Research Simulation v1",
    "description": "100% synthetic Bangladesh-context FMCG operations (not actual merchant records)",
    "available": False,
    "installed": False,
    "rows": 0,
    "evidence_tier": "synthetic_simulation",
    "download_path": None,
    "status": "awaiting_import",
}

@router.get("/datasets")
def datasets():
    return {"datasets": [DATASET]}

@router.get("/vertical-schema")
def schema():
    return {
        "bangladesh_fmcg": {
            "description": DATASET["description"],
            "universal_columns": ["order_id", "shop_id", "customer_id", "sku_id", "order_datetime", "quantity"],
            "vertical_columns": {},
            "vertical_analyses": ["rq1_forecasting", "rq2_inactivity", "rq3_policy_simulation", "rq4_technical_explainability"],
        }
    }

@router.get("/storage-status")
def storage():
    ok = r2_store.configured()
    return {"r2_configured": ok, "object_storage": "Cloudflare R2" if ok else "not_configured",
            "permanent_uploads_enabled": ok, "models_reset": True, "new_dataset_installed": False}

@router.get("/experiments")
def experiments():
    return {"experiments": []}

@router.get("/datasets/{vertical}/preview")
@router.get("/datasets/{vertical}/download")
def unavailable_dataset(vertical: str):
    raise HTTPException(404, "New research dataset is not yet imported")

@router.get("/experiments/{exp_id}")
@router.get("/experiments/{exp_id}/status")
def unavailable_experiment(exp_id: str):
    raise HTTPException(404, "No new experiment exists after the research reset")

@router.post("/experiments")
def create_experiment(body: dict):
    raise HTTPException(503, "New dataset-specific training pipeline is not yet installed")

@router.post("/experiments/{exp_id}/run")
def run_experiment(exp_id: str):
    raise HTTPException(503, "Old models removed; no new trainer installed")

@router.delete("/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    raise HTTPException(404, "No experiment exists after reset")

@router.post("/compare")
def compare(body: dict):
    raise HTTPException(422, "There are no completed new experiments")

@router.post("/upload-dataset")
async def upload_dataset():
    raise HTTPException(503, "Multi-table ZIP importer for the new dataset has not been installed")
