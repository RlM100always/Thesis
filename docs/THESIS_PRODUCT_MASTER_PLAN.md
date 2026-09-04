# B-SMART thesis and product master plan

Supersedes the previous version of this file. Consolidates the original
proposal, the codebase built so far, and the supervisor's structural
directions (chapter layout, literature-review scale, plagiarism/AI-use
limits, scalability protocol) into one plan.

## Approved title (unchanged)

**AI-Powered Business Analytics System for Performance Evaluation, Insight
Extraction, and Strategy Optimization**

The implementation focus stays Bangladeshi retail/inventory-based SMEs while
the architecture supports future sector templates. Narrowing the *scope*
this way keeps the title defendable without renaming anything already
approved.

## 1. Final positioning

This is not a dashboard plus a few model comparisons. The system has three
layers:

1. **Business Operations Layer** — sales, product, inventory, purchase,
   expense, customer, payment, supplier, and branch management. (Already
   built: `api/domain_models.py`, `commerce_routes.py`, `finance_routes.py`,
   `directory_routes.py` — see [CLAUDE.md](../CLAUDE.md) for the current
   implementation map.)
2. **AI Analytics Layer** — demand forecasting, future churn/next-purchase
   prediction, customer segmentation, anomaly detection, performance
   analysis.
3. **Strategy Optimization Layer** — forecast and risk scores turned into
   reorder quantity, customer-retention priority, and product/branch action
   ranking.

Real business data is the primary evidence. Synthetic/artificial data is
used **only** for: system testing, rare-scenario simulation, scalability
experiments, demo accounts, privacy-safe worked examples, and limited,
explicitly-labelled augmentation experiments. Synthetic and real results are
never mixed in a single reported number — see the ablation table and
`ml/scalability_benchmark.py`'s `synthetic_scalability_only` label in
[CLAUDE.md](../CLAUDE.md).

## 2. Formal problem formulation

For business $b$, branch $l$, product $p$, customer $c$, time $t$, the
operational data is:

$$D = \{\text{Sales, Inventory, Purchase, Expense, Customer, Payment, Context}\}$$

Three outputs:

**Demand prediction**
$$\hat{y}_{b,l,p,t+h} = f(X_{history}, X_{price}, X_{promotion}, X_{calendar}, X_{market})$$
— units of product $p$ expected to sell over the next $h$ days.

**Customer risk**
$$P(\text{No purchase in next } H \text{ days} \mid X_{c,t})$$
— using only data up to a historical cutoff, will the customer return within
60/90 days.

**Strategy optimization** — for each candidate action $a$:
$$U(a) = E[\text{Incremental Profit}] - \text{Action Cost} - \lambda \cdot \text{Risk}$$
subject to: available budget, storage capacity, supplier lead time, minimum
order quantity, customer contact consent, current and incoming stock. The
system recommends the practical actions with highest utility.

## 3. Proposed framework: B-SMART

**B-SMART: Bangladesh SME Monitoring, Analytics, Recommendation and Tracking
Framework.** Not a new classifier — novelty is the leakage-free,
Bangladesh-context-aware, end-to-end decision-support pipeline. (Freeze the
final name only after the literature search confirms no naming conflict.)

Sequential flow:

```
Real SME Data
    → Validation, Cleaning and Tenant Isolation
    → Canonical Transactional Database
    → Historical Feature Snapshots
    → Forecasting + Churn + Segmentation
    → Uncertainty and Explainability
    → Business Constraint Engine
    → Expected-Utility Action Ranking
    → Bangla Action Dashboard
    → Owner Feedback and Outcome Tracking
```

Pseudocode:

```
Algorithm: B-SMART Strategy Recommendation

Input:  Business data D, forecast horizon H, business constraints C,
        trained model versions M, available action set A
Output: Ranked actionable recommendations R

1.  Validate schema, timestamps, tenant ownership, missing values
2.  Build time-aware feature snapshot X_t
3.  Predict SKU demand and prediction intervals
4.  Predict future customer inactivity probabilities
5.  Calculate current business KPIs and abnormal deviations
6.  Generate eligible actions from forecasts, risks, and KPIs
7.  For each action a in A:
        estimate benefit(a), cost(a), risk(a); verify constraints C
        utility(a) ← benefit(a) - cost(a) - λ · risk(a)
8.  Remove infeasible actions
9.  Rank remaining actions by utility
10. Attach explanation, confidence, and supporting evidence
11. Return top-K recommendations
12. Record user response and eventual business outcome
```

