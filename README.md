# AI-Powered Business Analytics System for Bangladeshi Businesses

CSE 4th Year Thesis — an end-to-end machine learning pipeline that turns raw retail
transaction records into decisions a business owner can actually act on: *who* the
valuable customers are, *why* the model thinks so, and *what* next quarter's sales
look like.

---

## 1. The problem we are solving

Small and medium businesses in Bangladesh generate transaction data continuously —
POS records, bKash/Nagad payments, delivery logs, campaign responses — and almost
none of it is used analytically. In practice three gaps recur:

1. **No segmentation.** Every customer is treated identically. Marketing spend is
   spread flat instead of concentrated on the ~20% of customers who drive most profit.
2. **No forward view.** Inventory and staffing are planned from last month's gut feel,
   not a forecast, which is expensive in a market with sharp seasonality
   (Ramadan/Eid, Pohela Boishakh, monsoon).
3. **No trust in models, where they exist.** A black-box score that says "this customer
   is high value" is ignored by the person who has to act on it, because it gives no
   reason.

The academic gap mirrors this: most published work on customer analytics uses Western
or Chinese e-commerce datasets, with payment methods, festival seasonality, and
divisional geography that do not transfer to Bangladesh.

**So the thesis question is:** can a single reproducible pipeline deliver accurate
segmentation, reliable sales forecasting, *and* human-readable explanations, on data
that reflects Bangladeshi business reality?

---

## 2. What the system does

Four analytical capabilities, in one pipeline:

| Capability | Method | Business question answered |
|---|---|---|
| **Supervised segmentation** | XGBoost, Random Forest, Logistic Regression | "Which segment does this customer belong to?" |
| **Unsupervised segmentation** | K-Means on RFM features (K=4) | "What natural customer groups exist that we never defined?" |
| **Sales forecasting** | LSTM vs. ARIMA(2,1,2) | "What will monthly sales be, and which model should we trust?" |
| **Explainability** | SHAP over the XGBoost model | "*Why* did the model say that?" |

The supervised and unsupervised tracks are deliberately both present: the classifier
validates the labels the business already uses, while clustering tests whether those
labels match the structure actually in the data.

---

## 3. The data

`BD_Business_Analytics_Dataset.csv` — 32,000 transactions, 44 columns, synthetically
generated (Faker) but modelled on Bangladeshi business conditions:

- **Geography** — all 8 divisions and their districts
- **Seasonality** — Ramadan/Eid, Pohela Boishakh, Rainy Season, Winter
- **Payments** — bKash, Nagad, card, cash-on-delivery
- **Sectors** — Telecom, Electronics, RMG, FMCG, IT services, and others
- **Money** — all amounts in BDT (`*_BDT` columns)

Column families: customer identity and demographics · geography · date/season ·
business profile (type, employees, annual revenue) · product and pricing (quantity,
unit price, discount, net amount, profit margin) · fulfilment (channel, delivery days,
status, returns) · behaviour (purchase frequency, recency, CLV) · marketing
(channel, campaign) · satisfaction score.

Synthetic data is a deliberate choice, not a shortcut: real Bangladeshi transaction
data at this scale is not publicly releasable, and a reproducible thesis needs a
dataset the examiner can regenerate.

---

## 4. Architecture

Seven sequential stages. Each writes artifacts to `output/`; each stage reads only
what the previous ones produced. No hidden state, no notebook execution-order traps.

```
BD_Business_Analytics_Dataset.csv          (32,000 × 44, flat)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ 00  NORMALIZATION → star schema                          │
│     6 dimensions + 1 fact table, then re-joined          │
│     dim_customer · dim_product · dim_date                │
│     dim_business_profile · dim_marketing · dim_logistics │
│     fact_transactions                                    │
└──────────────────────────────────────────────────────────┘
        │  normalized_data/*.csv  +  ..._Merged.csv
        ▼
┌──────────────────────────────────────────────────────────┐
│ 01  PREPROCESSING                                        │
│     nulls → label encoding → feature engineering         │
│     (RFM score, seasonal flags, CLV tier)                │
│     → MinMax scaling → 70/15/15 train/val/test split     │
└──────────────────────────────────────────────────────────┘
        │  data_splits.pkl · scaler.pkl · label_encoders.pkl
        ├────────────────┬─────────────────┬───────────────┐
        ▼                ▼                 ▼               │
┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│ 02 CLASSIFY  │  │ 03 CLUSTER   │  │ 04 FORECAST  │       │
│ XGBoost      │  │ K-Means      │  │ LSTM         │       │
│ RandomForest │  │ elbow K=2-10 │  │   look-back 6│       │
│ LogisticReg  │  │ silhouette   │  │   100 epochs │       │
│              │  │ OPTIMAL_K=4  │  │ vs ARIMA     │       │
│              │  │              │  │   (2,1,2)    │       │
└──────────────┘  └──────────────┘  └──────────────┘       │
        │                │                 │               │
        │ models/*.pkl   │ segments.csv    │ forecast.pkl  │
        ▼                                                  │
┌──────────────┐                                           │
│ 05 SHAP      │  explains the winning XGBoost model       │
└──────────────┘                                           │
        │                                                  │
        └──────────────────┬───────────────────────────────┘
                           ▼
              ┌──────────────────────────┐
              │ 06 FINAL REPORT          │
              │ all metrics + 12 figures │
              │ → thesis Chapter 4       │
              └──────────────────────────┘
```

