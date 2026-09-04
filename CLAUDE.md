# CLAUDE.md

AI-Powered Business Analytics System — CSE 4th year thesis. Python ML pipeline over a
32k-record synthetic Bangladeshi retail/business transaction dataset.

## Layout

Flat repo. Scripts are numbered and run in order; each writes artifacts the next reads.

| Script | Does | Writes |
|---|---|---|
| `00_normalize_dataset.py` | Splits flat CSV into a star schema (6 dims + 1 fact), re-joins it | `normalized_data/*.csv`, `output/..._Merged.csv` |
| `01_preprocessing.py` | Nulls, label encoding, RFM/season/CLV-tier features, MinMax scale, 70/15/15 split | `output/processed_dataset.csv`, `data_splits.pkl`, `scaler.pkl`, `label_encoders.pkl` |
| `01b_customer_features.py` | **v2.** Aggregates to one row per customer, leak-free split, train-only scaler | `customer_features.csv`, `customer_splits.pkl` |
| `02_classification.py` | v1 (leaky). Kept for the ablation "before" column only | `classification_results.pkl`, `models/*.pkl`, figures |
| `02b_classification_v2.py` | **v2.** CV + bootstrap CI + McNemar + ROC + learning curve | `classification_v2_results.pkl`, `models/v2_*.pkl`, `figures/v2_*.png` |
| `03_clustering.py` | K-Means, elbow + silhouette over K=2..10, `OPTIMAL_K = 4` | `customer_segments.csv`, `models/kmeans_model.pkl`, figures |
| `04_forecasting.py` | Monthly sales: LSTM (look-back 6) vs ARIMA(2,1,2) vs seasonal-naive | `forecast_results.pkl`, figures |
| `05_shap_analysis.py` | SHAP over the XGBoost model | `shap_interpretation.txt`, figures |
| `06_final_report.py` | Reads all `.pkl`s, prints the thesis results tables | stdout only |
| `07_return_prediction.py` | Return prediction. Transaction-level, so `GroupShuffleSplit` on `Customer_ID` | `return_results.pkl`, `models/return_model.pkl` |
| `08_churn_prediction.py` | Churn (`Recency > 90`). Customer-level via `01b` | `churn_results.pkl`, `models/churn_model.pkl` |
| `common_eval.py` | Shared binary-task metrics: bootstrap CI, PR/ROC, lift@k | — (imported) |

`run_all.py` runs all 11 stages sequentially and stops on the first non-zero exit.

## Two systems live in this repo: the thesis pipeline (above) and B-SMART

The numbered scripts above are the original static thesis pipeline — synthetic
CSV in, pickles out, `predict.py`/`api/routes.py` serve them read-only. Alongside
it, a second, actively-developed system ("B-SMART") has grown up: a real
multi-tenant operational app (SQL-backed CRUD for orgs/branches/products/sales/
inventory/payments/etc.) plus its own leak-free real-data ML pipeline. **Both
mount into the same FastAPI app (`api/main.py`) and run side by side** — they
share no data model yet, only a CSV schema handshake (see below). Read
`docs/THESIS_PRODUCT_MASTER_PLAN.md`, `docs/FEATURE_STATUS.md`, and
`docs/REAL_DATA_PROTOCOL.md` before touching either the schema or the ML
research-question framing; they are the source of truth for B-SMART, not this
file.

B-SMART layout:

