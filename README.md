# B-SMART — Bangladesh SME Business Analytics

> **Research reset (25 October 2026).** All previously committed research datasets, trained model binaries, legacy ML pipelines and old experiment results were removed from **main**. They remain recoverable at [archive/pre-new-bsmart-dataset-2026-10-25](https://github.com/RlM100always/Thesis/tree/archive/pre-new-bsmart-dataset-2026-10-25).

## Store preview restored

The public website now includes a read-only [**32 simulated stores explorer**](https://thesis-j0n8.onrender.com/#/sample-stores). It shows Bangladesh division/district store cards, 2023–2025 generated revenue, order/customer/purchase/stock summaries, top product and an invoice example for each shop. Source summaries [here](research/new_dataset/shops_overview.psv), examples [here](research/new_dataset/shop_examples.psv) and scope/limitations [here](research/new_dataset/STORE_EXPLORER_README.md). **This is NOT a full operational database import.** The changes must deploy and load to become visible on the hosted website.

## New sole research dataset

**B-SMART Bangladesh SME Integrated Research Simulation v1**: fictional FMCG shops, customers, suppliers and BDT transactions spanning 2023–2025, with 32 shops, 11,000 customers, 480 SKUs and 56 suppliers. **100% synthetic**, not actual collected Bangladesh SME sales. The `63,104,115`-byte source ZIP was shared as a conversation download, **not committed to GitHub and not installed on Render**. Check its [source manifest](research/new_dataset/manifest.json) before importing.

**No new ML model has been trained on main after this reset.** Research Portal exposes 32 simulated shop summary previews while the full transactional dataset and models remain *awaiting import*. Old scoring routes and experiments are retired instead of misleadingly reporting old metrics as new findings.

## Retained software

React frontend + FastAPI application with authenticational/multi-tenant business infrastructure, inventory, sales, supplier and payment workflows, accounting, audit, permissions and Alembic migrations. Operational baseline heuristics are not claims of trained ML. Deployment health reports `artifacts_loaded: false`.

## New research roadmap

[Read the RQ1–RQ4 rebuilding protocol](docs/NEW_DATASET_REBUILD.md). RQ1/RQ2 outcomes will be measured on the synthetic dataset only. RQ3 is an explicitly simulated policy evaluation. RQ4 evaluates technical explanation checks; genuine owner usability cannot be proven without human testing. The [existing thesis report source archive](thesis_report/archive/2026-10-25_user_submitted_report.tex) was preserved; its original pharmacy-oriented scope has not yet been amended.

## Development

- Backend: `pip install -r requirements.render.txt` and `python run_api.py`
- Frontend: `cd frontend && npm ci && npm run dev`
- Docker builds the product without re-generating seven legacy datasets.
- Configure durable PostgreSQL and secure Cloudflare R2 credentials separately before storing real business data.

**Important:** This GitHub cleanup does **not** purge Render databases, Cloudflare R2 buckets or Git commit history. The new source archive must be uploaded/imported before model development resumes.
