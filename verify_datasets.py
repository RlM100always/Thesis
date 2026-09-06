"""Write a reproducibility manifest for every dataset used in the thesis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATASETS = [
    {
        "id": "synthetic_bsmart",
        "path": "BD_Business_Analytics_Dataset.csv",
        "real": False,
        "country": "Bangladesh-context generated data",
        "source": "01_generate_dataset.py (Faker)",
        "use": "controlled development, leakage and model comparison only",
    },
    {
        "id": "uci_online_retail_ii",
        "path": "data/real_public/online_retail_II.csv",
        "real": True,
        "country": "United Kingdom",
        "source": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
        "doi": "10.24432/C5CG6D",
        "use": "real transaction daily-demand and future-repeat validation",
    },
    {
        "id": "bangladesh_retailer_demand",
        "path": "data/real_public/bd_retailer_demand.xlsx",
        "real": True,
        "country": "Bangladesh",
        "source": "https://data.mendeley.com/datasets/xwmbk7n3c8/1",
        "doi": "10.17632/xwmbk7n3c8.1",
        "use": "real one-product quantity forecasting only",
    },
    {
        "id": "wfp_bangladesh_food_prices",
        "path": "data/real_public/wfp_food_prices_bgd.csv",
        "real": True,
        "country": "Bangladesh",
        "source": "https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh",
        "use": "real observed market-price benchmark; not SME sales",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    records = []
    for item in DATASETS:
        record = dict(item)
        path = Path(record["path"])
        record["exists"] = path.is_file()
        if path.is_file():
            record["bytes"] = path.stat().st_size
            record["sha256"] = sha256(path)
        records.append(record)
    manifest = {
        "verified_at": "2026-09-06",
        "rule": "Synthetic and real datasets are never blended into one evidence claim.",
        "datasets": records,
        "all_files_present": all(r["exists"] for r in records),
    }
    Path("output/dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
