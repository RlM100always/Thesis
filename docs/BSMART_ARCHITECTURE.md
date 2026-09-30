# B-SMART — Full System Architecture (10 layers)

This is the authoritative architecture for the thesis. Every layer below is
either **[IMPLEMENTED]**, **[PARTIAL]** or **[PROPOSED]** — that status is not
decoration, it is the rule that stops a proposal being presented as a result.

The target vertical is **Bangladeshi retail pharmacy SMEs**. Layers 1–4 are
generic enough to port to another SME vertical later, but layers 5–8 encode
pharmacy economics (batch/expiry, pack conversion, cold chain, prescription
repeat cadence) and would need redesign and revalidation for any other
category. No cross-vertical claim may be made before that work is done.

```
 1  PHARMACY DATA LAYER
 2  DATA VALIDATION & CANONICAL LAYER
 3  HISTORICAL SNAPSHOT LAYER            (decision cutoff t)
 4  ANALYTICS / AI LAYER                 (KPI · demand · inactivity · segments)
 5  B-SMART STRATEGY RECOMMENDATION      ★ the thesis's own algorithm
 6  CONSTRAINT ENGINE                    (remove infeasible actions)
 7  STRATEGY OPTIMIZATION                U(a) = benefit − cost − λ·risk
 8  EXPLAINABLE RECOMMENDATION
 9  OWNER DECISION                       accept / reject / modify / defer
10  OUTCOME & MONITORING LAYER           feedback, drift, revalidation
```

---

## Layer 1 — Pharmacy Data Layer **[PARTIAL]**

Entities: Sales · Products · Stock · Purchase · Batch · Expiry · Supplier ·
Customer · Payment · Expense · Promotion · Price.

| Where | Status |
|---|---|
| `api/domain_models.py` (live multi-tenant SQL app) | **[IMPLEMENTED]** — all 12 entities exist as tables |
| `00a_generate_pharmacy_dataset.py` (research dataset) | **[PARTIAL]** — Sales, Products, Price, Stock level, Batch, Expiry, Customer, Payment, Promotion present; Supplier, Purchase order and Expense are not generated |

Real vs synthetic provenance for every column is in
`normalized_data/DATASET_MANIFEST.md`. The medicine catalogue (111 SKUs:
brand, generic, dosage form, manufacturer) is **real** — Mendeley
DOI 10.17632/zhtvkny53n.1. Demand seasonality is fitted from a **real**
Bangladeshi daily-demand series, DOI 10.17632/xwmbk7n3c8.1.

## Layer 2 — Data Validation & Canonical Layer **[PARTIAL]**

| Check | Status | Where |
|---|---|---|
| Missing / duplicate detection | **[IMPLEMENTED]** | `01_preprocessing.py` fails loudly on unhandled nulls |
| SKU / Product ID consistency | **[IMPLEMENTED]** | `00_normalize_dataset.py` surrogate keys + lossless-join assert |
| Box–Strip–Piece unit normalization | **[PROPOSED]** | `pack_multiple` rounds order quantity, but source units are not yet converted |
| Timestamp checking | **[IMPLEMENTED]** | `13_` asserts all transaction timestamps parse |
| Returns / cancellation handling | **[PARTIAL]** | `Is_Returned`/`Return_Reason` carried; not yet netted out of demand |
| Stock / invoice reconciliation | **[PROPOSED]** | residual formula specified in the report, not computed |
| Data source & provenance tracking | **[IMPLEMENTED]** | `ImportBatch` + checksum in `api/data_import_routes.py`; `DATASET_MANIFEST.md` for research data |

## Layer 3 — Historical Snapshot Layer **[IMPLEMENTED]**

Decision cutoff `t`. Only information available strictly before `t` may enter a
feature. This is the project's central anti-leakage device.

- `13_bsmart_recommendation_engine.py::build_snapshot()` freezes `X_t` at the
  latest transaction date and reports how many rows it covers.
- `01b_customer_features.py` aggregates to one row per customer so a customer
  cannot span train/test, and fits the scaler on train only.
