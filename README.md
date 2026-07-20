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

Run from the repository root — all paths are relative.

### TensorFlow and the `.venv312` environment

TensorFlow has no build for Python 3.14, which is the system interpreter here. Stage 04
(the only TensorFlow consumer) therefore runs in a separate Python 3.12 virtualenv:

```bash
PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 04_forecasting.py
PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 06_final_report.py
```

`PYTHONIOENCODING=utf-8` is required on Windows — the console defaults to cp1252 and
the scripts print `→` and `✓`, which crashes with `UnicodeEncodeError` otherwise.

Stages 00–03 and 05 run fine on the system Python. To rebuild the venv from scratch:

```bash
py -3.12 -m venv .venv312
./.venv312/Scripts/python.exe -m pip install pandas numpy scipy scikit-learn \
    xgboost statsmodels matplotlib seaborn shap tensorflow-cpu
```

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

The fifteen figures: monthly sales trend · confusion matrices (XGBoost, RF) · model
comparison bar · XGBoost feature importance · elbow + silhouette · K-Means 2-D
clusters · cluster distribution · RFM cluster heatmap · LSTM vs ARIMA forecast ·
forecast error comparison · LSTM training loss · SHAP summary bar · SHAP beeswarm ·
SHAP waterfall.

### What is versioned, and why

`.gitignore` keeps the repo reviewable as *source*, not as data. Everything under
`output/` and `normalized_data/` is regenerable by `run_all.py`, so it is ignored —
`data_splits.pkl` alone is 11 MB and `rf_model.pkl` is 9 MB.

Two exceptions are deliberately **tracked**:

- `BD_Business_Analytics_Dataset.csv` (11 MB) — the source everything derives from.
  Without it nothing reproduces.
- `output/figures/*.png` (~1.2 MB) — cited in Chapter 4, so they are deliverables.

`.claudeignore` is a separate file with a different job: `.gitignore` says "don't
version this", `.claudeignore` says "don't read this". Some files are tracked in git
yet still pointless for an AI assistant to read — the PNGs and the 11 MB CSV are both.

---

## 7. Findings

All figures below are the actual output of `06_final_report.py`.

### 7.1 Classification — test set (4,800 records)

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| **XGBoost** | **94.81%** | 95.08% | 94.81% | 94.81% |
| Random Forest | 92.33% | 93.02% | 92.33% | 92.35% |
| Logistic Regression | 83.58% | 84.53% | 83.58% | 83.50% |

The 11-point gap between XGBoost and the linear baseline is the substantive result:
segment boundaries are genuinely non-linear, so the ensemble is doing real work rather
than reproducing a threshold a simple model could find.

### 7.2 Clustering — K-Means, K=4, 4,996 customers

| Cluster | Customers | Share |
|---|---|---|
| Low-Engagement | 2,691 | 53.9% |
| VIP-Platinum | 1,131 | 22.6% |
| Moderate-Spender | 877 | 17.6% |
| High-Value | 297 | 5.9% |

**Silhouette score: 0.1725.** This is weak — the convention is that >0.5 indicates
well-separated clusters. Reported as-is: the four groups are commercially usable but
they overlap rather than sitting in clean, distinct regions of RFM space. The honest
reading is that customer behaviour here is closer to a continuum than to four natural
kinds, and the four-way split is a business convenience the data tolerates rather
than one it demands.

### 7.3 Forecasting — 6 held-out months

| Metric | LSTM | ARIMA(2,1,2) | Winner |
|---|---|---|---|
| RMSE | 34,388,663 | 43,509,553 | LSTM |
| MAE | 23,746,746 | 28,922,927 | LSTM |
| MAPE | 11.39% | 13.29% | LSTM |

LSTM beats the classical baseline by **21.0% lower RMSE**, on the same series and the
same held-out window. An ~11% MAPE on monthly sales is a plausible, defensible number.

Note that the LSTM figures move slightly between runs (an earlier run gave RMSE
34,128,514 / MAPE 11.31% / 21.6%). Despite `tf.random.set_seed(42)`, TensorFlow's GPU
kernels and EarlyStopping make training non-deterministic — that run stopped at epoch
12, this one at 16. ARIMA is fully deterministic and does not move. **Re-run
`06_final_report.py` and quote the numbers from your final run**; do not mix runs
across chapters.

Caveats worth stating in the defence: the series is only 48 months, which leaves 36
training sequences after the 6-month look-back; EarlyStopping halted training at epoch
12; and the ARIMA fit emitted a maximum-likelihood convergence warning. The comparison
is fair — both models saw identical data — but neither is data-rich.

### 7.4 Explainability

Behavioural features dominate the SHAP ranking: purchase frequency, net transaction
amount, customer lifetime value, and recency all outrank demographics. Age and gender
matter far less than what customers actually do. Recency is the sharpest retention
signal — inactivity past ~90 days is the strongest churn indicator in the data.

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

---
---

# বাংলায় বিস্তারিত — আমরা আসলে কী করেছি, কীভাবে করেছি

এই অংশে পুরো কাজটা ধাপে ধাপে বাংলায় ব্যাখ্যা করা হলো — কোন স্টেপে **কী ইনপুট**
গেছে, **কোন অ্যালগরিদম** চলেছে, আর **কী আউটপুট** বেরিয়েছে।

## ০ক. শিক্ষককে ৫ মিনিটে যা বলবেন

### আমরা আসলে কোন সমস্যা সমাধান করেছি?

বাংলাদেশের ছোট ও মাঝারি ব্যবসাগুলো প্রতিদিন প্রচুর ডেটা তৈরি করে — POS বিক্রি,
bKash/Nagad লেনদেন, ডেলিভারি রেকর্ড, ক্যাম্পেইনের সাড়া। **কিন্তু এই ডেটা থেকে
তারা কোনো সিদ্ধান্ত নেয় না।** ডেটা জমা হয়, পড়ে থাকে।

বাস্তবে তিনটা নির্দিষ্ট ক্ষতি হয়:

**১. সব কাস্টমারকে একরকম ধরা হয়।** যে কাস্টমার বছরে ২০ লাখ টাকার কেনে, আর যে
২ হাজারের — দুজনকেই একই SMS, একই ডিসকাউন্ট পাঠানো হয়। মার্কেটিং বাজেট সমানভাবে
ছড়িয়ে যায়, অথচ লাভের বড় অংশ আসে অল্প কিছু কাস্টমার থেকে।

