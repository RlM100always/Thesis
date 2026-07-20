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

## Serving layer

```
frontend/  React + Vite + Recharts (:5173)
    │ fetch JSON
api/       FastAPI — main.py · routes.py · schemas.py (:8000)
    │
predict.py  ← the ONLY module that opens a pickle
    │
output/models/*.pkl, output/*.csv
```

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
