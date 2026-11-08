"""Research portal status for the Drive-managed thesis dataset.

The real SME source files are maintained in the project's private Google Drive.
This API does not host raw source records and does not yet execute the research
pipelines directly. Saved RQ1 code and aggregate experiment outputs are in GitHub.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from . import r2_store
router = APIRouter(prefix="/api/research/portal", tags=["research"])

@router.get("/datasets")
def datasets():
    return {"datasets": [{
        "vertical": "bangladesh_sme",
        "name": "Real Bangladesh SME research dataset",
        "description": "Source files are maintained in the project Google Drive folder; this API does not serve raw records.",
        "source": "project_google_drive",
        "available": True,
        "installed_in_api": False,
        "status": "drive_managed",
        "download_path": None,
    }]}

@router.get("/vertical-schema")
def schema():
    return {
        "vertical": "bangladesh_sme",
        "source": "project_google_drive",
        "research_questions": ["RQ1_demand_forecasting", "RQ2_customer_prediction", "RQ3_replenishment", "RQ4_explanation_evaluation"],
    }

@router.get("/storage-status")
def storage():
    configured = r2_store.configured()
    return {
        "r2_configured": configured,
        "object_storage": "Cloudflare R2" if configured else "not_configured",
        "permanent_uploads_enabled": configured,
        "research_data_source": "project_google_drive",
        "raw_research_files_hosted_by_api": False,
        "model_artifacts_loaded": False,
    }

@router.get("/experiments")
def experiments():
    return {"experiments": [{
        "id": "rq1_fixed_origin_v2",
        "name": "RQ1 fixed-origin multi-model development benchmark",
        "source": "GitHub research/forecasting/results/rq1_fixed_origin_v2",
        "status": "saved_development_results",
        "final_holdout_evaluated": False,
    }]}

@router.get("/datasets/{vertical}/preview")
@router.get("/datasets/{vertical}/download")
def no_dataset(vertical: str):
    raise HTTPException(503, "The real research dataset is maintained in Google Drive and is not served as raw data by this API")

@router.get("/experiments/{exp_id}")
@router.get("/experiments/{exp_id}/status")
def no_experiment(exp_id: str):
    if exp_id == "rq1_fixed_origin_v2":
        return {"id": exp_id, "status": "saved_development_results", "final_holdout_evaluated": False}
    raise HTTPException(404, "No matching saved experiment is registered")

@router.post("/experiments")
def create_experiment(body: dict):
    raise HTTPException(503, "The research pipeline is available in the GitHub repository but is not connected to this API")

@router.post("/experiments/{exp_id}/run")
def run_experiment(exp_id: str):
    raise HTTPException(503, "The research model runner is not connected to this API")

@router.delete("/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    raise HTTPException(404, "No API-managed experiment exists")

@router.post("/compare")
def compare(body: dict):
    raise HTTPException(422, "Live API comparison is not available; inspect the saved research outputs in GitHub")

@router.post("/upload-dataset")
async def upload_dataset():
    raise HTTPException(503, "The research source files are maintained in Google Drive; upload is not enabled in this API")