| Module | Does |
|---|---|
| `api/database.py`, `api/config.py` | SQLAlchemy engine/session; `DATABASE_URL` (sqlite dev / Postgres prod), JWT settings from `.env` (see `.env.example`) |
| `api/domain_models.py` | ~20-table multi-tenant schema: Organization, User, Membership, Branch, Product, Customer, Supplier, SalesOrder/Item, Payment, StockMovement, InventoryBalance, Expense, PurchaseOrder/Item, LedgerEntry, SalesReturn/Item, Refund, AuditLog, ImportBatch |
| `alembic.ini`, `migrations/` | Schema migrations (dev uses `create_all` on startup instead; Alembic owns prod upgrades) |
| `api/auth.py` | JWT auth + a dev-mode bypass (auto-creates `developer@bsmart.local`); tenant scoping via required `X-Organization-ID` header |
| `api/app_routes.py`, `commerce_routes.py`, `directory_routes.py`, `finance_routes.py`, `analytics_routes.py` | Org/user, products/inventory/sales, branches/staff/customers/suppliers, purchasing/payments/returns/ledger, operational dashboard — full CRUD against the DB, never touch pickles |
| `api/data_import_routes.py` | Durable CSV/XLSX intake with provenance (checksum, `ImportBatch`), column-mapping validation, and `/api/app/datasets/sales.csv` export in the canonical `bsmart_sales_anonymized.csv` schema |
| `ml/real_pipeline.py` | `python -m ml.real_pipeline --input <canonical-sales.csv> [--organization-id <id>]` — trains fresh models (HistGradientBoostingRegressor demand forecast, future-repeat classifier) on real data; **refuses insufficient data, never fabricates a fallback result**. With `--organization-id`, artifacts land in `artifacts/real/<org_id>/` where the live API finds them |
| `ml/serving.py` | The only module that opens a B-SMART joblib artifact (same rule `predict.py` follows for the thesis pipeline). `predict_daily_rates(org_id, sales_df)` returns per-(branch, SKU) demand predictions, or `{}` when that org has no trained model — never a guessed number |
| `ml/scalability_benchmark.py` | Explicitly-synthetic scale test (100 → 1M rows); its numbers must never be reported as real-data accuracy |
| `tests/` | Covers only the B-SMART DB/API layer (`test_auth.py`, `test_domain_database.py`, `test_commerce_api.py`, `test_operational_analytics.py`) — the numbered pipeline has no automated tests |

`/api/app/recommendations` (`api/analytics_routes.py`) now uses that trained
demand model when one exists for the organization, and falls back to its
transparent 28-day baseline otherwise. Each action carries
`"confidence": "model" | "baseline"` and the response's `model_status` is
`model` / `mixed` / `baseline` — so a heuristic is never presented as an ML
prediction. Train a model for an org by exporting its sales
(`/api/app/datasets/sales.csv`) and running `ml/real_pipeline.py` with
`--organization-id`; the running server picks the artifact up on the next
request, no restart needed.

The bridge between the two systems is the CSV schema: `data_import_routes.py`
exports operational sales in exactly the columns `ml/real_pipeline.py` requires
(`branch_id, invoice_id, line_id, sold_at, customer_pseudo_id, sku, quantity,
unit_price, discount_amount, line_total`). There is no automatic hookup yet —
running the real pipeline on live tenant data is a manual export → train step.

