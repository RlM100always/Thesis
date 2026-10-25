# B-SMART — Research Dataset Selection and Evidence Decision (25 October 2026)

> Status: **proposed research protocol, not experimental results**. This file supplements, and does not overwrite, the submitted 75-page report. Thesis initial empirical vertical: **Bangladeshi retail pharmacies**. No new real datasets are claimed downloaded or analysed by this decision.

## Executive decision

**Do not choose a single public dataset as a substitute for Bangladeshi pharmacy data.** The uploaded 75-page progress report formally commits to four RQs: RQ1 context-aware branch/SKU forecasting, RQ2 future customer inactivity, RQ3 feasible replenishment versus the owner's existing policy, and RQ4 owner decision quality/usability. These need distinct observations and sometimes human participants.

The defensible architecture is **Tier 1: 3–5 independently consenting pharmacies (primary; future)** + **Tier 2: well-labelled public benchmarks (method and portability; currently partial)** + **Tier 3: synthetic test fixtures**. Keep three evidence tiers and every experiment's source separate.

**Recommended ONE public transactional backbone, if additional data is needed:** dunnhumby **The Complete Journey** (multi-table original two-year transaction release); validate licence and provenance before downloading. It enables sales history, store/product features, household recency, RFM, inactivity snapshots and campaigns together, but **is not Bangladesh/pharmacy evidence** and has **no observed batch expiry, on-hand inventory, supplier cost, or reliable counterfactual policy impact**.

**Recommended focused supplementary benchmark:** **FreshRetailNet-50K** (stockout-labelled perishable-goods dataset, CC BY 4.0). It is appropriate for RQ1 stockout-censoring robustness, not a real pharmacy field trial and not RQ2.

**Keep** existing UCI Online Retail II, Bangladesh retailer demand, WFP/DAM prices and the declared synthetic pharmacy data as existing comparators, subject to verified reproducibility. Do not replace usable evidence just to increase the number of dataset names.

## Uploaded report evidence: pre-existing scope, not newly invented results

Source: user-provided `thesis.pdf` (75 pages), LaTeX source archived at `thesis_report/archive/2026-10-25_user_submitted_report.tex`, independently from `thesis_report/main.tex`.

| PDF location | Fixed design commitment | Consequence for dataset selection |
|---|---|---|
| Page 44, Table 3.1 | RQ1: WAPE, MASE, interval coverage on unseen branch/SKU periods | Need timestamped SKU demand, pricing/context and ideally stock records |
| Page 44, Table 3.1 | RQ2: PR-AUC, Lift@10%, Brier score | Need longitudinal, stable **pseudonymous** customer identity and future follow-up |
| Page 44, Table 3.1 | RQ3: stockouts, inventory and total cost under policy comparison | Need actual stock/incoming quantities, lead time, constraints and cost; otherwise simulation is clearly hypothetical |
| Page 44, Table 3.1 | RQ4: task correctness, time, confidence, usability | **Cannot be answered by CSV alone**; recruit consenting target owner/operators |
| Pages 44–46 | Target 3–5 pharmacies, 12–24 months (as feasible); evidence tiers and provenance manifest | Tier 1 still not collected per repo `docs/REAL_DATA_SOURCES.md`; ethics before access |
| Pages 61–65 | Frozen chronological validation, baseline comparison, calibration, robustness, block bootstrap and decision outcomes | Lock protocol before opening last holdout |
| Pages 70–71 | Implementation and Experimental Results are essentially empty | Do **not** claim thesis finished or backfill fake experimental figures |

## Existing four analytical datasets — evidence vs missing fields

| Source | Verified role in repository | What it cannot prove |
|---|---|---|
| **BD_Pharmacy_Dataset** (`01_generate_dataset.py`, pharmacy synthetic fixture) | Synthetic method development, run-time tests, 30k transactions and algorithm demonstration | Real shop sales, learned real customer consent, stockout savings, Bangladesh-specific field effectiveness |
| **UCI Online Retail II** (UK gifts/wholesale, 2009–2011; 1,067,371 raw records) | Real transaction ingestion, churn/repeat purchase, RFM, segmentation, price/quantity demand; repo records existing benchmark | Bangladeshi pharmacy generalization, batch expiry/stockout or supplier constraints; nontrivial missing IDs/cancellations |
| **Mendeley Bangladeshi retailer demand** (DOI 10.17632/xwmbk7n3c8.1) | Genuine Bangladesh **one-product** daily quantity benchmark, 1,826 days | Customer churn, retail prices, multi-SKU/branch, expiries and stock-control benefits |
| **WFP/DAM Bangladesh prices** | Market-price context / independent monthly price forecasting | Not pharmacy SKU sales, not customers, not revenue |

Other existing supporting sources (not substitute independent transaction studies): **Medicinal Products in Bangladesh** (DOI 10.17632/zhtvkny53n.1; medicine brand/generic/manufacturer catalogue) and WFP market references. A *medicine catalogue* is not proof that model-generated transactions are real.

