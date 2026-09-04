# Real data in this project — what exists, what it proves, what it cannot

Several kinds of data live in this repository and they must never be blended
or reported together. This file is the register of what is actually real.

| Tier | Data | Real? | Bangladeshi? | Status |
|---|---|---|---|---|
| 1. Primary | Consenting SME sales records | — | — | **NOT YET COLLECTED** |
| 2. Public secondary (prices) | WFP/DAM market prices (`data/real_public/`) | ✅ Yes | ✅ Yes | ✅ Downloaded, benchmarked |
| 2b. Public secondary (transactions) | UCI Online Retail II | ✅ Yes | ❌ UK | ✅ Trained, real WAPE/ROC-AUC |
| 2c. Public secondary (demand only) | Mendeley BD retailer series | ✅ Yes | ✅ Yes | ✅ Trained, real WAPE |
| 3. Synthetic | `BD_Business_Analytics_Dataset.csv` | ❌ No (Faker) | Modelled on BD | ✅ In use |

## Tier 2 — WFP Bangladesh food prices (real, downloaded)

- **File**: `data/real_public/wfp_food_prices_bgd.csv` (+ `wfp_markets_bgd.csv`)
- **Source**: [WFP Price Database via HDX](https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh),
  compiled from Bangladesh's **Department of Agricultural Marketing (DAM)** and FAO GIEWS
- **License**: CC BY-IGO — attribution is **required**; cite WFP and DAM in the thesis
- **Size**: 33,606 observations · 110 markets · all 8 divisions · 73 commodities · BDT
- **Granularity**: monthly (observations dated to the 15th), `Retail` and `Wholesale`
- **Code**: `ml/market_prices.py`

### A structural quirk you must know

WFP widened its Bangladesh basket in **February 2024**. So the series split in two:

- **Four long series** run back to 2004–2005 and are the only ones long enough
  to train and test a seasonal model: Rice (coarse) 216 months, Wheat flour 212,
  Lentils (masur) 199, Oil (palm) 197.
- **Everything else** (Sugar, soybean oil, potato, chili, garlic, chicken, onion,
  eggs) starts 2024-02 with ~24 months — usable as a market-context feature,
  far too short for a seasonal benchmark. `ml/market_prices.py` enforces this
  split rather than silently mixing them.

### Real-data forecasting benchmark (already run)

`python -m ml.market_prices --all` → `artifacts/real_public/price_forecast_benchmark.json`.
Chronological hold-out, final 12 months as test, no model sees the test window.

| Commodity | Months | Seasonal-naive | Naive (last value) | SARIMA | Gradient boosting | Winner |
|---|---|---|---|---|---|---|
| Rice (coarse) | 216 | 0.1423 | **0.0314** | 0.1616 | 0.2291 | naive |
| Wheat flour | 212 | 0.0866 | 0.0855 | **0.0785** | 0.2388 | SARIMA |
| Lentils (masur) | 199 | 0.1424 | **0.0697** | 0.2199 | 0.0967 | naive |
| Oil (palm) | 197 | 0.0641 | **0.0558** | 0.2331 | 0.2923 | naive |

Metric is WAPE, lower is better (MAE/RMSE/MASE also recorded in the JSON).

**Report this honestly: the naive last-value baseline wins on three of four
commodities, and gradient boosting loses badly on three.** This is a real
result, not a failure to be hidden — Bangladeshi staple prices are close to a
random walk at monthly resolution, so a complex model has little to add. It
independently reproduces the same lesson as the synthetic pipeline's
"seasonal-naive beats LSTM and ARIMA" finding, which makes the thesis's
argument about baseline discipline stronger, not weaker.

### What this data can and cannot support

**Can:**
- The `X_market` market-price term in the problem formulation, using real
  prices — `price_feature_table()` returns a month × commodity table to join
  onto sales. This is what makes the planned "without market-price data"
  ablation an experiment on real inputs.