- `09_retrain_models.py` opens an untouched 20% holdout exactly once, after all
  tuning is finished inside the development rows.

Evidence that this matters, measured on this dataset: transaction-level split
with a CLV feature scores **85.27%**; the same task done leak-free scores
**~51%** against a 35.2% majority baseline. ~34 points of the original headline
were leakage, not modelling.

## Layer 4 — Analytics / AI Layer **[IMPLEMENTED]**

| Component | Model | Current performance |
|---|---|---|
| Performance evaluation / KPI | deterministic aggregates | — |
| Demand forecasting | EWMA(span=6) vs mean baseline, gated per (SKU, division) on a 3-month held-out tail | gate picked EWMA on 357 series, baseline on 512 — the baseline wins more often, and that is reported as-is |
| Monthly sales forecast | seasonal-naive vs LSTM vs ARIMA | **seasonal-naive wins**: MAPE 4.08% vs 10.60% (LSTM) vs 16.16% (ARIMA) |
| Customer inactivity (churn) | leak-free classifier, `09_retrain_models.py` | ROC-AUC **0.924**, PR-AUC **0.814**, lift@10% **2.41×**, base rate 34.1% |
| Customer segmentation | RFM + K-Means | K=4, silhouette 0.2354 — a business choice; the metric prefers K=2 |

**Supporting-model discipline:** a complex model is used only where it beats
the transparent baseline on held-out evidence. On this dataset that rule
demotes the deep model (LSTM loses to seasonal-naive) and demotes EWMA on 512
of 869 series. Reporting those losses is the point, not an embarrassment.

## Layer 5 — B-SMART Strategy Recommendation Algorithm ★ **[IMPLEMENTED]**

`13_bsmart_recommendation_engine.py`. **This is the thesis's own algorithm.**
Its components (EWMA, gradient boosting, newsvendor cost reasoning) are
established; the contribution is their composition into a constraint-aware,
abstention-capable, quota-balanced recommender fitted to pharmacy economics.

Inputs: demand forecast · customer inactivity risk · KPI/business performance ·
customer segment · uncertainty.

It generates three candidate action types — two of which exist *only* because
this is a pharmacy:

| Action | Pharmacy-specific? | Generated from |
|---|---|---|
| **Reorder** | partly (shelf-life cap) | demand gate + stock urgency |
| **Near-expiry markdown** | **yes** | recorded batch expiry within the near-expiry window |
| **Retention contact** | no | churn model + consent |

**A second implementation runs on a tenant's own live data** (`api/bsmart_live.py`,
2026-09-30, `/api/app/bsmart/run`), not the frozen research CSV above. It
generates the same three action types from the operational schema —
reorder from `Product`/`InventoryBalance`/`SalesOrder`, near-expiry from the
live `Batch`/`BatchStock` ledger, retention from `Customer`/`SalesOrder` with
the same consent gate — and persists into the same `Recommendation` table the
research import does, so one decision/outcome/monitoring loop (layers 9-10)
serves both. **[PARTIAL]**, not [IMPLEMENTED] to the same degree as the
research engine: the live schema has no pack size, MOQ, cold-chain flag,
storage capacity or owner-declared budget yet (see Layer 6 below), so those
constraints are simply absent rather than approximated. `/bsmart-actions`
labels every recommendation "নিজের ডেটা" (live) or "গবেষণা নমুনা" (research
sample) so the two are never presented as the same evidence tier.

## Layer 6 — Constraint Engine **[IMPLEMENTED]**

Infeasible actions are removed *before* ranking. Abstention is valid safety
behaviour, not a system error (report §3.2.4.2).

