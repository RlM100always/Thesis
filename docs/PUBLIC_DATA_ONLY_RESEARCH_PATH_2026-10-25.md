# B-SMART — Internet-Only Research Path (25 October 2026)

## Constraint from thesis team
**No primary business data collection and no owner/staff interviews, surveys or usability sessions.** Only legally accessible online datasets, documented research software and reproducible evaluation are available.

This changes the prior strategy materially. **Do not keep treating 3–5 consenting Bangladesh pharmacies or a Bangladeshi owner's study as funded/available research work.** Existing source thesis remains a 75-page progress report with Chapter 4 and Chapter 5 unfinished, and repeatedly describes **Bangladesh retail pharmacies** as the initial empirical vertical; this plan **does not alter** it until supervisor approval.

## Evidence decision

The work can be a **public-benchmark, retrospective, offline algorithm-and-software evaluation** aimed at eventual Bangladesh SME deployment — **NOT** an empirical field validation in Bangladesh, and **NOT** a verified improvement in business outcomes or human usability. Rewrite research questions, sampling claims, abstract, conclusions and methodology accordingly *only after supervisor approval*.

### One central dataset: dunnhumby The Complete Journey (larger 2-year release)

**Source publisher:** https://www.dunnhumby.com/source-files/ — publisher calls it a *representation* of households' shopping and notes the dataset is designed for academic practice. Therefore treat as **documented real-world-inspired retail data, not independently verified raw observed transactions**, unless provenance is further verified.

**Download mirror:** https://www.kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey — research the actual licence on the chosen copy before use; do not redistribute raw files automatically.  
**Schema example:** https://github.com/bltap-plmarket/dunnhumby-complete-journey/blob/main/docs/SCHEMA.md

The larger release includes approximately:
- `transaction_data.csv`: 2,595,732 basket line records, with `household_key`, `BASKET_ID`, `DAY`, `PRODUCT_ID`, `QUANTITY`, `SALES_VALUE`, `STORE_ID`, `RETAIL_DISC`, `WEEK_NO`, coupon fields;
- `product.csv`: product descriptions/categories;
- `campaign_table.csv`, `campaign_desc.csv`, `coupon.csv`, `coupon_redempt.csv`: promotion/household contact;
- `causal_data.csv`: store/product/week displays and mailers;
- `hh_demographic.csv`: subset demographics.

**Important:** indexed DAY does not necessarily correspond to known calendar dates; no inferred Bangladesh festival/calendar labels. The package `completejourney` (CC0) includes a **different, one-year** subset with 1,469,307 lines; DO NOT merge counts or licences. Full upstream dataset may require download registration and licence review. No historical stock-on-hand balance, supplier invoice costs, supplier lead time, batch expiry or actual realised value of a recommended alternative ordering policy was verified. Households are stable household proxies, not patient/customer identity.

### Optional second dataset: FreshRetailNet-50K

Official https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K — 50,000 store–product 90-day series, hourly stockouts and promotion features; dataset card declares CC BY 4.0. Useful for independent demand censoring and simulated stockout resilience; not a source of RQ2 households or real SME procurement costs. This dataset is **stronger than pretending store inventory exists in Complete Journey**.

### Existing public validation

- Bangladesh retailer demand (Mendeley DOI 10.17632/xwmbk7n3c8.1) — genuinely Bangladeshi one-product RQ1 baseline, no RQ2/RQ3.
- UCI Online Retail II — transaction/churn replication, UK not Bangladesh.
- WFP/DAM Bangladesh food-price series — contextual market benchmark only.
- Synthetic pharmacy or seven sector fixtures — engineering tests and transparent simulations only.

## Revised internet-only RQs to propose to supervisor

| Proposed question | Data | Valid evaluation | Claims excluded |
|---|---|---|---|
| **RQ1**: Can historical transaction and promotion features improve out-of-time retail demand forecasts over transparent baselines? | Complete Journey (main); Bangladesh daily retailer demand (external); FreshRetailNet if used | Rolling-origin/held-out time WAPE/MASE, MAE, bias, feature ablation | Bangladesh pharmacy effect; demand under unavailable stock without observed stock |
| **RQ2**: Can time-frozen purchase histories predict future **household inactivity** with calibrated uncertainty? | Complete Journey `household_key` and DAY | End-of-follow-up censoring; PR-AUC, ROC-AUC, Brier, calibration, Lift@10%, prevalence/recency baseline | Local SME customer behaviour and causal marketing uplift |
| **RQ3**: Can a constrained, forecast-driven policy improve **simulated** retail decisions relative to rule-based policies across plausible cost/lead-time assumptions? | Complete Journey demand replays; FreshRetailNet stockout sensitivity if used | Explicitly assumed purchasing cost, holding cost, lead times and initial stock; sensitivity intervals; feasibility, cost, service level, stockout days; no-action fallback | Measured real profit, real supplier costs, actual Bangladesh field impact, pharmacy expiry claims |
| **RQ4**: How faithful, stable and computationally practical are explanations for B-SMART predictions and recommendations? | Trained RQ1/RQ2 models | Local/global importance consistency, perturbation faithfulness, explanation stability, coverage of constraints, runtime and reproducibility | **Human comprehension/usability/adoption** — not evaluated without real users |