- A genuine real-data forecasting benchmark on Bangladeshi data (above).
- Real price context for Chapter 1 motivation and Chapter 5 discussion.

**Cannot — do not claim otherwise:**
- ❌ SKU demand forecasting — there are no quantities sold, only prices.
- ❌ Churn, RFM, or segmentation — there are no customers.
- ❌ Inventory/reorder strategy evaluation — there are no stock levels.
- ❌ Anything described as "SME sales data" — these are market price
  observations, not any shop's transactions.

## Tier 2b/2c — Real-data validation study (গবেষণা মোড)

`ml/real_data_validation.py` runs the exact leak-free training code a
B-SMART business's own data uses (`ml/real_pipeline.py`) against two more
real datasets, since — despite an exhaustive second search covering Kaggle,
Mendeley/Data in Brief, IEEE DataPort, UCI, and Bangladeshi platform data
releases — **no public dataset combines Bangladeshi origin, real observed
transactions, and customer-level records.** The closest Bangladeshi
candidate found (Mendeley 10.17632/mgzvngzng2.1, the retail-network dataset
already rejected above) reports algorithmic sales *targets*, not observed
sales, and has no customer field at all.

So two real datasets are used, each for only what it can honestly support:

**Tier 2b — UCI Online Retail II** (`data/real_public/online_retail_II.csv`,
converted once from the source `.xlsx` via streaming `openpyxl` reads —
loading ~1M rows through pandas' default Excel path exhausted memory on this
machine). Real invoice-level transactions, UK gift retailer, Dec 2009–Dec
2011, CC BY 4.0. 805,620 usable lines after dropping 22,956 cancelled/
returned lines, 5,881 customers, 4,631 SKUs. **Not Bangladeshi** — read as a
validation of the modelling method on genuine transaction data, never as a
claim about Bangladeshi buying behaviour. Forecast trained on the top 40
SKUs by volume only (`ml/real_data_validation.py`'s `FORECAST_TOP_SKUS`) —
reindexing the full ~4,600-SKU range to a daily grid is not feasible on this
machine; future-repeat (churn) training uses every customer, no such limit.

Results (real, not fabricated — rerun `python -m ml.real_data_validation`
to reproduce):

| Task | Metric | Model | Baseline |
|---|---|---|---|
| Demand forecast (top-40 SKUs) | WAPE | 1.138 (gradient boosting) | 1.225 (seasonal-naive) |
| Future-repeat / churn | ROC-AUC / PR-AUC / lift@10% | 0.749 / 0.795 / 1.77× (random forest) | — |

**Tier 2c — Bangladeshi retailer demand series**
(`data/real_public/bd_retailer_demand.xlsx`, Mendeley DOI
10.17632/xwmbk7n3c8.1, CC BY 4.0, Khulna University of Engineering and
Technology). Real daily sales for one product, 2013-01-01 to 2017-12-31
(1,826 days). **Genuinely Bangladeshi, genuinely real — but only two
columns exist in the source (date, quantity)**: no customer field, no
price. `ml/external_datasets.load_bd_retailer_demand` fills the remaining
canonical columns with explicit placeholders (`customer_pseudo_id =
"ANONYMOUS"` for every row, `unit_price = 1.0`) so the schema validates —
**never report a revenue or customer number from this dataset**, only
demand/quantity forecasts.

| Task | Metric | Model | Baseline |
|---|---|---|---|
| Demand forecast | WAPE | 0.190 (gradient boosting) | 0.238 (seasonal-naive) |

Served read-only to the frontend via `GET /api/research/real-data-validation`
(`api/routes.py`) — reads the pre-computed
`artifacts/real_public/real_data_validation.json`, never retrains on
request. Shown on গবেষণা মোড's "Real-data validation" page
(`frontend/src/pages/RealDataValidation.jsx`), clearly separated from and
never blended with Model Report's synthetic-pipeline numbers.

## Tier 1 — Consenting SME data (still required)

This is the gap. `docs/REAL_DATA_PROTOCOL.md` specifies 3–5 consenting
Bangladeshi SMEs with invoice-line-level records. **No amount of public data
substitutes for it**, because the thesis's core claims — demand forecasting,
future-churn prediction, and constraint-aware reorder strategy — all need
quantities, customers, and stock, none of which exist in any public
Bangladeshi dataset we could find.

Searched and rejected outright — no customer+date+quantity+price schema at
all (see also `candidate_datasets_not_used/README.md`):

| Candidate | Why rejected |
|---|---|
| [Comprehensive Retail Network Dataset for Bangladesh](https://data.mendeley.com/datasets/mgzvngzng2/1) (719,817 shops, CC BY) | Sales figures are *algorithmic targets, not actual sales*; the paper states it "lacks temporal depth"; no customers. Citable for retail-landscape context only. |
| Daraz scrape (`real-datasets.csv`) | Bangladeshi, but product-catalogue/review data, not transactions. |
| Various Kaggle "retail transaction" listings (India/Pakistan/South Asia) | Either explicitly synthetic/simulation-labelled, or schema unverifiable behind JS-gated pages — high risk of being generated data, not observed. |
| Nielsen POS Kirana-store dataset | Real, but store/brand-level aggregated — no customer ID. |

Two real datasets *did* pass and are now in use, each for only what they can
honestly support — see Tier 2b/2c above: Online Retail II (real
transactions, but UK) and the Mendeley Bangladeshi retailer series (real
Bangladeshi data, but demand-only, no customers).

Use `docs/SME_DATA_COLLECTION_KIT.md` to collect Tier 1 — this is still the
only path to genuine Bangladeshi customer-level evidence. One cooperating
shop with 6+ months of records is enough to start.

## Reproducing the download

```powershell
mkdir data\real_public
curl -sL -o data\real_public\wfp_food_prices_bgd.csv "https://data.humdata.org/dataset/c76eabb7-fdb5-43b7-a5c4-09091bb8acde/resource/966ab7ac-56d6-4dac-8eba-dfe815d59a52/download/wfp_food_prices_bgd.csv"
curl -sL -o data\real_public\wfp_markets_bgd.csv "https://data.humdata.org/dataset/c76eabb7-fdb5-43b7-a5c4-09091bb8acde/resource/60852e15-3e4c-43eb-abf0-650e83c8eb91/download/wfp_markets_bgd.csv"
python -m ml.market_prices --all

# Online Retail II: download the .xlsx from UCI, then convert to CSV once via
# streaming reads (pandas' default openpyxl path exhausts memory on ~1M rows).
# The CSV is gitignored (94 MB); this step must be rerun after a fresh clone.
# Run this as a script (writes the header once, then streams every row):
#
#   import openpyxl, csv
#   wb = openpyxl.load_workbook("online_retail_II.xlsx", read_only=True, data_only=True)
#   with open("data/real_public/online_retail_II.csv", "w", newline="", encoding="utf-8") as f:
#       writer, header_written = csv.writer(f), False
#       for name in wb.sheetnames:
#           rows = wb[name].iter_rows(values_only=True)
#           header = next(rows)
#           if not header_written:
#               writer.writerow(header); header_written = True
#           for row in rows:
#               writer.writerow(row)

# Bangladeshi retailer demand series (Mendeley, small, tracked in git):
curl -sL -o data\real_public\bd_retailer_demand.xlsx "https://data.mendeley.com/public-files/datasets/xwmbk7n3c8/files/4e659dee-1332-4306-b456-b259a499f1dd/file_downloaded"

python -m ml.real_data_validation
```

## Citation to use in the thesis

> World Food Programme. *WFP Food Prices Database — Bangladesh*, compiled from
> the Department of Agricultural Marketing (DAM), Government of Bangladesh, and
> FAO GIEWS. Distributed by the Humanitarian Data Exchange (HDX) under CC BY-IGO.
> Accessed 2026-09-04.