### Why this design

- **Why normalize into a star schema first (stage 00)?** The raw CSV is a denormalized
  dump with heavy redundancy — a customer's name and division repeat across every one
  of their transactions. Splitting into dimensions and a fact table demonstrates proper
  database design, removes update anomalies, and makes the data model defensible in the
  thesis. It is re-joined immediately afterwards because the ML stages want a wide frame.
- **Why file-based handoff between stages?** Every stage is independently runnable and
  re-runnable. A failed LSTM run does not cost you the preprocessing.
- **Why three classifiers?** Logistic Regression is the interpretable baseline, Random
  Forest the bagging comparator, XGBoost the boosting candidate — a fair comparison
  needs all three families, not just the winner.
- **Why LSTM *and* ARIMA?** ARIMA is the classical statistical baseline the literature
  expects. Claiming deep learning helps requires showing it beats that baseline on the
  same series and the same RMSE.
- **Why SHAP?** It closes the trust gap from §1.3. Feature importance says *which*
  feature matters globally; SHAP says how a feature pushed *this* prediction, which is
  what makes an output actionable.
- **Why `random_state=42` everywhere?** Every number printed in the thesis must
  reproduce exactly when the examiner reruns the pipeline.

---

## 5. Running it

```bash
pip install -r requirements.txt
python run_all.py            # runs stages 00 → 06 in order
```

Or one stage at a time, in order:

```bash
python 00_normalize_dataset.py
python 01_preprocessing.py
python 02_classification.py
python 03_clustering.py
python 04_forecasting.py
python 05_shap_analysis.py
python 06_final_report.py
```

Run from the repository root — all paths are relative. TensorFlow is required only
by stage 04; `tensorflow-cpu` is sufficient.

---

## 6. Outputs

```
normalized_data/     6 dimension tables + fact_transactions.csv
output/
  processed_dataset.csv        cleaned, encoded, engineered
  customer_segments.csv        every customer with its cluster label
  *.pkl                        splits, scaler, encoders, results
  shap_interpretation.txt      plain-language feature insights
  models/                      xgboost · rf · lr · kmeans
  figures/                     12 × 300 DPI PNGs for Chapter 4
```

The twelve figures: monthly sales trend · confusion matrices (XGBoost, RF) · model
comparison bar · XGBoost feature importance · elbow + silhouette · K-Means 2-D
clusters · cluster distribution · RFM cluster heatmap · LSTM vs ARIMA forecast ·
forecast error comparison · SHAP summary.

---

## 7. Findings, in short

- Gradient boosting leads the segmentation task; the tree ensembles clearly separate
  from the linear baseline, which confirms the segment boundaries are non-linear.
- K-Means independently recovers four coherent groups, aligning with the business's
  own four-tier scheme — the labels are not arbitrary.
- Behavioural features dominate the SHAP ranking: purchase frequency, net transaction
  amount, customer lifetime value, and recency outrank demographics. Age and gender
  matter far less than what customers actually do.
- Recency is the sharpest retention signal — inactivity past ~90 days is the strongest
  churn indicator in the data.
- LSTM and ARIMA are compared on identical RMSE/MAE over the same held-out months;
  exact figures are printed by `06_final_report.py`.

**Practical translation:** target retention at customers crossing the 90-day recency
line, concentrate marketing on the high-frequency/high-CLV cluster, and plan inventory
around the forecast rather than last month's sales.

---

## 8. Limitations and future work

- The dataset is synthetic. Distributions are realistic by construction, so absolute
  accuracy figures should be read as evidence the pipeline works, not as field results.
- Forecasting operates on monthly aggregates, which gives the LSTM a short series.
  Daily or weekly aggregation would give deep learning more to work with.
- Next steps: validate on real partner-business data, serve the models behind an API
  with a dashboard, and add per-customer SHAP explanations at prediction time rather
  than only global summaries.