Repo's `artifacts/research_portal/EXP-001.json` and `EXP-D093B701.json` contain **two saved completed synthetic-category experiments** (pharmacy/grocery); the grocery record also logs forecast failure. Render currently generates **seven synthetic sector CSVs**. Seven deployed files are **not seven validated real-world research datasets**.

## Candidate evaluation: public data researched 25 October 2026

| Dataset / origin | Customer history | Product/store/time | Actual stockout labels | Pharmacy batch/expiry | Suitable role | Decision |
|---|---|---|---|---|---|---|
| **dunnhumby The Complete Journey**, retail grocery, US | Yes, household | Yes, household/product/store/baskets/campaigns/discounts | No verified on-hand stock | No | One cohesive **public transactional backbone** for RQ1/RQ2 | **Prioritise new public candidate; not yet obtained** |
| **FreshRetailNet-50K**, fresh retail | No | Yes, store/product/hour/day | **Yes**, hourly | No | RQ1 censored-demand + stockout robustness | **Prioritise as focused benchmark; not yet obtained** |
| **UCI Online Retail II**, UK | Yes, partially missing | Yes, invoice/SKU/time | No | No | Existing RQ1/RQ2 external replication | **Retain** |
| **M5 Forecasting Accuracy**, USA Walmart | No | Yes, SKU/store/day with prices/events | No | No | Optional independent forecasting baseline | **Defer**: ~450 MB, competition-specific use restrictions, overlapping effort |
| **Corporación Favorita Store Sales**, Ecuador | No | Store/family/day/promotions | No | No | Optional forecast cross-store stress test | **Defer**; not needed for RQ2/RQ3 |
| **BD retailer demand**, Bangladesh | No | Single item/time | No | No | Local demand portability | **Retain** |
| **WFP/DAM prices**, Bangladesh | No | Market/commodity/month | No | No | External context, independent price study | **Retain**, not integrated as exact SKU price without matching |
| **3–5 pharmacies, Bangladesh** | Optional/consented only | Required POS invoice/SKU/branch/day | Inventory movement/stock status needed | Target as recorded | **Primary domain validity** for RQ1/RQ3, eligible RQ2/RQ4 | **Essential; no verified collection yet** |

### Public candidate A — dunnhumby usage constraints and variants

**Do not combine two distinct Complete Journey variants silently.**

- Large `transaction_data.csv` release cited at 2,595,732 basket-line rows, associated with product, household, coupon, campaign and promotional tables. It uses **DAY/WEEK_NO indices**, not authoritative calendar dates. Never invent actual dates/holidays; keep relative day index and avoid false national calendar enrichment.
- The `completejourney` package **separately** describes a 2,469-household, one-year subset of **1,469,307** transaction rows; it is **not** the same raw sample.
- Licensing may differ by release or mirror (package CC0; some Kaggle re-hosts describe DbCL). **Review chosen copy's licence/terms before downloading, redistributing or selling a derivative**. Keep raw package/data out of public GitHub unless explicitly permitted.
- Customer inactivity from no recorded repeat purchase is not provable as true long-term churn and household != pharmacy customer. Use a **defined 30/60/90-day horizon, sufficient future follow-up and only historically available features**. Campaign exposure does not establish causal incremental profit.
- URLs: https://www.kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey and https://github.com/bradleyboehmke/completejourney . A separate, huge *dunnhumby Source Files* synthetic dataset must **not** be confused with this named release.

### Public candidate B — FreshRetailNet-50K, genuine stockout benchmarking

- Official dataset: https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K ; paper: https://arxiv.org/abs/2505.16319
- Published split includes approximately **4.5M train plus 350k eval** daily store-product observations; 50,000 series of 90 days, 898 stores. Official card states **865 perishable SKUs** (paper abstract may round differently).
- Fields include `stock_hour6_22_cnt`, `hours_stock_status`, `hours_sale`, `sale_amount`, `discount`, date, product/store/category, weather and activity flags. `sale_amount` is **scaled/normalised**: do not call it pharmacy revenue/BDT or unscale without reference factor.
- Licence in published dataset card: **CC BY 4.0**; attribute dataset creators.
- Use store-product aligned time windows; test masked true stockout periods and sensible forecast metrics, stockout-censoring sensitivity and calibration of policy simulations. A stockout-aware algorithm must use only **past** stock states available at prediction time, never future stockout labels as features.
- Not eligible evidence for pharmacy-expiry, patient safety, retention or business profits.

### Primary domain data — indispensable evidence contract

Subject to ethics approval/consent and sufficient data: recruit **3–5 independent Bangladesh retail pharmacies**, target **12–24 months** where feasible. Minimum analytical entities:

