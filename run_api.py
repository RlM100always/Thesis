"""
=============================================================
API LAUNCHER
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
HOW TO RUN (any shell, any working directory):

    python run_api.py

Then open http://127.0.0.1:8000/docs for the interactive Swagger UI.

WHY A LAUNCHER INSTEAD OF CALLING UVICORN DIRECTLY
--------------------------------------------------
`python -m uvicorn api.main:app` only works from the project root, because
"api.main" is resolved against the current directory. Running it from
inside api/ fails with a confusing error:

    ModuleNotFoundError: No module named 'api'

This script pins the working directory to the project root first, so it
does not matter where you launch it from. It also checks that the pipeline
has actually been run, and says so plainly instead of surfacing an
ImportError from deep inside the model-loading code.
"""

import utf8_console  # noqa: F401  — UTF-8 stdout before any printing

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Both are needed: chdir fixes the relative paths inside predict.py, and the
# sys.path entry lets "api.main" resolve regardless of the launch directory.
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

REQUIRED = [
    ROOT / "output" / "customer_splits.pkl",
    ROOT / "output" / "customer_features.csv",
    ROOT / "output" / "models" / "v2_xgboost.pkl",
    ROOT / "output" / "models" / "churn_model.pkl",
    ROOT / "output" / "models" / "return_model.pkl",
]

missing = [p for p in REQUIRED if not p.exists()]
if missing:
    print("ERROR: the pipeline has not been run — required artifacts are missing:\n")
    for p in missing:
        print(f"  - {p.relative_to(ROOT)}")
    print("\nRun the pipeline first:\n\n    python run_all.py\n")
    sys.exit(1)

if __name__ == "__main__":
    import uvicorn

    print("=" * 62)
    print("  AI Business Analytics API")
    print("=" * 62)
    print("  Swagger UI : http://127.0.0.1:8000/docs")
    print("  Health     : http://127.0.0.1:8000/health")
    print("  Dashboard  : http://localhost:5173   (cd frontend; npm run dev)")
    print("=" * 62)

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
