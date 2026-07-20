# CLAUDE.md

AI-Powered Business Analytics System — CSE 4th year thesis. Python ML pipeline over a
32k-record synthetic Bangladeshi retail/business transaction dataset.

## Layout

Flat repo. Scripts are numbered and run in order; each writes artifacts the next reads.

| Script | Does | Writes |
|---|---|---|
| `00_normalize_dataset.py` | Splits flat CSV into a star schema (6 dims + 1 fact), re-joins it | `normalized_data/*.csv`, `output/..._Merged.csv` |
| `01_preprocessing.py` | Nulls, label encoding, RFM/season/CLV-tier features, MinMax scale, 70/15/15 split | `output/processed_dataset.csv`, `data_splits.pkl`, `scaler.pkl`, `label_encoders.pkl` |
| `02_classification.py` | XGBoost / RandomForest / LogisticRegression on `Customer_Segment` | `classification_results.pkl`, `models/*.pkl`, figures |
| `03_clustering.py` | K-Means, elbow + silhouette over K=2..10, `OPTIMAL_K = 4` | `customer_segments.csv`, `models/kmeans_model.pkl`, figures |
| `04_forecasting.py` | Monthly sales: LSTM (look-back 6, 100 epochs) vs ARIMA(2,1,2) | `forecast_results.pkl`, figures |
| `05_shap_analysis.py` | SHAP over the XGBoost model | `shap_interpretation.txt`, figures |
| `06_final_report.py` | Reads all `.pkl`s, prints the thesis results tables | stdout only |

`run_all.py` runs 00→06 sequentially and stops on the first non-zero exit.

## Python environments

Two interpreters, deliberately:

- **System Python 3.14** — stages 00–03, 05. TensorFlow has no 3.14 build.
- **`.venv312/` (Python 3.12)** — stage 04 only, because it needs TensorFlow (2.21).

```bash
PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 04_forecasting.py
```

`PYTHONIOENCODING=utf-8` is mandatory on Windows: the console is cp1252 and the
scripts print `→`/`✓`, so it crashes with `UnicodeEncodeError` without it.
`run_all.py` uses `sys.executable`, so it will hit the fallback trap below if run
under 3.14 — run stage 04 by hand.

## Known trap in `04_forecasting.py`

If TensorFlow or statsmodels is missing, the `else:` branches **silently fabricate**
forecasts as `actual + np.random.normal(...)` (5% noise for LSTM, 18% for ARIMA)
instead of failing. That produced an earlier round of fake results (MAPE 0.74%/1.60%).
Real results are ~11.31%/13.29%.

Verify a run was real by checking `output/models/lstm_model.h5` and
`output/figures/lstm_training_loss.png` exist. The block is still in the code and
should be deleted before submission.

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

## Current results (real, verified)

- Classification: XGBoost 94.81% acc · RF 92.33% · LogReg 83.58%
- Clustering: K=4, silhouette **0.1725** — weak, clusters overlap.
- Forecasting: LSTM RMSE 34.4M / MAPE 11.39% vs ARIMA 43.5M / 13.29%. LSTM −21.0% RMSE.
  LSTM numbers drift between runs (EarlyStopping epoch varies: 12 → 16); ARIMA is
  deterministic. Only 36 training sequences; ARIMA logs a convergence warning.
- 15 figures in `output/figures/`.
- `output/forecast_results_SIMULATED_backup.pkl` is the old fake run — never cite it.

## Known methodological weaknesses (documented in README §৮.৪)

Do not present these numbers as clean wins; the README states them honestly.

1. **Target leakage.** `Customer_Lifetime_Value_BDT` nearly determines
   `Customer_Segment` — the segments sit in near-disjoint CLV bands. A depth-3
   decision tree on CLV *alone* scores 91.06% vs XGBoost's 94.81% on 42 features.
   The synthetic generator evidently derived the label from CLV.
2. **`OPTIMAL_K = 4` is hardcoded** ([03_clustering.py:119](03_clustering.py#L119))
   and silhouette actually peaks at K=2 (0.2837 vs 0.1725). Defensible as a business
   choice, but it is not what the metric selected.
3. **Unhandled nulls.** Stage 01 fixes only `Return_Reason`, then prints "No other
   critical missing values found" — but `Campaign_Type` is 30.26% null and
   `Marketing_Channel` 3.8%. `.astype(str)` turns these into a `"nan"` category.
