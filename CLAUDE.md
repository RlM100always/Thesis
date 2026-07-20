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