This already exists as a rough draft in `api/analytics_routes.py`'s
recommendation engine — the next step is replacing its current heuristics
with steps 3–4 output once real-data models exist (see Current Priority).

## 4. Worked example

| Product | Last 7-day sales | Current stock | Lead time | Predicted 7-day demand |
|---|---|---|---|---|
| Soybean Oil | 30 | 12 | 4 days | 34 |
| Rice 5kg | 18 | 40 | 3 days | 20 |
| Sugar 1kg | 25 | 8 | 5 days | 29 |

Soybean Oil, safety stock 6: $\text{Reorder} = 34 + 6 - 12 = 28$.

System output (Bangla): *"আগামী সাত দিনে Soybean Oil-এর সম্ভাব্য demand
৩০–৩৮ unit। বর্তমান stock ১২ এবং supplier lead time চার দিন। Stockout এড়াতে
আজ প্রায় ২৮ unit order করার পরামর্শ।"* The full worked example in the thesis
must show input, intermediate calculation, model output, and the final
recommendation — not just the final number.

## 5. Research questions and hypotheses

1. Do Bangladesh-aware calendar, price, promotion, and market features
   improve branch–SKU demand forecasts over seasonal and statistical
   baselines?
2. How accurately and reliably can temporal customer snapshots predict no
   repeat purchase in the following 60/90 days?
3. Does a forecast-driven reorder policy reduce simulated and pilot-observed
   stockouts and holding cost against the owner's existing policy?
4. Do Bangla action explanations improve owner task completion, confidence,
   and perceived usability?

## 6. Chapter structure

**Chapter 1 — Introduction.** Motivation opens on a concrete Bangladeshi SME
scenario: ledger/Excel bookkeeping, failing to anticipate Eid/Ramadan demand,
stockouts and dead stock, losing a customer without noticing, and financing
difficulty from lacking formal financial statements. Objectives,
contributions, challenges (see §9 below for a research-backed challenge
list), and a chapter-by-chapter organization summary.

**Chapter 2 — Related Works** (matches the LaTeX template's own chapter file
name — see [THESIS_REPORT_WRITING_GUIDE.md](THESIS_REPORT_WRITING_GUIDE.md)
for the exact template mapping; this is one chapter with three subsections,
not two separate chapters). Background study covers SME/CMSME
definitions, BI, RFM/CLV, time-series forecasting, churn/survival analysis,
segmentation, market basket analysis, explainable AI, inventory
optimization, MLOps/drift/calibration, and Bangladesh payment/business
context. Literature review: minimum 20 papers at proposal/defence stage,
40+ in the final thesis, distributed as:

| Area | Now | Final |
|---|---|---|
| Bangladesh SME/digitalization | 4 | 7 |
| Retail forecasting/inventory | 5 | 9 |
| Churn/customer analytics | 3 | 6 |
| Segmentation/recommendation | 3 | 5 |
| Explainable/responsible AI | 2 | 5 |
| Business decision support | 2 | 4 |
| Production ML/scalability | 1 | 4 |
| **Total** | **20** | **40+** |