| Group | Constraint | Status |
|---|---|---|
| Inventory | current stock | **[IMPLEMENTED]** — `Stock_Level` urgency gate |
| Inventory | incoming stock | **[IMPLEMENTED]** — inventory position `IP = on-hand + on-order − backorder` |
| Inventory | backorder | **[IMPLEMENTED]** — added to required quantity |
| Purchasing | budget | **[IMPLEMENTED]** — 40% share of identified need |
| Purchasing | supplier lead time | **[IMPLEMENTED]** — declared assumption, 5 days |
| Purchasing | MOQ | **[IMPLEMENTED]** — order raised to the supplier minimum, *unless* the larger quantity could not clear before expiry, in which case the action is dropped rather than inflated |
| Purchasing | pack size | **[IMPLEMENTED]** — order rounded to pack multiple |
| Product | expiry | **[IMPLEMENTED]** — near-expiry window drives its own action type |
| Product | remaining shelf life | **[IMPLEMENTED]** — order capped to what demand can clear before expiry |
| Product | storage capacity | **[IMPLEMENTED]** — one action may not consume more than a declared share of free shelf space |
| Product | cold chain | **[IMPLEMENTED]** — cold-chain SKUs are capped against refrigerated capacity, not shelf capacity |
| Customer | contact consent | **[IMPLEMENTED]** — hard gate on `Marketing_Consent` |
| Customer | business policy | **[IMPLEMENTED]** — campaign capacity per cycle; consent says who *may* be contacted, capacity says how many *can* be |

