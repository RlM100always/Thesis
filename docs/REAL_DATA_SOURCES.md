# Real data in this project — what exists, what it proves, what it cannot

Three kinds of data live in this repository and they must never be blended or
reported together. This file is the register of what is actually real.

| Tier | Data | Real? | Bangladeshi? | Status |
|---|---|---|---|---|
| 1. Primary | Consenting SME sales records | — | — | **NOT YET COLLECTED** |
| 2. Public secondary | WFP/DAM market prices (`data/real_public/`) | ✅ Yes | ✅ Yes | ✅ Downloaded, benchmarked |
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

## Tier 1 — Consenting SME data (still required)

This is the gap. `docs/REAL_DATA_PROTOCOL.md` specifies 3–5 consenting
Bangladeshi SMEs with invoice-line-level records. **No amount of public data
substitutes for it**, because the thesis's core claims — demand forecasting,
future-churn prediction, and constraint-aware reorder strategy — all need
quantities, customers, and stock, none of which exist in any public
Bangladeshi dataset we could find.

Searched and rejected (see also `candidate_datasets_not_used/README.md`):

| Candidate | Why rejected |
|---|---|
| [Comprehensive Retail Network Dataset for Bangladesh](https://data.mendeley.com/datasets/mgzvngzng2/1) (719,817 shops, CC BY) | Sales figures are *algorithmic targets, not actual sales*; the paper states it "lacks temporal depth"; no customers. Citable for retail-landscape context only. |
| Online Retail II | Real transactions but a UK retailer in GBP — not Bangladeshi. |
| Daraz scrape (`real-datasets.csv`) | Bangladeshi, but product-catalogue/review data, not transactions. |

Use `docs/SME_DATA_COLLECTION_KIT.md` to collect Tier 1. One cooperating shop
with 6+ months of records is enough to start.

## Reproducing the download

```powershell
mkdir data\real_public
curl -sL -o data\real_public\wfp_food_prices_bgd.csv "https://data.humdata.org/dataset/c76eabb7-fdb5-43b7-a5c4-09091bb8acde/resource/966ab7ac-56d6-4dac-8eba-dfe815d59a52/download/wfp_food_prices_bgd.csv"
curl -sL -o data\real_public\wfp_markets_bgd.csv "https://data.humdata.org/dataset/c76eabb7-fdb5-43b7-a5c4-09091bb8acde/resource/60852e15-3e4c-43eb-abf0-650e83c8eb91/download/wfp_markets_bgd.csv"
python -m ml.market_prices --all
```

## Citation to use in the thesis

> World Food Programme. *WFP Food Prices Database — Bangladesh*, compiled from
> the Department of Agricultural Marketing (DAM), Government of Bangladesh, and
> FAO GIEWS. Distributed by the Humanitarian Data Exchange (HDX) under CC BY-IGO.
> Accessed 2026-09-04.
