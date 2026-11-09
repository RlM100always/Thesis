# B-SMART — Bangladesh Business OS

**Website:** https://thesis-j0n8.onrender.com
**Online stores:** https://thesis-j0n8.onrender.com/#/stores
**NEW Cloudflare D1 owner dashboard:** https://thesis-j0n8.onrender.com/#/d1-owner

## Current status (10 November 2026)

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

## Research, report, and software completion record

This repository now contains the current reproducible research record and the
corresponding LaTeX progress report. The report is complete as an **initial
thesis progress report**: it documents the four research questions, the
available experiments, the leakage-safe validation design, the owner-facing
interpretation of the results, and the evidence limits. It is not a claim that
the whole research programme is finished; the remaining evidence is listed
explicitly below.

### Research workflow and current evidence

| Area | Current work recorded | Current evidence boundary |
|---|---|---|
| RQ1 demand forecasting | Exposure-aware SKU audit, fixed-origin model comparison, six-date leakage-safe shop-category validation, frozen-tail stress check, regime-wise analysis, and actual-versus-predicted figures | A blind final holdout and independent physical-stock validation are still required before a final deployment claim |
| RQ2 customer inactivity | Temporal split, model comparison, PR-AUC/ROC-AUC/Brier, top-risk-decile lift, six-date rolling validation, and customer-cluster bootstrap intervals | Ranking and campaign prioritisation are supported; causal retention impact and final probability calibration are not yet measured |
| RQ3 replenishment | Eight-date observed-sales backtest, baseline-versus-trend policy comparison, low-stock slice, holding-cost sensitivity, service/cost interpretation, and owner-impact graphs | Owner's actual policy, validated cost inputs, and realised owner outcomes are still required; the separate 2,500-row scenario file is assumption-based |
| RQ4 explanation evaluation | 1,800-case mechanical explanation audit, constraint checks, and evidence-boundary graph | Validated participant responses are 0; human usability, confidence, task accuracy, and completion-time results are not claimed |

### Reader-facing result summary

| RQ | Main measured result | Correct interpretation |
|---|---|---|
| RQ1 | Leakage-safe six-date HGB WAPE **32.57%**, versus 28-day mean **39.33%** and weekly naive **46.06%**; frozen-tail context check **33.45%** | The model is useful for short-horizon planning in this panel, but the final claim still needs a blind holdout and validated stock exposure |
| RQ2 | Test PR-AUC **0.746**, ROC-AUC **0.830**, and mean highest-risk-decile lift **2.06x** with bootstrap uncertainty | The model can rank a smaller retention list; it does not prove that a retention action causes extra purchases |
| RQ3 | Eight-date observed-sales backtest: trend policy cost change **+0.54%** and lost units **0 vs 0**; trend cheaper at 3 dates and more expensive at 5 | The recommendation is a cost/service comparison, not guaranteed profit; owner's actual policy and validated costs are still missing |
| RQ4 | **1,800/1,800** mechanical explanation checks passed; validated participant responses **0** | The explanation rules are internally consistent, but no human usability result is claimed |

These figures are intentionally shown as separate metrics. Forecasting error,
classification ranking, replenishment cost and explanation usability answer
different questions and must not be collapsed into one overall score.

Run instructions and saved aggregate outputs are documented in
`research/experiments/README.md` and `research/forecasting/README.md`. Raw
customer, order, inventory, and scenario files remain outside GitHub. The
researcher-provided real dataset folder is recorded in those READMEs:

<https://drive.google.com/drive/u/0/folders/1ET_on20yEu4z2_P-sRRECt1ZGUC6vphz>

The principal saved result locations are:

- `research/experiments/results/multidate_business_impact/`
- `research/forecasting/results/rq1_frozen_tail_v1/`
- `research/experiments/results/rq1_exposure_aware_20261109/`
- `research/experiments/results/rq2_customer_prediction/`
- `research/experiments/results/rq3_scenario_comparison/`
- `research/experiments/results/rq4_explanation_case_audit/`
- `thesis_report/Figures/`
- `research/experiments/build_reader_figures.py` (rebuilds the six compact result graphs from the saved CSV aggregates)

### Report-making workflow

- LaTeX master source: `thesis_report/main.tex`
- Chapter and appendix sources: `thesis_report/Chapters/` and
  `thesis_report/Appendices/`
- Report figures: `thesis_report/Figures/`
- Build notes: `thesis_report/BUILD.md`
- Current compiled PDF: `output/pdf/main-thesis-report.pdf`

The current PDF was compiled from the updated master source, checked as an A4
document with exactly **70 pages**, and visually inspected for the cover,
tables, figures, headers, page numbers, and section transitions. Repeated
result tables were replaced by direct graphs where a visual comparison is
clearer: RQ1 origin/context WAPE, RQ2 model comparison and targeting lift,
and RQ3 scenario trade-off and historical demand backtest. The report presents
the result in a reader-facing order: dataset profile, experiment design,
simple result graph, business meaning, and limitation for each RQ. It does
not combine forecasting, inactivity, replenishment, and explanation into one
misleading accuracy score.

To rebuild after changing the source, use the commands in `thesis_report/BUILD.md`
with a complete TeX Live installation. The checked-in PDF is the current
compiled artifact; auxiliary TeX files and private data exports are not
committed.

The standard build sequence is:

```bash
cd thesis_report
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The final checked-in PDF was built from this source with the report figures
embedded at publication-readable resolution. The source keeps the detailed
audit/model appendices available for reproducibility, while the reader-facing
PDF omits those long appendices to meet the 70-page limit.

### Software/tool workflow

The research package is separate from the operational B-SMART application.
The application work currently includes the React storefront on Render, the
Cloudflare Worker API, the Cloudflare D1 commerce schema, owner console,
inventory/POS and admin flows, deterministic assistant fallback, CI checks,
deployment runbook, and legacy FastAPI separation notes. The D1 demo records
are explicitly marked as fictional sample shops and must not be presented as
real trading activity. The original FastAPI operational database has not been
migrated into D1.

The end-to-end project sequence is:

1. Keep the private Drive export outside GitHub and run the source audits.
2. Run the RQ1--RQ4 experiment scripts and the multi-date owner-impact runner.
3. Regenerate figures and aggregate result files.
4. Update `thesis_report/main.tex`, compile and inspect the PDF.
5. Run the software tests and deployment checks documented in `cloudflare/`
   and `docs/`.

### Remaining work before a final thesis claim

The current report is ready as a progress-report deliverable, but the final
thesis evidence still needs: a truly untouched RQ1 holdout or held-out
businesses, validated stock exposure and cost data, a documented owner-policy
replay for RQ3, probability calibration for RQ2, and a consented participant
study for RQ4. These gaps are stated in the report rather than hidden behind
the PDF or the software interface.