This table describes the research engine (`13_bsmart_recommendation_engine.py`).
The live engine (`api/bsmart_live.py`, Layer 5 above) implements current
stock, incoming stock, supplier lead time (real, from `Supplier.typical_lead_days`,
not a declared constant) and contact consent — the constraints the live
operational schema actually has data for. It does **not** implement budget,
MOQ, pack size, storage capacity, cold chain or campaign capacity: none of
those fields exist on `Product`/`Supplier` yet, and approximating a budget as
a fraction of one tenant's own small candidate set was tried and found to
degenerate (see the module's own comment) rather than shipped as a fake
constraint. Wire each one honestly as its underlying field is added.

Cold-chain and prescription-only status are **real pharmacy domain facts**, not
invented flags: insulin requires 2–8 °C storage, and antibiotics and
chronic-disease medicines are prescription-only under the DGDA schedule.

**Measured effect of turning the full engine on** (same dataset, same cutoff):
reorder candidates fell 538 → 126 once incoming stock was netted off demand,
and feasible retention actions fell 990 → 150 once campaign capacity applied.
The constraint engine is not decorative — it removes three quarters of what a
naive recommender would have suggested.

## Layer 7 — Strategy Optimization **[IMPLEMENTED]**

`U(a) = E[ΔProfit(a)] − ActionCost(a) − λ·Risk(a)`, λ = 0.5 declared.

**R_t is a balanced slate, not a leaderboard.** A pure global sort is dominated
by whichever action type carries the largest BDT magnitude — on real medicine
economics that is always retention (a customer's lifetime value dwarfs the
margin on one cheap medicine line). Sorted globally, R_t came back 15 retention
actions and zero stock actions: correct arithmetic, useless to an owner. R_t
therefore reserves a per-type quota and ranks by `U(a)` within each type.

## Layer 8 — Explainable Recommendation **[IMPLEMENTED]**

Every action carries `reason`, `confidence`, `cutoff`, `evidence_source` and a
structured `explanation` block: the evidence behind the quantity, plus a
per-constraint verdict. Real output from the engine:

```
Order 50 units of Losucon M (Rajshahi)

Why?  forecast demand over lead time = 27.9    incoming stock = 41
      safety stock = 5.7                       backorder     = 10
      lead time = 5 days                       stock status  = Low
      demand model = model (EWMA gate beat the mean baseline on a held-out tail)

Budget ok (৳444 of ৳26,181) · MOQ ok (raised to 50) · Pack ok (multiple of 10)
Shelf life ok · Storage ok · Cold chain not required        Confidence = model
```

Served at `/api/research/bsmart/latest` and rendered by
`frontend/src/pages/BSmartAlgorithm.jsx`. A capped or blocked constraint is
styled distinctly from a clean pass, so "capped to shelf allowance" can never
be misread as "ok".

## Layer 9 — Owner Decision **[IMPLEMENTED]**

Accept / Reject / Modify / Defer, with the pharmacist as final authority.

- `Recommendation` persists the action verbatim — utility terms, constraint
  verdicts and explanation — so it stays auditable after the model that
  produced it has been retrained or replaced.
- `RecommendationDecision` is **append-only**: changing your mind adds a row
  rather than editing one, so the decision history survives.
- `modify` requires the owner's own quantity. A systematic gap between the
  suggested and chosen quantity is itself a measurable finding about the model.
- `POST /api/app/bsmart/recommendations/{id}/decision`

## Layer 10 — Outcome & Monitoring Layer **[IMPLEMENTED]**

`RecommendationOutcome` records what actually happened: action taken, stock-out
days before/after, holding cost before/after, expired value, customer response,
predicted vs realised quantity, and a drift flag.

`GET /api/app/bsmart/monitoring` aggregates acceptance rate, realised
stock-out and holding-cost change, mean forecast error and response rate.

**Every metric returns `null` when nothing has been observed**, never 0 — an
unmeasured outcome must not read as a measured zero. The endpoint says so in
its own response. Until real pharmacies feed this loop, **no business-outcome
claim may be made**: the thesis can claim a working, honestly-evaluated,
fully-instrumented recommender, not a proven improvement in profitability.

---

## Honest status summary

| Layer | Status | Where |
|---|---|---|
| 1 Data | PARTIAL | `00a_generate_pharmacy_dataset.py`, `api/domain_models.py` |
| 2 Validation | PARTIAL | `00_normalize_dataset.py`, `01_preprocessing.py`, `api/data_import_routes.py` |
| 3 Snapshot | IMPLEMENTED | `13_…::build_snapshot`, `01b_customer_features.py`, `09_retrain_models.py` |
| 4 Analytics | IMPLEMENTED | `04`, `08`, `09`, `03`, `13_…::gate_demand_model` |
| 5 B-SMART | IMPLEMENTED | `13_bsmart_recommendation_engine.py` |
| 6 Constraints | IMPLEMENTED (13 of 13) | `13_…::build_reorder_candidates`, `::feasibility_and_rank` |
| 7 Optimization | IMPLEMENTED | `13_…::feasibility_and_rank` (quota-balanced slate) |
| 8 Explanation | IMPLEMENTED | engine `explanation` block → `BSmartAlgorithm.jsx` |
| 9 Owner decision | IMPLEMENTED | `Recommendation`, `RecommendationDecision`, `api/bsmart_routes.py` |
| 10 Outcome/monitoring | IMPLEMENTED | `RecommendationOutcome`, `/api/app/bsmart/monitoring` |

Remaining gaps are both in the **data** layers, not the algorithm: box–strip–piece
unit conversion and stock/invoice reconciliation (layer 2), and supplier,
purchase-order and expense generation in the research dataset (layer 1).

## Why this design is defensible for a Bangladeshi pharmacy SME

1. **It refuses rather than guesses.** No consent, no contact — 781 of 1,771
   flagged customers are abstained on. A recommender that always answers is
   easier to build and worse to trust.
2. **It lets the baseline win.** The promotion gate demoted the complex model
   on 512 of 869 series and seasonal-naive beat LSTM outright. The thesis
   reports those losses.
3. **It encodes pharmacy economics, not generic retail.** Shelf-life caps and
   near-expiry markdown have no equivalent in a general reorder rule, and
   expiry is exactly where a Bangladeshi pharmacy's cash actually dies.
4. **It is auditable end to end.** Every candidate — feasible or not — is
   written to `bsmart_candidate_actions_audit.csv` with the reason it survived
   or was dropped.
5. **It keeps the owner in charge.** The system ranks and explains; the
   pharmacist decides (layer 9, once built).

**What it is not, yet:** validated on real pharmacy data. The dataset is
real-catalogue-anchored but its transactions are synthetic (Tier 3). Tier 1
collection under `docs/REAL_DATA_PROTOCOL.md` is what converts "a working
algorithm" into "a proven one".
