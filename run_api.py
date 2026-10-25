"""Run the retained B-SMART business platform without obsolete ML artifacts."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn
    print("B-SMART operational API: http://127.0.0.1:8000/docs")
    print("Research models: reset / not trained")
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
