"""B-SMART research status only. The separate 32 simulated shops catalogue
has been removed at the user's request. No operational storefront data is
presented as research data, and legacy model results remain unavailable.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from . import r2_store
router = APIRouter(prefix="/api/research/portal", tags=["research"])

@router.get("/datasets")
def datasets():
    return {"datasets": [{
        "vertical": "bangladesh_sme",
        "name": "B-SMART future research dataset",
        "description": "No bundled simulation or generated shop previews are installed.",
        "available": False, "installed": False, "rows": 0,
        "status": "awaiting_research_dataset",
        "download_path": None,
    }]}

@router.get("/vertical-schema")
def schema():
    return {}

@router.get("/storage-status")
def storage():
    configured = r2_store.configured()
    return {"r2_configured": configured,
            "object_storage": "Cloudflare R2" if configured else "not_configured",
            "permanent_uploads_enabled": configured,
            "models_reset": True, "new_dataset_installed": False}

@router.get("/experiments")
def experiments():
    return {"experiments": []}

@router.get("/datasets/{vertical}/preview")
@router.get("/datasets/{vertical}/download")
def no_dataset(vertical: str):
    raise HTTPException(404, "No research dataset is currently installed")

@router.get("/experiments/{exp_id}")
@router.get("/experiments/{exp_id}/status")
def no_experiment(exp_id: str):
    raise HTTPException(404, "There is no active research experiment")

@router.post("/experiments")
def create_experiment(body: dict):
    raise HTTPException(503, "Research pipeline not installed")

@router.post("/experiments/{exp_id}/run")
def run_experiment(exp_id: str):
    raise HTTPException(503, "Research pipeline not installed")

@router.delete("/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    raise HTTPException(404, "No experiment exists")

@router.post("/compare")
def compare(body: dict):
    raise HTTPException(422, "No completed experiments to compare")

@router.post("/upload-dataset")
async def upload_dataset():
    raise HTTPException(503, "Research import pipeline is not installed")