**২. সামনে কী হবে তার কোনো ধারণা নেই।** আগামী মাসে কত মাল লাগবে, কত কর্মী
লাগবে — গত মাসের অনুমান দিয়ে ঠিক করা হয়। বাংলাদেশে ঋতু-নির্ভরতা তীব্র
(রমজান-ঈদ, পহেলা বৈশাখ, বর্ষা), তাই ভুল অনুমানের খরচ বেশি — হয় স্টক পড়ে
থাকে, নয় বিক্রির সময় মাল শেষ।

**৩. মডেল থাকলেও কেউ বিশ্বাস করে না।** কোনো সফটওয়্যার যদি বলে "এই কাস্টমার
গুরুত্বপূর্ণ" কিন্তু **কেন** বলে না, দোকানের ম্যানেজার সেটা উপেক্ষা করেন।
ব্যাখ্যা ছাড়া ভবিষ্যদ্বাণী কাজে লাগে না।

### গবেষণার দিক থেকে ফাঁকটা কোথায়?

কাস্টমার অ্যানালিটিক্স নিয়ে প্রকাশিত বেশিরভাগ গবেষণা পশ্চিমা বা চীনা
ই-কমার্স ডেটা ব্যবহার করে। সেখানে **পেমেন্ট পদ্ধতি ভিন্ন** (ক্রেডিট কার্ড,
bKash নয়), **উৎসব ভিন্ন** (ক্রিসমাস, ঈদ নয়), **সাপ্তাহিক ছুটি ভিন্ন**
(শনি-রবি, শুক্র-শনি নয়), **ভৌগোলিক গঠন ভিন্ন** (বিভাগ-জেলা নয়)।
এসব মডেল বাংলাদেশে সরাসরি প্রয়োগ করা যায় না।

### তাই আমাদের গবেষণা প্রশ্ন

> **একটাই পুনরুৎপাদনযোগ্য পাইপলাইন দিয়ে কি একসাথে (ক) নির্ভুল কাস্টমার
> সেগমেন্টেশন, (খ) নির্ভরযোগ্য বিক্রয় পূর্বাভাস, এবং (গ) মানুষের বোধগম্য
> ব্যাখ্যা — তিনটাই দেওয়া সম্ভব, বাংলাদেশি ব্যবসার বাস্তবতা প্রতিফলিত করে
> এমন ডেটার উপর?**

### আমাদের উত্তর — চারটা ক্ষমতা, এক পাইপলাইনে

| সমস্যা | আমাদের সমাধান | পদ্ধতি | ফলাফল |
|---|---|---|---|
| কে মূল্যবান কাস্টমার? | সুপারভাইজড শ্রেণিবিন্যাস | XGBoost / RF / LogReg | ৯৪.৮১% (সতর্কতা §৮.৪) |
| ব্যবসার নিজের ভাগটা কি ঠিক? | আনসুপারভাইজড ক্লাস্টারিং | K-Means (RFM) | ৪টা দল, silhouette ০.১৭ |
| সামনের মাসে বিক্রি কত? | সময়-সিরিজ পূর্বাভাস | LSTM বনাম ARIMA | LSTM ২১% ভালো |
| মডেল এটা কেন বলল? | ব্যাখ্যাযোগ্য AI | SHAP | আচরণ > জনতত্ত্ব |

### কেন সুপারভাইজড আর আনসুপারভাইজড — দুটোই?

এটা প্রায়ই জিজ্ঞেস করা হয়। কারণ দুটো **আলাদা প্রশ্নের** উত্তর দেয়:

- **সুপারভাইজড (স্টেপ ২)** ব্যবসা যে চার ভাগ ইতিমধ্যে ব্যবহার করে, সেটা
  শেখে ও নতুন কাস্টমারে প্রয়োগ করে → *"এই নতুন কাস্টমার কোন দলে?"*
- **আনসুপারভাইজড (স্টেপ ৩)** কোনো লেবেল না দেখে ডেটাকে নিজেই দল বানাতে দেয়
  → *"ব্যবসার নিজের ভাগটা আদৌ ডেটার সাথে মেলে কি না?"*

দ্বিতীয়টা প্রথমটাকে **যাচাই** করে। শুধু সুপারভাইজড করলে আমরা কখনো জানতাম না
যে ভাগটা আসলে দুর্বল (silhouette ০.১৭) — সেটা একটা **আবিষ্কার**, ব্যর্থতা নয়।

### সবচেয়ে বড় ব্যবহারিক ফল

SHAP বিশ্লেষণ দেখাচ্ছে **কাস্টমার কে (বয়স, লিঙ্গ) তার চেয়ে কাস্টমার কী করে
(কত ঘন ঘন কেনে, কত টাকার, শেষ কবে কিনেছে) সেটা অনেক বেশি গুরুত্বপূর্ণ।**
বিশেষ করে **৯০ দিনের বেশি নিষ্ক্রিয়তা** সবচেয়ে শক্তিশালী চার্ন সংকেত।

**অর্থাৎ ব্যবসাকে বলা যায়:** বয়স-লিঙ্গ ধরে ক্যাম্পেইন সাজানো বন্ধ করুন;
বরং যারা ৯০ দিনের সীমা পার করছে তাদের ধরুন, উচ্চ-ফ্রিকোয়েন্সি দলে বাজেট
কেন্দ্রীভূত করুন, আর পূর্বাভাস দেখে স্টক সাজান — গত মাসের অনুমানে নয়।

---

## ০. এক নজরে পুরো প্রসেস