**These are revised *research proposals*, NOT the four existing claims completed.** Explicit supervisor signoff is needed since original RQ3 and RQ4 evaluate observed business value and actual owner usability.

## Minimum experiments runnable entirely online

1. **P01 Dataset audit**: establish distribution/version/explicit licence, SHA256, rows, date range or DAY index, missingness, inconsistent keys, outliers and duplicate transactions; do not substitute generated data into an observed dataset without saying so.
2. **P02 Demand**: group `STORE_ID`, `PRODUCT_ID`, `DAY`; train/validate/test in increasing chronological windows, align coupon/promo from *past and contemporaneously known planned* events. Compare seasonal naive, rolling mean, and one/two ML methods; fix metrics and horizons before final test.
3. **P03 Inactivity**: cutoffs across household histories, horizon 30/60 days selected before test, freeze RFM features at T, purge end-of-file censored labels, time-based validation; compare recency heuristics and logistic/gradient boosting.
4. **P04 Constrained decision *simulation***: deterministic rules with stated assumed initial stock, supplier lead times, unit purchase/holding/stockout costs and inventory budgets; compare baseline reorder and model-driven reorder with identical realized historical sales paths. Label available purchases as *sales observations* not unconstrained true demand.
5. **P05 Explainability**: produce SHAP/permutation analyses for held-out records, top-feature faithfulness via perturbation, stability across refits, explanation coverage and deterministic evidence card checks. **No owner feedback score.**
6. **P06 Independent replication**: run prior Bangladesh retailer single-product forecast as local external benchmark (does not replicate churn/strategy), and optionally stockout challenges on FreshRetailNet.
7. **P07 Product validation**: automated import schema tests, backdated-transaction prevention, tenant-access tests, deterministic results checks, reproducible script and dashboard demos. This is engineering QA, not an RQ4 user usability study.

## Dataset input schema for demo and research

```
transaction: source_id, household_or_customer_id, store_id, basket_id, day_index,
             product_id, quantity, sales_value, discount_amount
product: product_id, department, commodity, brand
promotion: store_id, product_id, week_no, promotion_type
historical_stock: MISSING (do not fill in)
purchasing_cost: MISSING (do not fill in)
supplier_lead_time: MISSING (scenario assumption only)
expiry: NOT APPLICABLE for main grocery research
```

The software **must surface missing data and simulated values as a separate evidence tier**. The product can offer stock/purchase/expiry features for real future deployments, but its internet-only research does not verify their observed accuracy or monetary impact.

## Three viable scope levels

1. **Best academic fit, simplest:** ONE Complete Journey dataset for main P02–P05, plus existing Bangladesh retailer one-product series for a local-context independent RQ1 check. RQ4 renamed technical explainability and RQ3 simulation. No person/shop participation.
2. **Stronger demand/stockouts:** Add FreshRetailNet only for P06, if time and compute permit. It remains a distinct evidence domain.
3. **If supervisor requires Bangladesh-only observational primary data or original RQ4 owner usability unchanged:** **The full stated thesis cannot be completed under the internet-only constraint.** Negotiate narrowed/revised scope early instead of inventing a Bangladesh observational multi-table dataset or survey.

## What must happen to existing submitted report

- Record approval of **public-secondary-data, experimental-computational research** instead of primary-data/field-validation promises.
- Update Chapter 1 scope/population/claims (target-market intent vs validated geography).
- Update Chapter 2 literature positioning, sector-specific evidence, generalisability limits.
- Update Chapter 3 RQ3/RQ4 methods, eligibility, cost assumptions, data-tier definitions, evaluation metrics, ethics (public-data licences), revised outcomes.
- Write Chapter 4 implementation only from code and test evidence; Chapter 5 only from **actual completed experiment outputs**, not this protocol.
- Do not claim real Bangladesh SME performance, measured improvement, or owner usability without direct evidence.

## Recording and storage

Keep a checked-in **manifest** of source, version, licence, retrieved_at, SHA256, row counts, code commit, eligibility and splits. Do not publish copyrighted Kaggle raw archives in GitHub without redistribution permission. Avoid storing datasets in Git for the deployed Docker image when too large; use validated authenticated R2 object storage (setup not complete until Render R2 credentials tested). Built-in seven synthetic datasets remain labelled as such.

**Status on 25 October 2026:** this plan documents available public sources; **no new raw files downloaded, no new experiments executed and no final thesis results written by this edit**.