```text
organization(org_id, region, consent_scope)
branch(branch_id, org_id)
product(sku_id, generic/brand, pack_size, prescription_flag, cold_chain_flag)
invoice(invoice_id, branch_id, sold_at, status, discount, payment_mode)
invoice_line(invoice_id, sku_id, qty, sold_unit_price, discount, return_flag)
inventory_movement(branch_id, sku_id, lot_id, event_at, qty_delta, reason)
lot(lot_id, sku_id, expiry_date, received_at, available_qty)
purchase_order(branch_id, supplier_id, sku_id, ordered_at, received_at, qty, cost)
supplier_policy(supplier_id, valid_from, lead_time, MOQ, pack_multiple)
business_constraint(branch_id, effective_from, budget, capacity, risk_budget)
optional_customer_purchase(org_scoped_pseudo_id, invoice_id, event_at)
optional_owner_decision(action_id, issued_at, accepted/rejected/deferred, outcome_at)
```

Only include fields **actually recorded**; unknown stock must be unknown, not zero. No artificial customer identifiers may be assigned to make a source eligible for RQ2. Cold-chain constraints must never be inferred from drug names without verified domain rules. Keep real identifiers and secrets out of GitHub, screenshots, logs and public app. De-identification **and** authorised use remain required.

### Eligibility gates

- RQ1 eligible iff time-indexed SKU quantities, unique product/branch and reliable cutoff semantics; stockout-aware claims require stock availability observations.
- RQ2 eligible iff persistent **pseudonymous** customer keys + observation/follow-up windows + documented consents and defensible inactivity definition.
- RQ3 eligible iff stock/movements, lead times, costs/feasible bounds and comparator; if missing, **simulation only**, with assumptions and no measured uplift claim.
- RQ4 eligible iff actual human users perform blinded/counterbalanced matched decision tasks; cannot be "complete" from dataset downloads.
- A dataset may satisfy one research question and fail others. Mark N/A, do not fill with synthetic columns to create nominal eligibility.

## One research-to-product architecture

```text
REAL PHARMACY (future)      PUBLIC DATA (benchmark)     SYNTHETIC (QA only)
         |                         |                        |
         +--------------- source-scoped ingest ------------+
                                   |
                      validation + provenance manifest
                                   |
                  strict organisation boundaries + schema map
                                   |
               event records -> immutable as-of-T snapshots
                                   |
             KPI/analytics + baseline + forecast + inactivity
                                   |
               eligible constraints + abstain/no-action gate
                                   |
               explanation -> owner accept/reject/defer log
                                   |
                 later realised outcomes + evaluation
```

**Software product rule:** same user-facing software supports multiple verticals as extensions, but empirical claims are initially for pharmacy only. Hide/disable (or explicitly mark unavailable) decisions that need absent fields. Initial rollout should prioritise correct POS, purchases, lot/expiry-aware inventory, payments, access controls, CSV import/export and audit history; start prediction only after reliable historical data and a robust baseline. Never create a universal cross-vertical ML model without separate evidence.

## Thesis claim ledger: status as of 25 October 2026

| Claim | Evidence currently in repo | Permissible thesis wording |
|---|---|---|
| B-SMART prototype and recommendation code exists | Modules, saved synthetic runs, current deployed service | "Prototype implemented" / details after reproducibility QA |
| Public retail models have produced validation artifacts | `artifacts/real_public/*.json` with numerical results | "Preliminary external benchmark", metrics only after rerun and audit |
| Bangladesh pharmacy prediction accuracy verified | **No consenting primary dataset located** | **Do not claim** |
| Multiple-pharmacy pooled model generalises | No held-out real pharmacies | **Do not claim** |
| Recommendations save pharmacy money | No genuine field counterfactual or measured impact | **Do not claim** |
| All seven SME sectors validated | Seven generated synthetic fixtures, two archived experiment results | **Do not claim** |

## Source registry (externally verified)

1. UCI Online Retail II, D. Chen, DOI 10.24432/C5CG6D, https://archive.ics.uci.edu/dataset/502/online+retail+ii (CC BY 4.0).
2. Jahin & Shahriar (2024), Supply Chain Demand Forecasting Dataset of Bangladeshi Retailer, DOI 10.17632/xwmbk7n3c8.1, https://data.mendeley.com/datasets/xwmbk7n3c8/1 (CC BY 4.0).
3. WFP/DAM, Bangladesh food price context, https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh (CC BY-IGO as documented; attribution required).
4. Rahman & Khan (2024), Medicinal Products in Bangladesh, DOI 10.17632/zhtvkny53n.1, https://data.mendeley.com/datasets/zhtvkny53n/1 (CC BY 4.0; catalogue only).
5. Dingdong-Inc (2025), FreshRetailNet-50K, https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K ; https://arxiv.org/abs/2505.16319 (CC BY 4.0).
6. dunnhumby/84.51 Complete Journey dataset variants, https://www.kaggle.com/datasets/frtgnn/dunnhumby-the-complete-journey ; https://github.com/bradleyboehmke/completejourney (check exact version/terms before use).
7. M5 Forecasting, https://www.kaggle.com/competitions/m5-forecasting-accuracy/data (competition rules; optional only).
8. Corporación Favorita, https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/data (optional only).

All titles and counts above describe **upstream documentation or existing versioned repository artifacts**; they are **not** assertions that new datasets have been ingested or new experiments run in this GitHub change. Freeze source URL, version, retrieval timestamp, row count and SHA-256 when each dataset is actually retrieved.