```
কাঁচা CSV (৩২,০০০ সারি × ৪৪ কলাম)
      ↓  স্টেপ ০ — নরমালাইজেশন (স্টার স্কিমা)
৬টা dimension টেবিল + ১টা fact টেবিল → আবার জোড়া লাগানো
      ↓  স্টেপ ১ — প্রিপ্রসেসিং (ক্লিন + ফিচার তৈরি + স্কেলিং + স্প্লিট)
৪২টা ফিচার, ট্রেন/ভ্যালিডেশন/টেস্ট ভাগ
      ↓
      ├── স্টেপ ২ — ক্লাসিফিকেশন (XGBoost / Random Forest / Logistic Regression)
      ├── স্টেপ ৩ — ক্লাস্টারিং (K-Means, K=৪)
      ├── স্টেপ ৪ — ফোরকাস্টিং (LSTM বনাম ARIMA)
      └── স্টেপ ৫ — ব্যাখ্যা (SHAP)
      ↓  স্টেপ ৬ — সব রেজাল্ট একসাথে রিপোর্ট
থিসিসের চতুর্থ অধ্যায়ের টেবিল + ১২টা গ্রাফ
```

---

## ১. স্টেপ ০ — ডেটা নরমালাইজেশন (`00_normalize_dataset.py`)

**সমস্যা কী ছিল:** কাঁচা CSV টা পুরোপুরি ফ্ল্যাট। একজন কাস্টমারের নাম, বয়স, বিভাগ —
তার প্রত্যেকটা লেনদেনের সারিতে বারবার লেখা। এতে ডেটা রিডানডেন্সি হয়, আর
আপডেট অ্যানোমালি তৈরি হয় (নাম একজায়গায় বদলালে বাকিগুলো পুরনো থেকে যায়)।

**কী করেছি:** ডেটাবেজ ডিজাইনের নিয়ম মেনে **স্টার স্কিমা**-তে ভাগ করেছি।

| টেবিল | প্রাইমারি কী | কী রাখে |
|---|---|---|
| `dim_customer` | `Customer_ID` | নাম, বয়স, লিঙ্গ, সেগমেন্ট, টাইপ, বিভাগ, জেলা |
| `dim_date` | `Transaction_Date` | বছর, মাস, কোয়ার্টার, সপ্তাহ, বার, সিজন |
| `dim_product` | `Product_ID` (সারোগেট) | প্রোডাক্টের নাম ও ক্যাটাগরি |
| `dim_business_profile` | `Business_ID` (সারোগেট) | ব্যবসার ধরন, কর্মী সংখ্যা, বার্ষিক আয় |
| `dim_marketing` | `Marketing_ID` (সারোগেট) | মার্কেটিং চ্যানেল, ক্যাম্পেইন টাইপ |
| `dim_logistics` | `Logistics_ID` (সারোগেট) | পেমেন্ট মেথড, অর্ডার চ্যানেল, ডেলিভারি স্ট্যাটাস |
| `fact_transactions` | `Transaction_ID` | পরিমাণ, দাম, ডিসকাউন্ট, লাভ + উপরের ৬টার ফরেন কী |

**অ্যালগরিদম:** `drop_duplicates()` দিয়ে ইউনিক রেকর্ড বের করা, তারপর সারোগেট কী
বসিয়ে `merge()` দিয়ে ফরেন কী ম্যাপিং।

**ইনপুট:** `BD_Business_Analytics_Dataset.csv`
**আউটপুট:** `normalized_data/`-এ ৭টা CSV + `output/BD_Business_Analytics_Dataset_Merged.csv`

**কেন আবার জোড়া লাগালাম:** ML মডেল একটা চওড়া (wide) টেবিল চায়, আলাদা টেবিল না।
তাই নরমালাইজেশনটা ডেটাবেজ ডিজাইন দেখানোর জন্য, আর জোড়া লাগানোটা ML-এর জন্য।

---

## ২. স্টেপ ১ — প্রিপ্রসেসিং (`01_preprocessing.py`)

### (ক) মিসিং ভ্যালু হ্যান্ডলিং
`Return_Reason` কলামটা ফাঁকা থাকে যেসব পণ্য ফেরত আসেনি তাদের জন্য — এটা ভুল না,
ডিজাইনেই এমন। তাই ফাঁকা জায়গায় `"No Return"` বসিয়েছি।

### (খ) ফিচার ইঞ্জিনিয়ারিং — নতুন কলাম বানানো

এটাই এই স্টেপের সবচেয়ে গুরুত্বপূর্ণ কাজ। কাঁচা কলাম থেকে **অর্থবহ** ফিচার বানানো:

1. **RFM Score** — মার্কেটিংয়ের ক্লাসিক পদ্ধতি। `pd.qcut()` দিয়ে প্রত্যেকটাকে ৪টা
   কোয়ার্টাইলে ভাগ করে ১–৪ স্কোর দিয়েছি:
   - `Recency_Score` — শেষ কেনাকাটার পর কত দিন গেছে (কম দিন = বেশি স্কোর, তাই লেবেল উল্টো `[4,3,2,1]`)
   - `Frequency_Score` — মাসে কতবার কেনে (বেশি = বেশি স্কোর)
   - `Monetary_Score` — কত টাকার কেনে (বেশি = বেশি স্কোর)
   - `RFM_Score` = তিনটার যোগফল (৩ থেকে ১২ পর্যন্ত)
2. **CLV_Tier** — লাইফটাইম ভ্যালুকে ৪ ভাগে: Bronze / Silver / Gold / Platinum
3. **সিজনাল ফ্ল্যাগ** — `Is_Eid_Season`, `Is_Ramadan`, `Is_Pohela_Boishakh`,
   `Is_YearEnd_Sale` (০ বা ১) — বাংলাদেশের উৎসবভিত্তিক বিক্রি ধরার জন্য
4. **`Is_Weekend`** — শুক্র/শনিবার = ১ (বাংলাদেশের সাপ্তাহিক ছুটি অনুযায়ী, পশ্চিমা শনি/রবি না)
5. **`Revenue_Per_Employee`** = বার্ষিক আয় ÷ কর্মী সংখ্যা (ব্যবসার দক্ষতার মাপ)
6. **`High_Discount_Flag`** — ডিসকাউন্ট ২০%-এর বেশি হলে ১
7. **`Net_Profit_Ratio`** = লাভ ÷ নিট বিক্রয়

### (গ) টার্গেট ভ্যারিয়েবল (যা প্রেডিক্ট করব)
```
Segment_Label:  Low-Engagement=0, Moderate-Spender=1, High-Value=2, VIP-Platinum=3
Return_Binary:  পণ্য ফেরত এসেছে কি না (০/১)
```

