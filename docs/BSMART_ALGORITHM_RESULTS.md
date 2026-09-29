# B-SMART Algorithm — Real Run Results (current)

This is the current, authoritative record of what `13_bsmart_recommendation_engine.py`
actually produces. **Do not re-derive any B-SMART number by hand from the JSON/CSV —
cite this file.**

It supersedes every earlier run. The legacy 32k-row multi-sector Faker dataset
(a 5-name "pharmacy-SKU slice" of Antacid/Antibiotics/BP Medicine/Diabetes
Medicine/Vitamins, priced on the same random scale as apartments and MRI scans)
has been **deleted and replaced** — see `normalized_data/DATASET_MANIFEST.md`
and `00a_generate_pharmacy_dataset.py`.

## The dataset this run uses

Built by `00a_generate_pharmacy_dataset.py`:

- **Real**: 111 actual Bangladeshi medicine SKUs (brand, generic, dosage form,
  manufacturer) from the Mendeley *Medicinal Products in Bangladesh* dataset
  (DOI 10.17632/zhtvkny53n.1, CC BY 4.0); real BD divisions/districts;
  transaction-timing seasonality (day-of-week, month-of-year, year-over-year
  growth, noise scale) fitted from the real `bd_retailer_demand.xlsx`
  Bangladeshi daily-demand series (DOI 10.17632/xwmbk7n3c8.1).
- **Synthetic, declared**: customers and transaction linkage; per-SKU retail
  price (no real per-SKU Bangladeshi price dataset exists — assigned from
  typical price bands per drug class); `Marketing_Consent` (55% assumed
  opt-in); batch/expiry dates; the CRM tier label and the customer-lapse
  process (both deliberately noisy — see the manifest for why).

4,510 customers with transactions, 30,000 transactions, 2021-01-01 to
2024-12-31. Still **not** Tier-1 real pharmacy partner data
(`docs/REAL_DATA_SOURCES.md`): no public dataset anywhere combines Bangladeshi
origin + observed pharmacy transactions + customer identity.

## What the script is

`13_bsmart_recommendation_engine.py` implements **Algorithm 1** from
`thesis_report/Chapters/proposedMethod.tex` (`alg:bsmart`,
`sec:sequential_procedure`) as real, runnable code — not a diagram of it. It is
the thesis's own algorithm, designed for the Bangladeshi retail-pharmacy
vertical; it is not an off-the-shelf method.

Reproduce the whole chain with:

```powershell
.\.venv312\Scripts\Activate.ps1
python 00a_generate_pharmacy_dataset.py
python 00_normalize_dataset.py
python 01_preprocessing.py
python 01b_customer_features.py
python 09_retrain_models.py
python 13_bsmart_recommendation_engine.py
```

The generator is seeded, so the dataset is byte-identical on every run.

## Three action types — two of them pharmacy-specific

| Action type | What it proposes | Gate it must pass |
|---|---|---|
| **Reorder** | Order N units to cover lead-time demand at 1.65-sigma service | Purchasing budget share **and** a shelf-life cap: quantity may not exceed what this SKU's own demand rate can clear within the 180-day minimum accepted shelf life |
| **Near-expiry** *(pharmacy-specific)* | Mark down stock on batches expiring within 120 days, before a share of it is written off | Time: only feasible while shelf life remains |
| **Retention** | Contact a customer the churn model flags | Explicit `Marketing_Consent` — no consent, no action |

The near-expiry arm and the shelf-life cap exist because this is a pharmacy.
Generic retail reorder logic has no equivalent of either (see
`docs/PHARMACY_VERTICAL_SCOPE_AND_SUPERVISOR_GUIDELINE.md` §6).

## R_t is a balanced slate, not a leaderboard

A pure global sort on `U(a)` is dominated by whichever action type carries the
largest BDT magnitude. On real medicine economics that is always retention —
a customer's lifetime value dwarfs the margin on one cheap medicine line (the
measured spread per action type is in the run block below).

Sorted globally, R_t came back **15 retention actions and zero stock actions** —
operationally useless to a pharmacy owner, who needs their day's stock work as
well as their call list. R_t therefore reserves a quota per action type
(`top_k_quota`, 5/5/5) and ranks by `U(a)` *within* each type, redistributing
unused quota by utility. This is a deliberate design decision, declared in
`ASSUMPTIONS`, not an artifact.

