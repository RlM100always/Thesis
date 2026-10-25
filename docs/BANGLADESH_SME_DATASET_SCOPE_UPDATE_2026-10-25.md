# Bangladesh SME Datasets — RQ1–RQ4 Feasibility & Scope Amendment (25 October 2026)

> **User clarification (25 Oct 2026):** Eligible initial business can be **ANY Bangladeshi SME**, not necessarily a pharmacy. This is an **alternate proposed research scope**, **not yet reflected or approved** in the submitted thesis PDF. Do not silently revise the earlier pharmacy-specific report or assert that any new dataset has been downloaded/trained.

## Finding

**No publicly verifiable Bangladeshi SME dataset found in this search that jointly contains timestamped SKU purchases, repeat-customer IDs, historical stocks, procurement/lead times, costs and expiry (where relevant), *and* an actual B-SMART user usability evaluation.** These are not interchangeable proxies. RQ4 requires collecting B-SMART task data from target users.

For minimal methodology disruption, recruit **one sector among inventory-carrying Bangladeshi SME retailers**: grocery, clothing, electronics or pharmacy. Software may later support others. Non-inventory service SMEs would require reworking RQ1 and RQ3.

## Candidate matrix — public sources identified and source-level verified

Legend: **Yes** observed suitable attribute/evidence; **Partial** limited secondary evidence; **No** not eligible. The table is *not* a statement of prior execution.