### (ঘ) ক্যাটাগরিক্যাল এনকোডিং
**অ্যালগরিদম: Label Encoding** (`sklearn.LabelEncoder`) — ১৪টা কলামে
(Business_Category, Payment_Method, Division, Season ইত্যাদি)। লেখা → সংখ্যা,
কারণ ML মডেল লেখা বোঝে না। এনকোডারগুলো `label_encoders.pkl`-এ সেভ করা, যাতে
পরে নতুন ডেটাতেও একই ম্যাপিং লাগানো যায়।

### (ঙ) নরমালাইজেশন
**অ্যালগরিদম: MinMaxScaler** — সব সংখ্যাকে ০ থেকে ১-এর মধ্যে আনা।
**কেন দরকার:** `Annual_Revenue_BDT` লাখ-কোটির ঘরে, আর `Customer_Age` ২০–৬০-এর ঘরে।
স্কেল না করলে মডেল বড় সংখ্যার কলামকে বেশি গুরুত্ব দিয়ে ফেলে।

### (চ) ডেটা ভাগ
৭০% ট্রেন / ১৫% ভ্যালিডেশন / ১৫% টেস্ট, **stratified split** —
অর্থাৎ প্রতিটা ভাগে চার সেগমেন্টের অনুপাত একই থাকে।

**ইনপুট:** merged CSV
**আউটপুট:** `data_splits.pkl`, `scaler.pkl`, `label_encoders.pkl`, `processed_dataset.csv`
**মোট ফিচার:** ২৮টা সংখ্যাগত + ১৪টা এনকোডেড = **৪২টা**

---

## ৩. স্টেপ ২ — ক্লাসিফিকেশন (`02_classification.py`)

**কাজ:** একজন কাস্টমার কোন সেগমেন্টে পড়বে সেটা প্রেডিক্ট করা (৪ ক্লাস)।

তিনটা আলাদা ধরনের অ্যালগরিদম ব্যবহার করেছি — তুলনাটা যেন ন্যায্য হয়:

| মডেল | ধরন | প্যারামিটার | কেন এটা |
|---|---|---|---|
| **XGBoost** | Boosting | `n_estimators=300`, `max_depth=6`, `learning_rate=0.1`, `subsample=0.8` | মূল প্রস্তাবিত মডেল — ভুল থেকে ধাপে ধাপে শেখে |
| **Random Forest** | Bagging | `n_estimators=200`, `max_depth=10`, `min_samples_split=5` | অনেক গাছের ভোট — তুলনার জন্য |
| **Logistic Regression** | Linear | `max_iter` ডিফল্ট | সহজ বেসলাইন — এর চেয়ে ভালো না হলে জটিল মডেল অর্থহীন |

**কীভাবে ট্রেন হয়:** ট্রেন + ভ্যালিডেশন একসাথে জুড়ে (`np.vstack`) ফাইনাল মডেল
ট্রেন হয়, আর টেস্ট সেট পুরোপুরি আলাদা রাখা হয় — যাতে মডেল আগে কখনো দেখেনি এমন
ডেটাতে পারফরম্যান্স মাপা যায়।

**মূল্যায়নের মেট্রিক:**
- **Accuracy** — মোট কতটা ঠিক
- **Precision** (weighted) — যাকে VIP বলেছি, সে আসলেই VIP কি না
- **Recall** (weighted) — আসল VIP-দের কতজনকে ধরতে পেরেছি
- **F1-Score** — উপরের দুটোর ভারসাম্য
- **Confusion Matrix** — কোন ক্লাসের সাথে কোনটা গুলিয়ে ফেলছে

**আউটপুট:** `models/xgboost_model.pkl`, `rf_model.pkl`, `lr_model.pkl`,
`classification_results.pkl` + কনফিউশন ম্যাট্রিক্স ও তুলনার গ্রাফ

---

## ৪. স্টেপ ৩ — K-Means ক্লাস্টারিং (`03_clustering.py`)

**পার্থক্যটা বুঝুন:** স্টেপ ২ ছিল **সুপারভাইজড** — ব্যবসা যে লেবেল দিয়ে রেখেছে সেটা
শেখানো। স্টেপ ৩ **আনসুপারভাইজড** — কোনো লেবেল না দেখিয়ে ডেটাকে নিজেই দল বানাতে দেওয়া।
এতে যাচাই হয় ব্যবসার নিজের ভাগটা আসলেই ডেটার স্বাভাবিক গঠনের সাথে মেলে কি না।

**ধাপ:**

1. **কাস্টমার-লেভেল অ্যাগ্রিগেশন** — `groupby("Customer_ID")` করে প্রতি কাস্টমারের
   একটা করে সারি বানানো:
   - `Recency` = দিনের সর্বনিম্ন (`min`)
   - `Frequency` = গড় মাসিক কেনাকাটা (`mean`)
   - `Monetary` = মোট খরচ (`sum`)
   - সাথে `CLV`, গড় সন্তুষ্টি স্কোর, লেনদেন সংখ্যা, গড় ডিসকাউন্ট, রিটার্ন রেট
2. **StandardScaler** — এখানে MinMax না, StandardScaler (গড়=০, SD=১)।
   **কেন:** K-Means দূরত্ব (Euclidean distance) দিয়ে কাজ করে, তাই প্রতিটা ফিচার
   একই স্কেলে না থাকলে বড় স্কেলের ফিচার ক্লাস্টার নিয়ন্ত্রণ করে ফেলে।
3. **অপটিমাল K বের করা** — K = ২ থেকে ১০ পর্যন্ত চালিয়ে দুটো জিনিস মাপা:
   - **Elbow Method** — Inertia (WCSS, ক্লাস্টারের ভেতরের বর্গ দূরত্বের যোগফল)
     যেখানে হঠাৎ কমা থামে, সেই "কনুই" পয়েন্ট
   - **Silhouette Score** — ক্লাস্টারগুলো কতটা আলাদা ও ঘন (−১ থেকে +১, বেশি = ভালো)
   - দুটো মিলিয়ে **K = ৪** বেছে নেওয়া হয়েছে
