## RQ2 threshold refinement v2 — 23 November 2026

- Reused the controlled snapshot and sales-order exports whose SHA-256
  hashes match the recorded RQ2 inputs. Target reconstruction agreement
  remained 100% across 72,146 snapshots.
- Compared the original CatBoost feature set with a past-only trajectory
  extension on the first two rolling-origin TRAIN folds. The original
  feature set was retained because its pooled PR-AUC (0.6990) was marginally
  higher than the trajectory variant (0.6988).
- Fitted Platt calibration on the first two TRAIN origins and reserved
  31 December 2024 as the threshold-selection origin. The selected rule
  maximises precision subject to TRAIN-origin recall of at least 85%;
  threshold 0.317603. TEST labels were not used for threshold selection.
- On the 21,164 TEST snapshots, precision is 0.6064, recall 0.8866,
  F1-score 0.7202, PR-AUC 0.7461 and ROC-AUC 0.8314. The confusion counts
  are TN 7,432, FP 5,016, FN 988 and TP 7,728.
- Compared with the v1 F2-maximising operating point, false positives fall
  by 2,153 (30.0%); recall falls by 7.32 percentage points and false
  negatives rise by 638. This is an explicit operating-point trade-off,
  not a material improvement in ranking discrimination.
- The latest TEST snapshot per 10,613 unique customers gives precision
  0.6172, recall 0.9035 and F1-score 0.7334.
- The TEST set was already evaluated in v1. The v2 TEST results are a
  repeated-holdout diagnostic and must not be described as a pristine
  independent confirmation. A later untouched period is required.
- Added aggregate-only outputs under
  `research/experiments/results/rq2_customer_prediction_v2/`. No raw
  customer data, customer identifiers or row-level predictions were
  committed.