| ID | Dataset and source | Geography & provenance | Actual repeat-customer purchase history | Dated SKU sales | Inventory/lead-time/costs | Fit for RQs | Use decision |
|---|---|---|---|---|---|---|---|
| BD-R01 | [Bangladeshi Retailer Daily Demand (KUET)](https://data.mendeley.com/datasets/xwmbk7n3c8/1), DOI: 10.17632/xwmbk7n3c8.1 | Bangladesh, real **single-product** daily sales 2013–2017, 1,826 days, **two source columns** date/quantity, CC BY 4.0 | No | **Yes**, single product | No | **RQ1 only** (time-series demand baseline) | **Retain existing evidence** |
| BD-R02 | [Comprehensive Retail Network Dataset Bangladesh](https://data.mendeley.com/datasets/mgzvngzng2/1), DOI: 10.17632/mgzvngzng2.1 and [related peer-reviewed paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12765268/) | Bangladesh, field-collected shop attributes for **719,817** reported outlets, product reference and algorithm/manager-informed **sales targets** for **613,656** shops (dataset release reports target data for 18 products; article abstract gives varying product counts), CC BY 4.0 | No | **No**; targets ≠ observed sales | Incomplete: shop visit/distribution metadata but no audited inventory/ledger | **SME geographical/sector context**, descriptive segmentation or planning; **not proof of RQ1 accuracy/RQ3 realised savings** | **Candidate, field-level audit needed** |
| BD-R03 | [World Bank Bangladesh Enterprise Survey 2022](https://microdata.worldbank.org/catalog/6497/data-dictionary/F1) | Real firm interviews in Bangladesh, **998 businesses, 490 variables**; structured cross-sectional enterprise factors (size, sales/performance/finance, barriers), data access per World Bank portal conditions | No | No (survey financial aggregates, not SKU timeline) | No purchase/stock ledger | **RQ3 managerial constraints background; RQ4 business-context background**; no direct RQ1/RQ2, no B-SMART usability test | **Candidate for explanatory SME context** |
| BD-R04 | [GenAI Adoption in SME Digital Marketing Survey](https://data.mendeley.com/datasets/vh63hfbt5g/1), DOI: 10.17632/vh63hfbt5g.1 | Bangladesh University of Business and Technology, **500 survey responses**, perceived usefulness/ease/trust/AI barriers, CC BY-NC 4.0 | No | No | No | **RQ4 background** on acceptance factors; *respondents are not necessarily actual B-SMART SME-owner users* | **Candidate for survey instrument design, not RQ4 direct validation** |
| BD-S01 | [GrocerySales10MDataset](https://data.mendeley.com/datasets/9jvxzmwby5/1), DOI: 10.17632/9jvxzmwby5.1 | Bangladesh-region **fully synthetic 10,000,000 transaction records**, 2023, order/customer/product/quantity/price/timestamp/region; CC BY 4.0 | **Synthetic IDs**, not real behaviour | Synthetic only | No verified actual inventory/lead time | **RQ1/RQ2 pipeline development**, scale and engineering tests; **no empirical Bangladesh generalization** | **Optional synthetic stress test (321 MB compressed)** |
| BD-A01 | [BanglaEcomReviewCorpus](https://pmc.ncbi.nlm.nih.gov/articles/PMC13011172/) | 8,685 labelled Bangla e-commerce reviews collected from Bangladesh-popular platforms | No | No | No | Optional sentiment/UX language research only; *no* direct RQ1–RQ3 | **Do not use as core dataset** |
| BD-A02 | [SARA AI Reception Assistant survey](https://data.mendeley.com/datasets/f4d5dbk6x2/1) | Bangladesh contextual interface study with 2,759 anonymised interaction/survey records from SARA deployed in a university, CC BY 4.0 | No | No | No | RQ4 **design/measurement inspiration only**, *not B-SMART owner decision effectiveness* | **Optional RQ4 study design reference** |

**Provenance risks:** public sample retail files with Bangladesh-labelled `Region` but without disclosed real collection methods must NOT be assumed observational. Likewise, Bangladeshi-author datasets about US or non-Bangladeshi shops are not Bangladeshi business evidence. A real survey and real sales-target data are not real invoice transactions.

## Correct RQ-to-dataset use

| Research question | Minimal observed data needed | Public Bangladesh evidence available | What still must be obtained |
|---|---|---|---|
| **RQ1 Demand Forecasting** | Dated product/SKU quantities by shop/branch, 12+ months recommended; prices and availability when claiming their effect | Bangladeshi retailer's one-product daily quantity; other supporting market prices | Multi-SKU, multi-shop transaction history and preferably stock levels, promotions; real train/test chronological evaluation |
| **RQ2 Customer Inactivity** | Persistent stable pseudonymous customer keys, repeat invoices over time, cutoff T, follow-up (T,T+H], no identity leakage | **No verified public Bangladesh real POS sequence identified** in search | One or more consent-based shops with loyalty/invoice customer key OR explicitly mark RQ2 untestable locally; synthetic IDs do not count |
| **RQ3 Strategy Optimization** | Dated inventory in/out, stockouts, PO/receipts, unit costs, supplier lead time, budgets and actual baseline owner decisions; expiry only for perishable/regulated goods | Shop distributions, product sales targets and WB business obstacles support problem framing but **not measured policy impact** | Real stock/purchase/lead time and outcome records; if unavailable, do transparent **simulated policy comparison** with uncertainty and no field uplift claim |
| **RQ4 Explainability & Usability** | Actual Bangladesh SME owners/staff trying THIS app on predefined tasks and providing correctness, duration, confidence and feedback with consent | BD AI-adoption survey gives contextual scales; SARA gives interaction/survey examples | Recruit real B-SMART users (pilot, usability sessions); no pre-existing public survey can test a product participants never used |

## Recommended single practical industry

**First choice:** a consenting Bangladeshi **grocery / general retail shop** with POS invoices, repeated buyer/loyalty IDs if RQ2 is retained, purchase receipts and current/historical stock. It aligns with existing software's retail operations, is less pharmacy-regulated, and has straightforward SKU forecasting and reorder actions. Clothing or electronics also fit if they have the needed records. Select by **data completeness, consent and retention**, not by the nicest business name.

**Minimum local evidence contract** (one pilot business for implementation; 3–5 independent businesses ideal for multi-shop generalization):
- transactions: `org_id, branch_id, invoice_id, sold_at, sku_id, qty, price, discount, status, customer_pseudo_id(optional)`;
- stock: `org_id, branch_id, sku_id, movement_at, qty_delta, stockout_flag(if_observed)`;
- suppliers/purchasing: `supplier_pseudo_id, sku_id, ordered_at, received_at, qty, unit_cost, lead_time`;
- policies: `branch_id, constraint_effective_at, budget, minimum_order_qty, storage_capacity, reorder_point`;
- optional product lifecycle: `lot_id, expiry_at` **only if actually relevant and observed**;
- actual B-SMART owner tasks: `participant_pseudo_id, task_id, condition, correct, time_seconds, confidence, feedback`.

No phone/email/NID/medical identifiers to public repository. Consent, data-use agreement and ethics approval before business acquisition; anonymise, access-control and set deletion policy.

## Explicit report methodology change required

The current 75-page PDF and archived TeX (see `thesis_report/archive/2026-10-25_user_submitted_report.tex`) call **retail pharmacy the initial empirical vertical**. Switching to "any Bangladeshi SME" is a **substantive scope change**, requiring **supervisor approval** and subsequent updates to:
1. Chapter 1 study context, research aim/population, stakeholder roles and boundaries;
2. Chapter 2 sector-specific literature and application validity;
3. Chapter 3 sampling, RQ operational definitions, task eligibility, example constraints, canonical schema and cross-shop evaluation;
4. RQ3 expiry/lot and clinical-specific constraints: mark optional or replace with applicable perishable/stock-age/supplier budget constraints, *without pretending expiry data exists*;
5. Abstract, title implications, limitation and implementation/experimental-result plans.

**Do not rewrite or claim approval of those sections yet**. Keep the submitted report immutable until approved; this note is a proposed amendment. The GitHub demo has seven synthetic sectors but no multi-sector empirical claim.

## Honest research plan

**Stage A — selection:** choose an inventory-carrying Bangladesh SME sector based on documented access, consent and dataset richness. Verify the actual owned data for stable IDs, historical dates, sales, inventory and purchase costs before committing to all four RQs.

**Stage B — public prototypes:** rerun current Bangladesh single-product RQ1; independently explore World Bank enterprise survey and Bangladesh retail network for **descriptive**, not observational SKU prediction; define reproducible schemas and baselines; optionally test synthetic RQ1/RQ2 software functions.

**Stage C — local acquisition:** onboard one consenting shop for data pipeline validation; extend to multiple shops for genuine transfer claims. Be ready to scope down RQ2 or RQ3 if real fields cannot be obtained.

**Stage D — evaluation:** chronological forecasting with seasonal naive / moving average versus ML and WAPE/MASE; inactivity with recency baseline vs logistic/RF and PR-AUC/Brier/lift; inventory policies against actual recorded baseline or declared simulations; usability study with actual owners/staff and paired tasks.

**Stage E — thesis/product:** complete implementation and results chapters only from successful/failed reproducible runs; drive feature flags off whether the required data are available. Keep SQLite for disposable dev only; permanent operational data require PostgreSQL; R2 private object storage access must be fully configured before treating file persistence as guaranteed.

## Sources (verified on 25 October 2026)

- Jahin & Shahriar 2024, DOI 10.17632/xwmbk7n3c8.1, Mendeley Data.
- Shahin, Swarna & Farid 2025/2026, DOI 10.17632/mgzvngzng2.1 and DOI 10.1016/j.dib.2025.112326.
- World Bank Enterprise Survey Bangladesh 2022, reference BGD_2022_WBES_v01_M, 998 × 490.
- Islam & Morshed 2026, DOI 10.17632/vh63hfbt5g.1, Mendeley Data (CC BY-NC 4.0).
- Uddin 2026, DOI 10.17632/9jvxzmwby5.1, Mendeley Data (**synthetic**).
- SARA user-interaction dataset, DOI 10.17632/f4d5dbk6x2.1.
- BanglaEcomReviewCorpus, PubMed Central PMC13011172.

**No new raw dataset downloaded/benchmarked, no primary SME sampled, no experiment run and no report chapters altered by adding this document.**