4. **ফাইনাল K-Means** (`n_init=15`, `random_state=42`) চালিয়ে ক্লাস্টার লেবেল বসানো
5. **ক্লাস্টারের নামকরণ** — প্রতিটা ক্লাস্টারের গড় `Monetary` র‍্যাঙ্ক করে
   নাম দেওয়া: সবচেয়ে বেশি → VIP-Platinum, তারপর High-Value, Moderate-Spender,
   Low-Engagement

**আউটপুট:** `customer_segments.csv` (প্রতি কাস্টমারের ক্লাস্টার),
`models/kmeans_model.pkl`, এলবো/সিলুয়েট গ্রাফ, ২-D ক্লাস্টার প্লট, RFM হিটম্যাপ

---

## ৫. স্টেপ ৪ — বিক্রয় পূর্বাভাস: LSTM বনাম ARIMA (`04_forecasting.py`)

**কাজ:** আগামী মাসগুলোর মোট বিক্রি কত হবে সেটা অনুমান করা।

### ডেটা প্রস্তুতি
লেনদেনগুলোকে মাস ধরে যোগ করে একটা **টাইম সিরিজ** বানানো:
`groupby("Year_Month")` → প্রতি মাসের মোট নিট বিক্রি (২০২১–২০২৪)।

### মডেল ১ — LSTM (ডিপ লার্নিং)
- **Sliding window পদ্ধতি:** আগের **৬ মাসের** বিক্রি দেখে পরের ১ মাস অনুমান
  (`LOOK_BACK = 6`)। অর্থাৎ [জানু–জুন] → জুলাই, [ফেব্রু–জুলাই] → আগস্ট, এভাবে।
- **নেটওয়ার্ক গঠন:**
  ```
  LSTM(64 ইউনিট, সিকোয়েন্স ফেরত দেয়)
    → Dropout(0.2)          ← ওভারফিটিং ঠেকাতে
  LSTM(32 ইউনিট)
    → Dropout(0.2)
  Dense(16, ReLU)
  Dense(1)                  ← চূড়ান্ত সংখ্যা: পরের মাসের বিক্রি
  ```
- **অপ্টিমাইজার:** Adam, **লস:** MSE, **epochs:** সর্বোচ্চ ১০০,
  **batch_size:** ৪, **EarlyStopping** (patience=10) — ভ্যালিডেশন লস ১০ epoch
  ধরে না কমলে থেমে যায় এবং সেরা ওজন ফিরিয়ে আনে
- শেষ **৬ মাস** টেস্টের জন্য সরিয়ে রাখা

### মডেল ২ — ARIMA(2,1,2) (পরিসংখ্যানভিত্তিক বেসলাইন)
- **p=2** — আগের ২টা মানের উপর নির্ভরতা (AutoRegressive)
- **d=1** — একবার ডিফারেন্সিং, সিরিজটাকে stationary করার জন্য
- **q=2** — আগের ২টা ভুলের উপর নির্ভরতা (Moving Average)
- **কেন রাখলাম:** এটা প্রচলিত পদ্ধতি। LSTM ভালো — এই দাবি করতে হলে
  প্রচলিত পদ্ধতিকে হারিয়ে দেখাতে হবে।

### তুলনার মেট্রিক
- **RMSE** = √(গড় বর্গ ভুল) — বড় ভুলকে বেশি শাস্তি দেয়
- **MAE** = গড় পরম ভুল — সহজ ব্যাখ্যা, টাকার এককেই
- **MAPE** = গড় শতকরা ভুল — শতাংশে, তাই তুলনা করা সহজ

**আউটপুট:** `forecast_results.pkl`, মাসিক ট্রেন্ড গ্রাফ, LSTM বনাম ARIMA
পূর্বাভাস গ্রাফ, ভুলের তুলনার চার্ট

> ⚠️ **এই স্টেপ নিয়ে জরুরি সতর্কতা — নিচের "সাবধানতা" অংশটা অবশ্যই পড়ুন।**

---

## ৬. স্টেপ ৫ — SHAP ব্যাখ্যা (`05_shap_analysis.py`)

**সমস্যা:** XGBoost ভালো প্রেডিক্ট করে, কিন্তু "কেন" বলে না। একজন ব্যবসায়ী
"এই কাস্টমার High-Value" শুনে কিছুই করতে পারে না, যতক্ষণ না জানে কীসের ভিত্তিতে।

**সমাধান — SHAP (SHapley Additive exPlanations):** গেম থিওরির শ্যাপলি ভ্যালু
থেকে আসা। মূল ধারণা: প্রতিটা ফিচারকে একটা "খেলোয়াড়" ধরে হিসাব করা হয় —
সে প্রেডিকশনটাকে কতটুকু উপরে বা নিচে ঠেলেছে।

**কীভাবে চালানো হয়:**
- `shap.TreeExplainer` — গাছভিত্তিক মডেলের জন্য বিশেষ দ্রুত অ্যালগরিদম
- গতির জন্য টেস্ট সেট থেকে **৫০০টা** নমুনা নেওয়া হয় (`np.random.seed(42)`)
- মাল্টিক্লাস বলে SHAP ভ্যালু আসে ৩-মাত্রিক আকারে (নমুনা × ফিচার × ক্লাস);
  গ্লোবাল গুরুত্বের জন্য ক্লাসগুলোর উপর গড় করা হয়, আর বিস্তারিত প্লটে
  **ক্লাস ২ (High-Value)** দেখানো হয়

**দুই ধরনের ব্যাখ্যা:**
- **গ্লোবাল** — গড়ে কোন ফিচার সবচেয়ে গুরুত্বপূর্ণ (বার চার্ট)
- **লোকাল/বিস্তারিত** — beeswarm প্লট: ফিচারের মান বেশি না কম, সেটা প্রেডিকশনকে
  কোন দিকে ঠেলছে

**ফলাফলের সারমর্ম:** আচরণভিত্তিক ফিচার (কেনার হার, লেনদেনের অঙ্ক, CLV, রিসেন্সি)
জনসংখ্যাতাত্ত্বিক ফিচারকে (বয়স, লিঙ্গ) অনেক পেছনে ফেলে দিয়েছে।
অর্থাৎ **কাস্টমার কে**, তার চেয়ে **কাস্টমার কী করে** সেটাই বেশি গুরুত্বপূর্ণ।