Per paper: problem, dataset/context, method, main result,
limitation/relevance — plus a literature matrix (country/sector, real vs
synthetic data, sample size, features, algorithms, baselines, metrics,
contribution, limitations, gap addressed by B-SMART). Existing-system
limitation table (generic ERP/POS lacks predictive support; standalone
forecasting papers skip the operational workflow; synthetic retail studies
have weak real-world validity; random splits leak; accuracy-only papers skip
business value; black-box models lose owner trust; foreign retail data
misses Bangladesh context; one global model hides store differences — each
row paired with B-SMART's answer). Citation style: `\cite{paper_key}` for
sources, `\ref{}` reserved for figures/tables/sections/equations.

**Chapter 3 — Proposed Methodologies** (template file: `proposedMethod.tex`).
Research questions/hypotheses, target SME population, data acquisition and
ethics, database schema, preprocessing, historical feature snapshots, model
definitions, the B-SMART algorithm (pseudocode + complexity analysis +
worked example), architecture/data-flow/sequence diagrams, evaluation
protocol.

**Chapter 4 — Implementation** (template file: `implementations.tex`). What
was actually built and how — system architecture realized in code (the
Business Operations / AI Analytics / Strategy Optimization layers), tech
stack, database schema as implemented, the B-SMART pipeline wiring
end-to-end. This chapter describes the system, not its results — experiment
outcomes belong in Chapter 5.

**Chapter 5 — Experimental Results** (template file: `experimentalResults.tex`,
sections 5.1 Results Analysis, 5.2 Summary of the Experimental Results).
This is where every experiment design below is actually run and reported:
- *Datasets*: real SME dataset, Bangladeshi public contextual datasets,
  external real benchmark (labelled non-Bangladeshi if used — see
  [CLAUDE.md](../CLAUDE.md)'s note on `candidate_datasets_not_used/`),
  synthetic scalability dataset (labelled separately, never merged into
  accuracy tables).
- *Forecast comparison*: seasonal-naive, moving average/ETS, Croston,
  SARIMA, XGBoost/LightGBM/CatBoost, LSTM/TFT/N-HiTS (only if data volume
  justifies). Metrics: WAPE, MASE/RMSSE, RMSE, prediction interval coverage,
  stockout cost, holding cost.
- *Churn comparison*: business-rule baseline, Logistic Regression, Random
  Forest, XGBoost/CatBoost, a survival model. Metrics: PR-AUC, ROC-AUC,
  Lift@10%, Brier score, calibration, campaign profit.
- *Ablations*: without Bangladesh calendar features; without market-price
  data; without price/promotion; without customer features; global vs
  store-specific model; real-only vs real-plus-controlled-augmentation.
- *Scalability and market-basket experiment* (§7 below) also gets reported
  here once the underlying algorithm exists — see
  [THESIS_REPORT_WRITING_GUIDE.md](THESIS_REPORT_WRITING_GUIDE.md) §5 for why
  that part is currently blocked.
- Business interpretation, threats to validity, and ethics discussion close
  out this chapter.

**Chapter 6 — Conclusions** (template file: `conclusions.tex`, sections
6.1 Research Summary, 6.2 Future Work Plan).

## 7. Scalability and algorithm experiments

Keep the supervisor's 100/500/1,000 requirement, but strengthen it with
larger scales — matches what `ml/scalability_benchmark.py` already
parameterizes:

100 · 500 · 1,000 · 10,000 · 100,000 · 1,000,000 transaction rows

Measure: data import time, preprocessing time, training time, prediction
latency, API throughput, peak memory, model artifact size, database query
latency.

For any market-basket/association-rule component: minimum support ∈
{0.01, 0.02, 0.05, 0.10}, runtime, memory footprint, number of generated
rules, rule quality — plotted as minimum support (x) vs runtime/memory/rule
count (y). **Report whatever the experiment produces; do not pre-write the
expected trend.**

## 8. Formal presentation structure

Title page → TOC → system/result overview diagram → motivation and
real-world scenario → objectives → contributions → challenges → background →
literature review → literature gap table → problem formulation → proposed
B-SMART framework (architecture, sequential flow, pseudocode, worked
example) → dataset and ethics → experimental setup → preliminary/current
results → scalability plan → product screenshots → timeline/Gantt chart →
expected outcomes → limitations → references. Academic and
citation-supported throughout — no marketing-style claims.

## 9. Research grounding for motivation and existing-system-limitation sections

Quick findings to cite properly once the full literature matrix is built
(each needs its own `\cite{}` entry, not just this summary):

- SME digital maturity across accounting, inventory, online sales, digital
  payments, and ERP integration averages only ~0.45 on a 0–1 scale in
  Bangladesh — moderate adoption, large headroom. ([Tipsoi — SME Digitization
  in Bangladesh](https://tipsoi.pro/sme-digitization-in-bangladesh/))
- Stock-outs and overstocking from poor demand forecasting are linked to a
  large share of e-commerce/retail business failures in Bangladesh's 2025
  market. ([devzcart — 2025 Reality Check](https://devzcart.com/blog/the-2025-reality-check-bangladeshs-e-commerce-boom-the-hidden-inventory-crisis))
- Only ~36% of Bangladeshi SMEs have access to formal credit, versus 48% in
  South Asia and 68% in East Asia & Pacific, largely because of missing
  financial records/collateral/documentation — the World Bank's stated
  motivation for formal, verifiable business records.
  ([World Bank — Financing Solutions for MSMEs in Bangladesh](https://documents1.worldbank.org/curated/en/995331545025954781/Financing-Solutions-for-Micro-Small-and-Medium-Enterprises-in-Bangladesh.pdf);
  [World Bank — MSME Finance Gap](https://documents1.worldbank.org/curated/en/653831510568517947/pdf/121264-WP-PUBLIC-MSMEReportFINAL.pdf))
- Mobile financial services (bKash, Nagad, Rocket, Upay) dominate SME/retail
  payment settlement, with cashless/wallet payments expected to cover most
  online purchases — directly motivates why B-SMART's `Payment` model treats
  bKash/Nagad/Bangla QR as first-class channels, not an afterthought.
  ([WJAETS — Impact of Mobile Financial Services in Bangladesh](https://wjaets.com/sites/default/files/fulltext_pdf/WJAETS-2025-1290.pdf))
- Barriers to SME digital-technology adoption post-COVID (cost, skills,
  infrastructure, trust) are documented specifically for Bangladesh, useful
  for the "non-technical user adoption" challenge and for justifying a
  Bangla-first, low-friction UI over a generic English dashboard.
  ([UniversePG — Adoption of Digital Technologies in Bangladeshi SMEs](https://www.universepg.com/cjbis/adoption-of-digital-technologies-in-bangladeshi-smes-barriers-enablers-and-strategic-responses-post-covid-19))
- On the ML side, recent retail-forecasting literature (2024–2025) shows a
  continued shift from purely statistical methods (SARIMA) toward
  ensemble/tree methods and hybrid deep-learning models for demand
  forecasting, and flags overfitting/compute cost as the reason many papers
  now prefer ensembles over deep nets on limited data — relevant to
  justifying B-SMART's baseline ladder (seasonal-naive → ETS/SARIMA →
  gradient boosting → LSTM/TFT only if data volume justifies it).
  ([MDPI — ML/DL for Demand Forecasting in Supply Chain: Critical Review](https://www.mdpi.com/2571-5577/7/5/93);
  [arXiv — Retail Demand Forecasting: Comparative Study](https://arxiv.org/pdf/2308.11939))

These are leads for the literature matrix, not finished citations — read each
source fully, extract its own dataset/method/result/limitation, and write an
original synthesis per the academic-integrity rules in §10. Do not cite the
summary above as if it were the paper.

## 10. Originality, plagiarism, and AI-use rules

Supervisor's targets: similarity/plagiarism ≤ 20%, AI-related ≤ 10%.
Workflow to meet them:

- No sentence copied from a source paper; read and understand first, then
  write an original synthesis.
- Every borrowed idea, dataset, or figure is cited; direct quotes only when
  necessary.
- No fabricated citation, result, or dataset — ever.
- Maintain a Zotero/BibTeX reference library.
- Figures, tables, pseudocode, and analysis are authored by the team, not
  copied from a source.
- Audit the final draft with Turnitin or the university-approved checker.
- AI-generated draft text is never pasted directly into the thesis; the
  authors verify, rewrite, and can defend every sentence.
- Disclose AI assistance if university policy requires it.
- No AI-detector score can be guaranteed, and no detector-evasion technique
  should be used — the goal is genuinely original, verifiable,
  student-understood writing, not passing a specific score.

## Current priority (execution order)

1. Freeze the target retail sector.
2. Build the consent form and real-data collection template
   (`docs/REAL_DATA_PROTOCOL.md` already drafts this — finalize it).
3. Build the 20-paper literature matrix (use §9 as a starting point, not a
   finished bibliography).
4. Freeze the problem formulation and B-SMART framework/name.
5. Finish the database/architecture migration (see [CLAUDE.md](../CLAUDE.md)
   for what's already built vs. remaining — e.g. the JWT/login gap, the
   import-UI now wired to `data_import_routes.py`).
6. Run leakage-free experiments on real data once §2 collection completes.
7. Run scalability, usability, and business-impact evaluation (§7).

This keeps the proposal's original promise, the supervisor's academic
requirements, and a production-grade product consistent within one thesis.