## Latest run (2026-09-13, cutoff 2024-12-31) — full 13-constraint engine

```
reorder candidates generated:     126
near-expiry candidates generated: 361   (of the (SKU, division) pairs holding at-risk batches)
retention candidates generated:  1961
total candidates:                2448

reorder feasible:                  53   (budget + MOQ + storage + shelf life)
near-expiry feasible:             361   (all still have shelf life left)
retention feasible:               150   (consent gate, then campaign capacity)

R_t (top-K):                       15   balanced 5 reorder / 5 near-expiry / 5 retention
reorder budget committed:      ৳2,994 of the 40% share of ৳65,451 identified need
model-ladder gate:            357 EWMA-model vs 512 mean-baseline series
churn model threshold:         0.4177
churn ROC-AUC (holdout):       0.936
churn PR-AUC (holdout):        0.820  (base rate 0.343, lift@10% 2.47x)
```

**The constraint engine does most of the work.** Turning the six new
constraints on cut reorder candidates 538 → 126 (incoming stock is netted off
demand, so orders already in transit are no longer re-ordered) and feasible
retention 990 → 150 (campaign capacity: a three-staff shop cannot ring 990
customers in a cycle). 2,448 candidates reduce to 564 feasible actions —
roughly three quarters of what a naive recommender would have proposed is
removed before ranking even begins.

Top action of each type in `R_t`:

```
retention   CUST-BD-02040   U = 321.46 − 5.00 − 34.63   = ৳281.84
near-expiry Actrapid        U = 1234.19 − 773.98 − 179.99 = ৳280.22   (insulin: cold-chain SKU)
reorder     Losucon M       U = 59.83 − 8.89 − 8.21      = ৳42.73
```

Utility scale by action type, which is why R_t uses a quota rather than a
global sort:

| Action type | mean U(a) | max U(a) |
|---|---|---|
| Reorder | −৳0.6 | ৳42.7 |
| Near-expiry | ৳24.4 | ৳280.2 |
| Retention | ৳43.5 | ৳281.8 |

Reorder's mean utility is *negative*: most reorder candidates are not worth
acting on once carrying cost and forecast risk are priced in, and the engine
says so rather than padding the list.


## Full machine-readable output

- `output/bsmart_recommendations.json` — `R_t`, the ranked feasible actions
- `output/bsmart_candidate_actions_audit.csv` — all 2,448 candidates, feasible or not, each with a reason
- `output/bsmart_run_summary.json` — the counts above, for citing
- `output/figures/bsmart_*.png` — the 4 charts used on the slides

## Slide mapping

| Slide (`BSMART_Thesis.pptx`) | Content | Figure |
|---|---|---|
| 25 — "We Ran the Algorithm — Here Is R_t" | Balanced top-15: 5 reorder, 5 near-expiry, 5 retention | `bsmart_top_recommendations.png` |
| 26 — "One Recommendation, Fully Explained" | Worked example: benefit − cost − risk for the top action | `bsmart_worked_example.png` |
| 27 — "2,448 Candidates In, 15 Recommendations Out" | Funnel with the real counts above, log scale | `bsmart_funnel.png` |
| 28 — "The Model Behind Step 4 Actually Separates Customers" | Real churn score histogram, actual vs predicted | `bsmart_churn_scores.png` |
| 29 — "Our Data: What's Real, What's Not Yet" | Evidence tiers, referencing this run | — |

## Why retention now produces actions (it previously produced zero)

The old dataset had no `marketing_consent` field at all, so every retention
candidate was abstained on. That was correct behaviour, but it meant the
retention arm could never be demonstrated. This dataset carries a
`Marketing_Consent` field, so the same consent gate now passes
customers who opted in, and campaign capacity then limits the cycle to 150
contacts — 1,961 flagged, 150 actionable. The gate is unchanged code —
only the evidence available to it changed. When Tier-1 partner data arrives,
consent stops being a declared assumption and becomes an owner-recorded fact,
with no further code change required.

## What supersedes what

Every number produced on the legacy multi-sector dataset has been deleted, and
the full numbered pipeline (`02` … `10`) has been rerun on the new pharmacy
dataset. Current pipeline results are recorded in `CLAUDE.md`; the B-SMART
numbers above are the ones to cite for Algorithm 1 itself.