**আউটপুট:** `shap_interpretation.txt` (সহজ ভাষায় ব্যাখ্যা), SHAP সামারি চার্ট

---

## ৭. স্টেপ ৬ — চূড়ান্ত রিপোর্ট (`06_final_report.py`)

সব `.pkl` ফাইল পড়ে থিসিসের চতুর্থ অধ্যায়ের জন্য গোছানো টেবিল প্রিন্ট করে —
ক্লাসিফিকেশনের তুলনা, ক্লাস্টারের প্রোফাইল, ফোরকাস্টের RMSE/MAE/MAPE।
কোনো ফাইল লেখে না, শুধু টার্মিনালে দেখায়।

---

## ৮. চূড়ান্ত ফলাফল (আসল মডেল থেকে)

### ৮.১ ক্লাসিফিকেশন — টেস্ট সেট (৪,৮০০ রেকর্ড)

| মডেল | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| **XGBoost** | **৯৪.৮১%** | ৯৫.০৮% | ৯৪.৮১% | ৯৪.৮১% |
| Random Forest | ৯২.৩৩% | ৯৩.০২% | ৯২.৩৩% | ৯২.৩৫% |
| Logistic Regression | ৮৩.৫৮% | ৮৪.৫৩% | ৮৩.৫৮% | ৮৩.৫০% |

XGBoost আর Logistic Regression-এর মধ্যে **১১ পয়েন্টের ব্যবধানটাই আসল ফলাফল** —
এতে প্রমাণ হয় সেগমেন্টের সীমারেখা সরলরৈখিক নয়, তাই জটিল মডেল ব্যবহার করা যুক্তিসঙ্গত।

### ৮.২ ক্লাস্টারিং — K=৪, ৪,৯৯৬ জন কাস্টমার

| ক্লাস্টার | কাস্টমার | শতকরা |
|---|---|---|
| Low-Engagement | ২,৬৯১ | ৫৩.৯% |
| VIP-Platinum | ১,১৩১ | ২২.৬% |
| Moderate-Spender | ৮৭৭ | ১৭.৬% |
| High-Value | ২৯৭ | ৫.৯% |

**Silhouette Score: ০.১৭২৫** — এটা দুর্বল (সাধারণত ০.৫-এর বেশি হলে ভালো ধরা হয়)।
সৎভাবে বললে: ক্লাস্টারগুলো ব্যবসায়িকভাবে কাজে লাগানোর মতো, কিন্তু ওদের মধ্যে
যথেষ্ট ওভারল্যাপ আছে। অর্থাৎ কাস্টমারদের আচরণ চারটা আলাদা দলে ভাগ হওয়ার চেয়ে
একটা ধারাবাহিক বিস্তারের (continuum) বেশি কাছাকাছি। **ডিফেন্সে এই প্রশ্ন আসতে
পারে — লুকানোর চেষ্টা না করে এটাই বলবেন।**

### ৮.৩ ফোরকাস্টিং — শেষ ৬ মাস

| মেট্রিক | LSTM | ARIMA(2,1,2) | বিজয়ী |
|---|---|---|---|
| RMSE | ৩,৪৩,৮৮,৬৬৩ | ৪,৩৫,০৯,৫৫৩ | LSTM |
| MAE | ২,৩৭,৪৬,৭৪৬ | ২,৮৯,২২,৯২৭ | LSTM |
| MAPE | ১১.৩৯% | ১৩.২৯% | LSTM |

LSTM প্রচলিত ARIMA-কে **২১.০% কম RMSE** দিয়ে হারিয়েছে — একই সিরিজে, একই
টেস্ট মাসগুলোতে। ১১% MAPE মাসিক বিক্রয় পূর্বাভাসের জন্য বাস্তবসম্মত সংখ্যা।

> **সতর্কতা:** LSTM-এর সংখ্যা প্রতি রানে সামান্য বদলায় (আগের রানে ছিল RMSE
> ৩,৪১,২৮,৫১৪ / MAPE ১১.৩১% / ২১.৬%)। `tf.random.set_seed(42)` থাকা সত্ত্বেও
> EarlyStopping কখন থামে তার উপর নির্ভর করে ফল বদলায় — আগের রানে ১২তম epoch,
> এবারে ১৬তম। ARIMA পুরোপুরি স্থির, বদলায় না।
> **থিসিসে লেখার আগে শেষবার `run_all.py` চালিয়ে সেই রানের সংখ্যাগুলোই সব
> অধ্যায়ে ব্যবহার করবেন** — এক অধ্যায়ে এক রানের, আরেক অধ্যায়ে আরেক রানের
> সংখ্যা দিলে পরীক্ষক অসঙ্গতি ধরে ফেলবেন।

**ডিফেন্সে যা স্বীকার করে নেবেন:** সিরিজটা মাত্র ৪৮ মাসের, ৬ মাসের look-back
বাদ দিলে ট্রেনিং সিকোয়েন্স থাকে ৩৬টা; EarlyStopping ১২তম epoch-এ ট্রেনিং
থামিয়ে দিয়েছে; আর ARIMA ফিট করার সময় convergence warning এসেছে। তুলনাটা
ন্যায্য (দুই মডেল একই ডেটা দেখেছে), কিন্তু ডেটার পরিমাণ কম।

---

## ৮.৪ ⚠️ যে তিনটা প্রশ্ন পরীক্ষক করবেনই — উত্তর তৈরি রাখুন

এই তিনটা দুর্বলতা ডেটা ও ফলাফল বিশ্লেষণ করে বের করা হয়েছে। **লুকানোর চেষ্টা
করবেন না** — পরীক্ষক ধরলে অপ্রস্তুত হবেন, কিন্তু নিজে থেকে বললে বরং বোঝা যাবে
আপনি নিজের কাজ বুঝেছেন। থিসিসের "Limitations" অংশে এগুলো লিখুন।

### প্রশ্ন ১: "৯৪.৮১% অ্যাকুরেসি এত বেশি কেন? সন্দেহজনক নয়?"

**এটাই সবচেয়ে গুরুত্বপূর্ণ প্রশ্ন।** ডেটা পরীক্ষা করে দেখা গেছে
`Customer_Lifetime_Value_BDT` আর `Customer_Segment` প্রায় একই জিনিস:

| সেগমেন্ট | CLV সর্বনিম্ন | CLV সর্বোচ্চ |
|---|---|---|
| Low-Engagement | ১,০১১ | ১৯,৯৮৬ |
| Moderate-Spender | ১০,০৩৬ | ৭৯,৯৯৫ |
| High-Value | ৫০,২১২ | ৪,৯৯,০২৪ |
| VIP-Platinum | ২,১১,৮২৪ | ১৯,৯৯,৯৫৫ |

সীমারেখাগুলো প্রায় আলাদা আলাদা ব্যান্ডে বসে আছে। **যাচাই করে দেখা হয়েছে:
শুধুমাত্র CLV দিয়ে একটা depth-3 ডিসিশন ট্রি ৯১.০৬% অ্যাকুরেসি পায়** — যেখানে
XGBoost ৪২টা ফিচার নিয়ে পায় ৯৪.৮১%।

**এর মানে কী:** সিন্থেটিক ডেটা বানানোর সময় CLV-এর রেঞ্জ দেখেই সেগমেন্টের লেবেল
বসানো হয়েছিল। তাই মডেল নতুন কিছু শিখছে না — বরং যে নিয়মে লেবেল তৈরি হয়েছিল,
সেই নিয়মটাই আবিষ্কার করছে। একে বলে **target leakage**।

**যেভাবে উত্তর দেবেন:** "৯৪.৮১% সংখ্যাটা মডেলের কৃতিত্ব নয়, ডেটা তৈরির
পদ্ধতির ফল। আমরা যাচাই করে দেখেছি একা CLV-ই ৯১% দেয়। **আসল ফলাফল হলো
৪২টা ফিচার মিলে বাড়তি ৩.৭৫ পয়েন্ট আনতে পেরেছে, আর Logistic Regression-এর
৮৩.৫৮% থেকে ১১ পয়েন্টের ব্যবধান** — যা প্রমাণ করে সম্পর্কটা সরলরৈখিক নয়।"

**যদি সময় থাকে ঠিক করার:** `01_preprocessing.py`-এর `NUMERIC_FEATURES` থেকে
`Customer_Lifetime_Value_BDT` আর `CLV_Tier_Enc` বাদ দিয়ে আবার চালান।
অ্যাকুরেসি কমবে (সম্ভবত ৭০–৮০%), কিন্তু সেটাই **সৎ ও অনেক বেশি অর্থবহ** ফল —
কারণ তখন মডেল আচরণ থেকে সত্যিই শিখছে, লেবেলের সূত্র মুখস্থ করছে না।

### প্রশ্ন ২: "K=4 কেন? Silhouette তো K=2-তে বেশি!"

এলবো রানের আসল সংখ্যা:

| K | Silhouette |
|---|---|
| **২** | **০.২৮৩৭** ← সর্বোচ্চ |
| ৩ | ০.১৫৬৫ |
| ৪ | ০.১৭২৫ |
| ৫+ | ক্রমশ কমতে থাকে |