- GitHub Actions research tests: **37 passed** in 3.95 seconds
  ([run 45236982573](https://github.com/RlM100always/Thesis/actions/runs/45236982573)).
- LaTeX report build: successful; **88 A4 pages**, 636,671 bytes
  ([run 45236025825](https://github.com/RlM100always/Thesis/actions/runs/45236025825)).
- RQ1, RQ3 and RQ4 experimental outputs and conclusions were not changed.

## RQ2 classification-metric extension — 23 November 2026

- Re-executed the RQ2 pipeline using the supplied snapshot export and order
  history; the recorded SHA-256 hashes and 72,146-row label reconstruction
  agreement remained unchanged.
- Added test-set F1-score, per-model aggregate confusion matrices and a
  21-point ROC-curve export for the selected CatBoost model. No row-level
  customer predictions or identifiers are written to the repository.
- CatBoost TEST results at the training-selected threshold 0.153927:
  precision 0.5385, recall 0.9598, F1-score 0.6900 and ROC-AUC 0.8313.
- CatBoost confusion matrix (actual rows; predicted columns; positive class
  is inactivity): active/active 5,279; active/inactive 7,169;
  inactive/active 350; inactive/inactive 8,366.
- The threshold remains selected from calibrated rolling-origin TRAIN
  predictions. TEST is used only for final evaluation.
- The existing 500-resample customer-cluster bootstrap intervals were
  retained because the rerun reproduced the same deterministic TEST metrics.
- Research contract tests: 7 passed locally, including the new F1 and
  confusion-count test. GitHub Actions research tests: successful, run
  [45221453888](https://github.com/RlM100always/Thesis/actions/runs/45221453888).
- LaTeX build: successful, run
  [45221403503](https://github.com/RlM100always/Thesis/actions/runs/45221403503).
  Final PDF: 87 A4 pages, 634,662 bytes; published at
  `output/pdf/main-thesis-report.pdf`.
- Visual QA: the updated RQ2 classification comparison, ROC curve and
  confusion-matrix figures were rendered and inspected on report pages 61--63.
  Labels, axes, counts and captions are visible without clipping or overlap.

## Academic language revision — 23 November 2026

- Revised the active report source and included RQ1--RQ4 chapters to use
  formal academic terminology, precise comparative statements and consistent
  British English in authored prose.
- Replaced informal or product-oriented expressions, including
  "owner-facing", "task-friendliness", "low-friction", "challenger" and
  "model wins", with terms that describe the evaluated concepts and metrics.
- Aligned the RQ4 research question and study-status statements with
  `docs/RQ4_USER_STUDY_PROTOCOL.md`; the participant study is still planned
  and is not reported as completed.
- Corrected outdated report-structure and methodological-output text to
  reflect the implemented system and the empirical results now included.
- Clarified that dataset provenance is reported from the supplied manifest
  and has not been independently verified through a field audit.
- Experimental metrics, model outputs, source citations and figure data were
  retained; the edits were to report wording and presentation.
- LaTeX build: successful, GitHub Actions run
  [45207685117](https://github.com/RlM100always/Thesis/actions/runs/45207685117).
- Research contract tests: successful, run
  [45207684975](https://github.com/RlM100always/Thesis/actions/runs/45207684975).
- Final PDF: 85 A4 pages, 623,923 bytes, published at
  `output/pdf/main-thesis-report.pdf`.

## Expanded research-figure revision — 23 November 2026

- Added 15 further data-backed figures across RQ1--RQ4 and improved two
  existing figures. The compiled report now contains 25 figures in total.
- RQ1 additions: demand-regime distribution, nine-origin paired comparison,
  context-versus-baseline horizon comparison, regime-level model comparison,
  prequential interval coverage, hierarchy-level WAPE and cluster-bootstrap
  uncertainty.
- RQ2 additions: calibration reliability, test-date discrimination and
  customer-cluster bootstrap intervals. The feature-importance figure now
  shows the ten leading predictors.
- RQ3 additions: shop-cluster bootstrap intervals for all four scenario
  outcomes and paired-case outcome counts.
- RQ4 additions: generated bilingual branch coverage, decision/action counts
  and exact rule-output agreement. The supplied explanation coverage figure
  now includes all eight audited numerical fields.
- Visual review: the new charts on report pages 55--63 were rendered and
  checked. Legend spacing and clipped axis titles were corrected.
- Final LaTeX build: successful, GitHub Actions run
  [45207685117](https://github.com/RlM100always/Thesis/actions/runs/45207685117).
- Research contract tests: successful, run
  [45207684975](https://github.com/RlM100always/Thesis/actions/runs/45207684975).
- Final PDF: 85 A4 pages, 623,923 bytes. Published at
  `output/pdf/main-thesis-report.pdf` and uploaded as the
  `main-thesis-report-pdf` Actions artifact.

# Verification record

## RQ1–RQ4 integration and final report build — 23 November 2026

- The updated LaTeX report is compiled from `thesis_report/main.tex` and keeps
  the existing University of Dhaka report layout.
- GitHub Actions LaTeX build: successful, run
  [45136998684](https://github.com/RlM100always/Thesis/actions/runs/45136998684).
  Final PDF: 77 A4 pages, 585,929 bytes. It is published at
  `output/pdf/main-thesis-report.pdf` and uploaded as the
  `main-thesis-report-pdf` Actions artifact.
- Research contract tests: successful, run
  [45136998715](https://github.com/RlM100always/Thesis/actions/runs/45136998715).
  Local test suite: 6 passed.
- RQ1: nine-origin seven-day context-aware LightGBM development WAPE is
  32.66% versus 33.47% for the historical baseline; under-forecast bias
  increases in magnitude from -2.02% to -6.05%. This is not an untouched
  final-test or production claim.
- RQ2: 72,146 snapshots across 10,613 customers; the 90-day no-repeat label
  was reconstructed with 100% agreement. CatBoost TEST PR-AUC is 0.7470,
  ROC-AUC 0.8313 and Brier 0.1647. Repeated customers overlap across the
  temporal split, so this is not cold-start or causal campaign evidence.
- RQ3: 2,500 paired scenarios compare baseline and trend policies using
  synthetic oracle demand. The trend scenario has 0.87% lower supplied
  scenario cost but 122.2% more lost units. The cost formula and owner's
  observed policy are unavailable; no realised-savings claim is made.
- RQ4: suggested quantity, action and constraint reason match 100% of
  1,800 prepared cases. Generated Bangla/English explanations have 100%
  coverage of branch-required numeric evidence. The constant
  `human_rating=YES` field is not participant feedback; the owner study
  remains pending.
- Raw business records and customer-level predictions are not committed
  to the public repository. Only code, manifests, documentation and
  aggregate outputs are published.

# Verification record

## Current SME scope revision — 2 November 2026

- Active LaTeX sources now cover Bangladeshi SMEs across sectors, with a shared
  operational core and inventory/service-specific extensions.
- Research population, data plan, model hierarchy, architecture, evaluation and
  conclusions were revised; no experimental results were invented.
- Added explicit per-business, per-sector, held-out-business and conditional
  held-out-sector evaluation. Broad framework coverage is not universal validity.
- `main.tex` uses the editable TikZ architecture instead of the old domain raster.
- Compiled with pdfLaTeX through repeated passes; citations and references resolve
  without undefined references/citations or overfull-box diagnostics.
- Title and architecture pages were rendered for visual inspection.
- The archived submitted report is retained unchanged as a historical document.

## Historical verification — pharmacy revision

Verified on 8 September 2026 from the project repository.

The verified build incorporates the Bangladeshi retail-pharmacy scope and the
supervisor-guided flow recorded in
`../docs/PHARMACY_VERTICAL_SCOPE_AND_SUPERVISOR_GUIDELINE.md`.

- LaTeX compilation: successful with Tectonic 0.17.0.
- Final PDF: 61 pages; the extra page preserves readable table and architecture
  labels after the pharmacy-specific revision.
- Cross-references and citations: resolved; no undefined-reference, undefined-citation, or overfull-box diagnostics.
- Visual QA: the revised title, pharmacy scope, bordered tables, equations,
  canonical data diagram, supervisor-guided architecture and continuous-learning
  flow were rendered and inspected with no clipping or overlap.
- Table verification: all substantive `tabularx` and `longtable` data tables use
  visible outer and inter-column rules; title and signature layout tables remain
  intentionally borderless.
- Minimal Overleaf archive: the two-file archive (`main.tex` and `logo.pdf`)
  compiles independently with the same resolved references and clean diagnostic
  checks.
- Scope verification: substantive writing covers Introduction, Background Study and Related Work, Proposed Methodology, and a current-stage Conclusion grounded only in those chapters. Implementation and Experimental Results remain heading-only placeholders.
- Front-matter verification: Abstract and Acknowledgements contain headings only, as requested.
- Reference verification: exactly 25 cited bibliography records are included; all 25 matched Crossref, DataCite, or an official publisher/repository endpoint.
- Planning-content verification: the former Two-Semester Work Plan, project-timeline table and milestone/contingency table are absent.
- Language verification: the compiled report, diagram labels, captions and tables are entirely in English.
- Evidence boundary: planned primary, public-real and generated evidence are kept separate. No experimental result or primary partner dataset is claimed in this initial report.
- Domain boundary: recommendations cover pharmacy business operations only;
  diagnosis, prescription selection and dosage advice are explicitly excluded.

The Tectonic engine may emit harmless underfull-box notices for narrow table cells
and package-level encoding notices from `algorithm2e.sty`; these do not create
clipping, overlap, missing glyphs, or unresolved document content in the rendered
PDF.
