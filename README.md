# B-SMART — Bangladesh Business OS

**Website:** https://thesis-j0n8.onrender.com
**Online stores:** https://thesis-j0n8.onrender.com/#/stores
**NEW Cloudflare D1 owner dashboard:** https://thesis-j0n8.onrender.com/#/d1-owner

## Current status (9 November 2026)

The React website is deployed on Render and the Cloudflare Worker `bsmart-commerce-api` has been deployed with the production multi-store upgrade. The Worker URL is https://bsmart-commerce-api.bcs-written-rakib.workers.dev . Cloudflare D1 `bsmart-commerce` remains the authoritative store/customer/order/inventory database for the D1 storefront.

Current `bsmart-commerce` D1 data: 10 **fictional sample shops** with 259 sample products, plus one retained POS CI fixture with one test product. There are three test orders, three order lines, three inventory movements, one test cashbook receipt and one legacy CI merchant account. All 11 stores are inactive and marked `is_demo=1`; therefore the public D1 store directory correctly returns zero stores and zero listed public products. There are no verified real merchant-owned operational stores and no D1 customer accounts. Existing records are preserved. These are **not** the previously removed 32 research shops or restored real businesses. Do not present sample data as real trading activity or collect payments from these sample shops.

The D1 owner console has **a separate account system**. New owner accounts use PBKDF2-HMAC-SHA-256 password hashes (100,000 iterations); legacy one-time access-key accounts remain compatible. Owners can create a private operational-store draft, manage products and stock, see orders and use demo POS/cashbook tools. Platform Admin approval is required before a merchant-owned store can become public and accept COD orders. Owner email verification and password recovery are implemented and deployed, but registration remains safely disabled until a verified Resend sender and `RESEND_API_KEY` are configured. Merchant identity validation is still required before operational publication. The old FastAPI business login will **not** sign in to the D1 owner console. The separate Cloudflare D1 database named `bcs-written` contains study-content records and is not the B-SMART commerce database; do not mix it with `bsmart-commerce`.

**Important: Original full business system has not been migrated.** The original extensive FastAPI + SQLAlchemy modules — actual POS/cash, accounting, CRM/customer profiles, staff, coupons, chat, invoicing, supplier/inventory procurement, financing and historical merchant records — still use the old operational database, last verified running on ephemeral SQLite on Render. This old data is **not** synced with the new D1 demo slice, and cannot be declared persistent through Cloudflare. Changing only `DATABASE_URL` to a D1 identifier is not a working migration.

The user's original local ZIP lacked the primary `bsmart.db` and contained only `bsmart.db-wal` / `bsmart.db-shm`. The connected R2 research bucket held setup metadata, not a complete merchant-data backup. Real historic orders/customers cannot be restored without a valid database/backup.

## Production upgrade deployment (8 November 2026)\n\n- [Merged production upgrade PR #20](https://github.com/RlM100always/Thesis/pull/20)\n- [Production CI: frontend, backend, D1 schema and Worker checks](https://github.com/RlM100always/Thesis/actions/runs/42443796673)\n- [Cloudflare Worker deployment](https://github.com/RlM100always/Thesis/actions/runs/42443796647)\n- Render deployment commit: `3cc005fd46f048fd5dcece1f072abbda36ce72c4` (live)\n- Cloudflare D1 schema version: **12** (migrations 0009–0012 applied after schema inspection and export)\n- Cloudflare Worker version: `836c5aa8-0c51-482a-bb01-29432d8d1f38` (100% deployment)\n\nThe Worker AI binding is present, but model inference is disabled by default. Assistants use deterministic database-grounded fallback answers until `AI_ENABLED=true` is deliberately configured. Owner email flows remain unavailable until the Resend provider is configured.\n\n## Implementation and verification