অর্থাৎ **Silhouette স্কোর অনুযায়ী K=2 সবচেয়ে ভালো, K=4 নয়।** কোডে
`OPTIMAL_K = 4` হাতে লিখে বসানো আছে ([03_clustering.py:119](03_clustering.py#L119)),
ডেটা থেকে বেছে নেওয়া হয়নি।

**যেভাবে উত্তর দেবেন:** "গাণিতিকভাবে K=2 ভালো স্কোর দেয়, কিন্তু ব্যবসায়িকভাবে
দুই ভাগ (ভালো/খারাপ কাস্টমার) কাজে লাগে না — মার্কেটিং টিমের চার স্তরের কৌশল
দরকার। তাই আমরা **ব্যবসায়িক প্রয়োজনে K=4 বেছেছি, পরিসংখ্যানগত সর্বোচ্চ স্কোরে
নয়** — এবং এই ট্রেড-অফটা আমরা সচেতনভাবে করেছি।" এটা বৈধ যুক্তি, কিন্তু
**সচেতন সিদ্ধান্ত হিসেবে বলতে হবে**, দুর্ঘটনা হিসেবে নয়।

### প্রশ্ন ৩: "Silhouette ০.১৭ মানে তো ক্লাস্টার ভালো হয়নি?"

ঠিক। ০.৫-এর উপরে হলে ভালো ধরা হয়। ০.১৭ মানে ক্লাস্টারগুলো যথেষ্ট ওভারল্যাপ করছে।

**যেভাবে উত্তর দেবেন:** "কাস্টমারের আচরণ চারটা আলাদা প্রকারে ভাগ হয় না, বরং
একটা ধারাবাহিক বিস্তার (continuum)। আমাদের চার ভাগ ডেটার প্রাকৃতিক গঠন নয়,
বরং ব্যবসায়িক সুবিধার জন্য কাটা সীমারেখা — ডেটা সেটা সহ্য করে, কিন্তু দাবি করে না।"

### আরেকটা ছোট সমস্যা: মিসিং ভ্যালু

স্টেপ ১-এর আউটপুট বলছে:
```
⚠ Marketing_Channel: 1216 missing (3.8%)
⚠ Campaign_Type: 9684 missing (30.26%)
✓ No other critical missing values found
```

কিন্তু কোড শুধু `Return_Reason` ঠিক করে — বাকি দুটো **হ্যান্ডল করা হয়নি**,
অথচ বার্তাটা বলছে সমস্যা নেই। `LabelEncoder`-এ `.astype(str)` থাকায় ফাঁকা
মানগুলো `"nan"` নামের একটা আলাদা ক্যাটাগরি হয়ে গেছে। **এটা crash করেনি, কিন্তু
`Campaign_Type`-এর ৩০% ডেটা একটা অর্থহীন ক্যাটাগরিতে ঢুকেছে।**
ঠিক করতে হলে `Return_Reason`-এর মতোই `"No Campaign"` / `"Unknown"` দিয়ে
`fillna()` করুন।

---

## ৯. কোন ফাইল git-এ রাখব, কোনটা রাখব না

`.gitignore` ফাইলটার মূল নীতি: **যা `run_all.py` দিয়ে আবার বানানো যায়, তা git-এ
রাখার দরকার নেই।** রিপোজিটরিতে থাকবে কোড, ডেটা নয়।

**যা ignore করা হয়েছে:**

| কী | কেন |
|---|---|
| `.venv312/` | ~২ GB। README §৫-এর কমান্ড দিয়ে যেকোনো সময় আবার বানানো যায় |
| `normalized_data/` | স্টেপ ০ আবার চালালেই তৈরি হয় (~১২ MB) |
| `output/*.pkl` | `data_splits.pkl` একাই ১১ MB |
| `output/models/` | `rf_model.pkl` একাই ৯ MB |
| `output/*.csv` | `processed_dataset.csv` ১৫ MB |
| `forecast_results_SIMULATED_backup.pkl` | নকল ফল — ভুল করেও যেন কেউ ব্যবহার না করে |
| `__pycache__/`, `.vscode/`, `~$*.docx` | কাজের কোনো জিনিস না |

**যা ইচ্ছাকৃতভাবে git-এ রাখা হয়েছে:**

- `BD_Business_Analytics_Dataset.csv` (১১ MB) — **মূল ডেটাসেট**। বাকি সবকিছু এটা
  থেকে তৈরি, তাই এটা না থাকলে কিছুই পুনরুৎপাদন করা যাবে না।
- `output/figures/*.png` (~১.২ MB) — থিসিসের চতুর্থ অধ্যায়ে এই গ্রাফগুলোই বসবে,
  তাই এগুলো ফেলে দেওয়ার জিনিস নয়, ডেলিভারেবল।

### `.gitignore` আর `.claudeignore` — পার্থক্যটা কী?

দুটো আলাদা কাজ করে, তাই দুটো আলাদা ফাইল:

- **`.gitignore`** বলে — *"এটা ভার্সন কন্ট্রোলে রেখো না"*
- **`.claudeignore`** বলে — *"এটা পড়ার চেষ্টা কোরো না"*

কিছু ফাইল git-এ রাখা আছে কিন্তু AI-এর পড়ার কোনো দরকার নেই — যেমন PNG গ্রাফগুলো
(ছবি, টেক্সট হিসেবে পড়া অর্থহীন) আর ১১ MB-র মূল CSV (৩২,০০০ সারি পড়ে কোনো লাভ
নেই, স্কিমাটা README §৩-এ লেখাই আছে)। এগুলো `.claudeignore`-এ আছে কিন্তু
`.gitignore`-এ নেই। এতে টোকেন খরচ অনেক কমে।

উল্টোটাও আছে: `output/shap_interpretation.txt` ফাইলটা `.claudeignore`-এ **রাখা
হয়নি** — কারণ ছোট, সাধারণ টেক্সট, আর মডেলের ফলাফল সহজ ভাষায় ব্যাখ্যা করে।

---

## ১০. যে সমস্যাটা ধরা পড়েছিল ও সমাধান করা হয়েছে

**সমস্যা:** `04_forecasting.py`-এ একটা fallback কোড আছে — TensorFlow বা
statsmodels ইনস্টল না থাকলে সে আসল মডেল ট্রেন না করে **আসল মানের আশেপাশে
র‍্যান্ডম নয়েজ** বসিয়ে নকল পূর্বাভাস বানায় (LSTM-এ ৫%, ARIMA-তে ১৮% নয়েজ)।
আগের রানে সেই পথেই চলেছিল — MAPE এসেছিল LSTM ০.৭৪%, ARIMA ১.৬০%, যা বাস্তব
পূর্বাভাসে অসম্ভব রকম নিখুঁত।

**সমাধান যা করা হয়েছে:**

সিস্টেমে শুধু Python 3.14 ছিল, আর TensorFlow-এর 3.14 বিল্ড এখনো বের হয়নি।
তাই আলাদা করে **Python 3.12 ইনস্টল করে `.venv312` নামে একটা venv** বানানো হয়েছে,
সেখানে TensorFlow 2.21 সহ সব ডিপেন্ডেন্সি ইনস্টল করে স্টেপ ৪ ও ৬ আবার চালানো হয়েছে।

**আসল মডেল চলেছে তার প্রমাণ:**
- `output/models/lstm_model.h5` তৈরি হয়েছে (৩৯২ KB, ২৯,৮৫৭ প্যারামিটার)
- `output/figures/lstm_training_loss.png` তৈরি হয়েছে
- ARIMA লগে `AIC: 1293.70` এসেছে (আসল ফিটের চিহ্ন)
- MAPE এখন ১১.৩১% / ১৩.২৯% — বাস্তবসম্মত

পুরনো নকল ফলটা `output/forecast_results_SIMULATED_backup.pkl`-এ রাখা আছে
(তুলনার জন্য; থিসিসে ব্যবহার করবেন না)।

### venv দিয়ে চালানোর নিয়ম

```bash
# ফোরকাস্টিং অবশ্যই venv দিয়ে চালাবেন (TensorFlow শুধু ওখানেই আছে)
PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 04_forecasting.py
PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 06_final_report.py
```

`PYTHONIOENCODING=utf-8` লাগে কারণ Windows কনসোল ডিফল্টে cp1252 এনকোডিং ব্যবহার
করে, আর স্ক্রিপ্টগুলোতে `→`, `✓` এর মতো ইউনিকোড অক্ষর প্রিন্ট হয় — না দিলে
`UnicodeEncodeError` দিয়ে ক্র্যাশ করবে।

### ⚠️ এখনো যা করা বাকি

`04_forecasting.py`-এর fallback ব্লকটা (`else:` শাখায় `np.random.normal(...)`
দিয়ে নকল প্রেডিকশন) কোডে **এখনো রয়ে গেছে**। ভবিষ্যতে কেউ ভুল করে TensorFlow
ছাড়া চালালে আবার নকল ফল তৈরি হবে, এবং সেটা দেখে বোঝার উপায় থাকবে না।
ডিফেন্সে জমা দেওয়ার আগে ওই ব্লকটা মুছে ফেলে সরাসরি এরর দেওয়াই নিরাপদ —
তাহলে মডেল না চললে চুপচাপ ভুল সংখ্যা না এসে পরিষ্কার এরর আসবে।