`frontend/src/pages/Upload.jsx` intentionally still calls the *old* pickle-era
`/api/upload*` endpoints (`api/routes.py`) — that page is a one-off scoring
pass against the thesis pickles for a visitor with no account, and never
touches the DB. Real, org-owned sales history intake is a separate feature:
`api/data_import_routes.py`'s `/api/app/imports` → `/api/app/imports/{id}/
validate-sales` → `/api/app/datasets/sales.csv` flow now has both `api.js`
functions (`importSalesFile`, `validateSalesImport`, `exportSalesDataset`) and
a UI section ("প্রকৃত বিক্রয় ইতিহাস আমদানি") on `BusinessSetup.jsx`, gated on
having an active organization. Smoke-tested end to end with curl: upload →
validate correctly flags SKUs not yet in the org's product catalog.

Note: `frontend/src/api.js`'s `appRequest` sends `X-Organization-ID` but never
a bearer token, so every `/api/app/*` call currently relies on `api/auth.py`'s
development-mode bypass — fine for the local thesis demo, but it means
`AUTH_MODE=jwt` in production would break the frontend until token handling
is added client-side (there is also no login/token-issuance endpoint yet to
add it against — external sign-in is explicitly out of scope per
`docs/FEATURE_STATUS.md`).

## Old serving layer (thesis pipeline only)

```
frontend/  React + Vite + Recharts (:5173)
    │ fetch JSON
api/       FastAPI — main.py · routes.py · schemas.py (:8000)
    │
    ├── upload_service.py   ← bring-your-own-CSV scoring (calls predict.py)
predict.py  ← the ONLY module that opens a pickle
    │
output/models/*.pkl, output/*.csv
```

### Bring-your-own-data

`/upload` takes any transaction CSV/Excel, asks the user to map four columns
(customer id, date, amount, quantity), rebuilds RFM features, and ranks customers
by churn risk with a downloadable CSV. `upload_service.py` never opens a pickle —
it calls `predict.py`, same as the route handlers.

**It scores, it never retrains.** Nothing under `output/` is written by the
serving layer, so the thesis numbers cannot drift from a dashboard visit.

Two definitions necessarily differ from `01b_customer_features.py`, because an
uploaded file has no `Days_Since_Last_Purchase` or `Purchase_Frequency_Monthly`
column to average: recency is derived from the newest date in the file, and
frequency from transactions per active month. Measured on this project's own
data cut to the four mappable columns, ranking quality holds up
(ROC-AUC ≈ 0.77 vs the 0.712 headline). The constants are in
`upload_service.py`; **re-measure with complete customer histories** — a
truncated row slice cuts each customer's last purchase and reports ≈0.58 for
reasons unrelated to the model.

Percentages from an upload are *not* calibrated for a business outside the
training data. The response carries a `domain_warning` and the UI renders it;
the `90+ days inactive` column is the dependable one, since it is measured from
the user's own dates rather than predicted.

### Partial payloads use the median, not zero

`predict._vectorise` fills an absent feature with the **population median**.
Filling with 0.0 is not neutral — the MinMax scalers were fit on training data
whose minimum is above zero for most features, so a raw 0.0 scales negative and
lands outside anything the model saw. Symptom when this was wrong: a four-field
churn payload returned 0.93 no matter what those fields said, and every customer
in an uploaded file came back "High" risk. If a prediction looks suspiciously
uniform, check the fill value first.

```powershell
# terminal 1
python run_api.py
# terminal 2
cd frontend; npm run dev
```

Use `run_api.py`, not `python -m uvicorn api.main:app` — the latter resolves
`api.main` against the CWD, so it only works from the project root and fails from
inside `api/` with `ModuleNotFoundError: No module named 'api'`. The launcher pins
the root and verifies artifacts exist before starting.

Swagger UI at `http://127.0.0.1:8000/docs`; dashboard at `http://localhost:5173`.

**Rule:** `predict.py` loads the training-time scaler/encoders and only ever calls
`transform`. Re-fitting on request data would silently produce wrong predictions with
no error. Route handlers must not touch pickles directly.

Frontend files use `.jsx` when they contain JSX — a `.js` file with JSX fails the
Vite build.

## Python environment

`.venv312/` (Python 3.12) — TensorFlow has no build for the system's Python 3.14.
Activate once, then everything is plain `python`:

```powershell
.\.venv312\Scripts\Activate.ps1   # PowerShell
python run_all.py
python run_api.py
```

**No environment variables are required.** `utf8_console.py` is imported first by
every script that prints, and reconfigures stdout/stderr to UTF-8. Adding a new
script that prints `→ ✓ ⚠`? Add `import utf8_console  # noqa: F401` above the other
imports, or it will die with `UnicodeEncodeError` on a cp1252 console.

Never document `PYTHONIOENCODING=utf-8 ...` or any `VAR=value cmd` form — this user
is on PowerShell, where that is parsed as a command name and fails.

## Fixed: the fabricated-forecast trap

`04_forecasting.py` used to fall back to `actual + np.random.normal(...)` when
TensorFlow or statsmodels was missing, silently producing fake results (MAPE 0.74%).
Both fallbacks are now removed — the script raises `SystemExit` with install
instructions instead. A missing dependency can no longer look like a finding.

Verify a run was real by checking `output/models/lstm_model.h5` and
`output/figures/lstm_training_loss.png` exist.

## Conventions

- Run from the repo root — every path is relative (`output/...`), so CWD matters.
- Matplotlib is `Agg`-backed; figures go to `output/figures/` at 300 DPI, never `plt.show()`.
- Palette used across figures: `#0A8754` green, `#0D1B2A` navy, `#E63946` red, `#64748B` grey.
- `random_state=42` everywhere. Keep it — thesis numbers must reproduce.
- Intermediate state is passed via `pickle`, not re-computed.
- CSVs are written `encoding="utf-8-sig"` (Excel-friendly, BOM on the header).
- Amounts are BDT; the currency suffix `_BDT` is part of the column names.

## Real data: what actually exists

`docs/REAL_DATA_SOURCES.md` is the register — read it before claiming anything
is "real". Summary of the three tiers:

- **Tier 1 (primary, NOT YET COLLECTED)** — consenting-SME sales records per
  `docs/REAL_DATA_PROTOCOL.md`. `docs/SME_DATA_COLLECTION_KIT.md` has the Bangla
  consent form and CSV template to go collect it. Lands in `data/real_sme/`,
  which is **gitignored — never commit shop data**.
- **Tier 2 (public, downloaded)** — `data/real_public/wfp_food_prices_bgd.csv`:
  real WFP/DAM Bangladeshi market prices, 33,606 rows, 110 markets, BDT,
  CC BY-IGO (attribution required). Served by `ml/market_prices.py`. Supports
  the `X_market` price feature and a real forecasting benchmark; it has **no
  quantities, customers, or stock**, so it cannot support demand forecasting,
  churn, or inventory strategy.
- **Tier 3 (synthetic)** — `BD_Business_Analytics_Dataset.csv`, everything under
  `output/`.

Never blend tiers in one reported number.

`python -m ml.market_prices --all` reruns the real price benchmark. Current
honest result: the naive last-value baseline wins on 3 of 4 staples and
gradient boosting loses badly — same baseline-discipline lesson as the
synthetic pipeline's seasonal-naive finding. Report it as-is.

## Real-data candidate files — parked in `candidate_datasets_not_used/`

`online_retail_II.xlsx` (UCI/Kaggle "Online Retail II", UK gift retailer, GBP)
and `real-datasets.csv` (scraped Daraz.com.bd product-catalog/review listings,
not transaction data) used to sit untracked at the repo root; moved into
`candidate_datasets_not_used/` (see its README) since **neither is referenced
by any script and neither satisfies the thesis's "real data" requirement**:
Daraz data has no transaction/customer fields needed for RFM/churn/forecast,
and Online Retail II is real but not Bangladeshi — using it as a primary
result would undercut the thesis's Bangladeshi-SME claim. If used at all,
Online Retail II belongs only as an explicitly-labelled non-Bangladeshi
cross-dataset check, never the headline evidence. The actual path to real
evidence is `docs/REAL_DATA_PROTOCOL.md` (consenting Bangladeshi SMEs) feeding
`ml/real_pipeline.py`.

## Working here

- Don't read `BD_Business_Analytics_Dataset.csv` (11 MB, 32k rows, 44 cols) directly —
  the column list is in this file's schema section of `README.md`; sample with `head`.
- Don't regenerate `output/` or `normalized_data/` casually; those artifacts back figures
  already cited in the thesis text. Ask first.
- Editing a step invalidates every later step — rerun the tail of the pipeline, not just one file.
- TensorFlow is the heaviest dependency; step 04 is the only consumer.

## Two pipelines: v1 (leaky) and v2 (honest)

**v1** = `01` → `02`, transaction-level. Its 94.69% is inflated by leakage and is
kept only as the "before" column of the ablation table. **Do not cite v1 numbers
as results.**

**v2** = `01` → `01b` → `02b`, customer-level and leak-free. These are the real
numbers.

| Stage | v2 file | What changed |
|---|---|---|
| Features | `01b_customer_features.py` | Aggregates to 4,996 customers (1 row each), so a customer cannot span splits. Scaler fit on train only. CLV excluded. |
| Classification | `02b_classification_v2.py` | 5-fold CV with per-fold scaling, bootstrap CIs, McNemar, macro metrics, class weighting, ROC + learning curves. |

To regenerate the leaky variant for the ablation (PowerShell):

```powershell
$env:INCLUDE_CLV = "1";    python 01b_customer_features.py; python 02b_classification_v2.py
$env:INCLUDE_CLV = $null;  python 01b_customer_features.py; python 02b_classification_v2.py
```

The second line is not optional — it restores the honest artifacts that `predict.py`
and the API serve.

## Current results (leak-free, verified)

**Classification** (750 held-out customers, 34 features):

| Model | Test acc | 95% CI | F1-macro | 5-fold CV |
|---|---|---|---|---|
| XGBoost | 67.07% | [63.87, 70.53] | 69.69% | 67.97% ± 1.18 |
| Logistic Regression | 64.00% | [60.80, 67.47] | 65.88% | 65.09% ± 1.19 |
| Random Forest | 62.80% | [59.47, 66.27] | 65.09% | 65.07% ± 0.91 |

McNemar XGBoost vs RF: p = 0.0103 → significant. Learning curve shows a 32-point
train/CV gap (overfitting; more data would help).

**Leakage ablation** — same leak-free split, only the CLV feature differs:

| Variant | XGBoost acc |
|---|---|
| v1 transaction-level + CLV (both leaks) | 94.69% |
| customer-level + CLV (CLV leak only) | 94.53% |
| **customer-level, no CLV (honest)** | **67.07%** |

CLV alone accounts for ~27 points. Note McNemar is *not* significant (p = 0.52) in
the CLV variant — when one feature determines the label, model choice stops mattering.

**Forecasting** — the seasonal-naive baseline **wins**:

| Model | RMSE | MAE | MAPE |
|---|---|---|---|
| **Seasonal-naive** | **29,824,641** | **15,313,944** | **6.60%** |
| LSTM | 35,870,997 | 24,972,834 | 11.91% |
| ARIMA(2,1,2) | 43,509,553 | 28,922,927 | 13.29% |

"LSTM beats ARIMA" is true but misleading: "same month last year" beats both. State
this plainly — it is the strongest evidence in the thesis that the series is
seasonal. LSTM numbers drift slightly between runs (EarlyStopping epoch varies);
ARIMA and seasonal-naive are deterministic.

**Churn** (`Recency > 90`, base rate 20.2%): Logistic Regression wins — ROC-AUC 0.712,
PR-AUC 0.421 vs 0.202 random, **2.48x lift @10%**. Genuinely usable for ranking a
retention campaign.

**Returns** (base rate 6.97%): Random Forest, ROC-AUC 0.580, PR-AUC 0.0877 vs 0.0697
random, 1.38x lift. **A negative result — report it as one.** Returns are near-random
with respect to pre-dispatch features.

> A first version scored ROC-AUC 0.97 because `Customer_Satisfaction_Score` was in the
> feature set. That score is given *after* the purchase experience: every transaction
> rated ≥4.1 has a 0.00% return rate and no returned item scores above 4.0. It is a
> consequence of the return, not a predictor. Same family of bug as the CLV leak —
> when a binary model looks great, check for post-outcome features first.

**Clustering:** K=4, silhouette 0.1725 — weak, clusters overlap. Silhouette actually
peaks at K=2 (0.2837); `OPTIMAL_K = 4` is hardcoded
([03_clustering.py:119](03_clustering.py#L119)). Defensible as a business choice,
but it is not what the metric selected.

`output/forecast_results_SIMULATED_backup.pkl` is the old fake run — never cite it.