- [Cloudflare D1 source, Worker, migrations and technical status](cloudflare/README.md)
- [Legacy data recovery precautions](docs/STOREFRONT_DATABASE_RECOVERY.md)
- [Cloudflare D1 Worker live smoke checks](https://github.com/RlM100always/Thesis/actions/runs/40326438876) — owner-created shop preview and transactional demo POS reconciliation passed
- [D1 access-key owner signup and stock CRUD tests](https://github.com/RlM100always/Thesis/actions/runs/40325162409)
- [Demo order cancellation and stock rollback](https://github.com/RlM100always/Thesis/actions/runs/40318406288)

For the backend local developer environment:

```bash
pip install -r requirements.render.txt
python run_api.py
cd frontend
npm ci && npm run dev
```

The D1 commerce platform and legacy FastAPI operational system remain separate. The legacy FastAPI operational database has not been migrated; it was last verified as ephemeral SQLite on Render. Do not claim historical POS, accounting, CRM or purchasing data is in D1.


## Production upgrade tracking

- [Step-by-step production implementation plan](docs/PRODUCTION_IMPLEMENTATION_PLAN.md)
- [Store owner access register (no passwords or secrets)](docs/STORE_ACCESS_REGISTER.md)
- [Deployment, verification and rollback runbook](docs/DEPLOYMENT_RUNBOOK.md)

The implementation plan distinguishes existing functionality from work still required. Do not treat sample catalogue stores as real merchants, and never publish owner passwords, platform-admin keys, API tokens or payment secrets in this public repository.

## Research, report and software work status

This repository now records the complete work sequence for the thesis: dataset
audit, four research-question experiments, report preparation, result figures,
and the B-SMART software/tool implementation. The detailed research log is in
[`research/experiments/README.md`](research/experiments/README.md), while the
forecasting-specific methods and outputs are in
[`research/forecasting/README.md`](research/forecasting/README.md).

### 1. Research workflow

| Step | Current status | Evidence or output |
|---|---|---|
| Dataset acquisition and audit | Completed with limits recorded | Researcher-provided real Bangladesh SME dataset; structural joins, sales totals, inventory movements and labels were reconciled. Source provenance and physical-stock provenance remain unverified. |
| RQ1 — demand forecasting | Leakage-safe experiments completed | Six-date shop-category validation, frozen Q4 tail stress check, baseline comparison, regime-wise WAPE and actual-versus-predicted graphs. Corrected six-date HGB WAPE: **32.57%**; frozen context model WAPE: **33.45%**. |
| RQ2 — customer inactivity | Completed on temporal snapshots | Label reconstruction matched 72,146 rows; PR-AUC, ROC-AUC, Brier score, top-decile lift and bootstrap lift intervals reported. Mean top-decile lift: **2.06x**. |
| RQ3 — replenishment | Historical backtest and scenario comparison completed | Eight observed-sales cutoffs, cost decomposition, low-stock subset and 0/2/5/10% holding-cost sensitivity. Trend cost change: **+0.54%**; lost units: **0 vs 0**. Actual owner-policy replay is still required. |
| RQ4 — explanation evaluation | Computational audit completed; human study open | 1,800 rule-test cases pass mechanical checks at 100%. Validated participant responses: **0**. No human usability or decision-accuracy claim is made. |
| Integrated analysis | Completed | SME-owner interpretation, evidence boundaries, limitations, simple result graphs and a four-RQ overview figure added. |

No single overall “accuracy score” is used. Forecasting, classification,
replenishment cost and explanation usability use different valid metrics.

### 2. Report-making workflow

`thesis_report/main.tex` is the active report source. The report now contains:

- dataset profile and experiment-design rationale;
- leakage-safe RQ1 results and regime-wise error analysis;
- RQ2 ranking, lift and uncertainty results;
- RQ3 historical cost, low-stock and sensitivity analysis;
- RQ4 mechanical-evidence versus human-study boundary;
- simple reader-facing figures and the integrated results overview;
- SME owner meaning, novelty, limitations and remaining validation steps.

Important report files:

- [`thesis_report/main.tex`](thesis_report/main.tex) — active report source;
- [`thesis_report/BUILD.md`](thesis_report/BUILD.md) — build instructions;
- [`thesis_report/Figures/`](thesis_report/Figures/) — report figures;
- [`research/experiments/results/multidate_business_impact/`](research/experiments/results/multidate_business_impact/) — cross-RQ result tables;
- [`research/forecasting/results/rq1_frozen_tail_v1/`](research/forecasting/results/rq1_frozen_tail_v1/) — frozen-tail RQ1 metrics.

Build from the repository root:

```bash
cd thesis_report
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The source and figures are updated. The local execution environment currently
lacks the TeX format files (`pdflatex.fmt`/`xelatex.fmt`), so local PDF
compilation is blocked; the repository workflow remains the intended PDF build
path.

### 3. Software and tool implementation workflow

| Software area | Current status | Main location or URL |
|---|---|---|
| Public React storefront | Deployed and smoke-tested | https://thesis-j0n8.onrender.com |
| Store directory | Implemented with inactive demo-store protection | `frontend/`, `#/stores` |
| Cloudflare Worker API | Deployed as `bsmart-commerce-api` | `cloudflare/`, Worker URL in the deployment section above |
| Cloudflare D1 commerce database | Schema and migrations deployed; demo records preserved and clearly marked | `cloudflare/migrations/`, D1 database `bsmart-commerce` |
| Business-owner console | Separate owner account, PBKDF2 password hashing, private store draft, product/stock/order tools and admin approval flow implemented | `frontend/` and `cloudflare/` owner routes |
| Inventory and POS tools | Demo stock CRUD, order flow, stock movement and cashbook reconciliation tested | Cloudflare Worker live-smoke workflows |
| AI assistant | Worker binding exists; deterministic database-grounded fallback is active while model inference is disabled by default | `cloudflare/` assistant routes |
| Admin and deployment controls | Approval, access-register, migration and rollback documentation maintained | [`docs/PRODUCTION_IMPLEMENTATION_PLAN.md`](docs/PRODUCTION_IMPLEMENTATION_PLAN.md), [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md) |
| Legacy FastAPI system | Still separate from D1; historical POS, CRM, accounting and purchasing data are not claimed to be migrated | `api/`, `run_api.py` |

The D1 sample shops are fictional demo records, not verified merchants. The
legacy FastAPI database and the D1 commerce database must not be treated as one
shared historical dataset.

### 4. Reproducibility sequence

To reproduce the current thesis evidence, use this order:

1. Keep the raw Drive export outside Git and run the source audits.
2. Run the RQ1--RQ4 experiment scripts in `research/experiments/`.
3. Run `research/experiments/run_multidate_business_impact.py` for the cross-RQ date-level outputs.
4. Run `research/forecasting/run_final_holdout.py` for the frozen-tail RQ1 check.
5. Run `research/experiments/build_thesis_results_overview.py` to regenerate the overview figure.
6. Rebuild `thesis_report/main.tex` and inspect the figures before submission.
7. Run the software checks and deployment smoke tests only against demo or approved operational data.

### 5. Remaining research and delivery steps

- reserve and evaluate one genuinely untouched future period or held-out business for the final RQ1 claim;
- validate reconstructed stock exposure with owner-approved physical-stock records;
- calibrate RQ2 probabilities and, if possible, measure a retention action with a consented intervention design;
- collect a participating owner's actual reorder policy and validated purchase, holding and lost-sales costs for RQ3;
- run the consented SME participant study required for RQ4, measuring task accuracy, completion time, confidence and usability;
- compile and visually inspect the final PDF through the configured TeX/CI environment;
- complete production migration only after the legacy database backup and merchant identity/approval requirements are satisfied.

The current implementation is therefore reproducible and report-ready for the
available evidence, but the remaining owner-policy, blind-holdout and human
participant steps must be completed before making causal business-impact or
human-usability claims.

Latest research branch: [codex/complete-rq-experiments-20261109](https://github.com/RlM100always/Thesis/tree/codex/complete-rq-experiments-20261109)
