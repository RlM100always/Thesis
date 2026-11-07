# B-SMART research revision — build and evidence checklist

The canonical original pre-defence research structure remains six chapters in thesis_report/main.tex. The current branch adds these four integrated sections:
- Chapters/evidence_aware_methodology_2026_11_05.tex — RQ design and time-aware validation.
- Chapters/evidence_aware_implementation_2026_11_05.tex — operational modules versus offline model results.
- Chapters/evidence_aware_results_2026_11_05.tex — RQ1 hierarchical diagnostics/model refits/rolling folds, RQ2 SHAP, RQ3 and RQ4 evidence limits.
- Chapters/evidence_aware_conclusion_2026_11_05.tex — measured answers and remaining work.
- Figures/rq1_hierarchy_wape.png and Figures/rq2_shap_global.png — PNGs generated from the verified aggregate results.
- research/analysis/*.py — research scripts intended to be run locally with restricted inputs.
- research/outputs/aggregate_results_2026-11-05.json — public-safe aggregate results.

## Reproducibility

Install numpy, pandas, matplotlib, scikit-learn, lightgbm, xgboost, joblib, openpyxl.

    python research/analysis/advanced_rq1_analysis.py --panel /restricted/rq1_daily_shop_category.xlsx --out /restricted/output_rq1
    python research/analysis/rq2_explanation_audit.py --snapshots /restricted/rq2_customer_snapshots_90d.xlsx --model /restricted/rq2_models.joblib --out /restricted/output_rq2
    python research/analysis/rq3_rq4_scenario_audit.py --rq3 /restricted/rq3_offline_policy_comparison.xlsx --rq4 /restricted/rq4_explanation_cases.xlsx --out /restricted/output_scenarios

Do NOT commit source spreadsheets, customer-risk models or row-level predictions to the public repository.

For the monolithic LaTeX source:

    cd thesis_report
    pdflatex -interaction=nonstopmode main.tex
    pdflatex -interaction=nonstopmode main.tex

Additional experimental PNG plots can be exported locally. The current branch's monolithic LaTeX compile was not independently executed via the GitHub connector; render in Overleaf/TeX Live before merging.

## Boundaries that must be preserved
- Network/day WAPE 6.02% and shop-category/day WAPE 83.98% are evaluations of the same predictions, not two separately trained models.
- Two-stage 84.04% and XGBoost 84.56% did not improve shop-category predictions.
- The RQ3 synthetic future-demand oracle does not represent actual merchant savings.
- The RQ4 evidence-complete flag does not establish owner comprehension or intervention benefit.
- RQ2 TreeSHAP is log-odds attribution, not a causal explanation.
- Internal transaction reconciliation does not independently verify merchant identities or consent.
- Experimental models are offline, not deployed production inference endpoints.

## Open scientific and software acceptance requirements
- [ ] Independent merchant source verification, data-owner permission and consent/ethics documentation.
- [ ] Independent audit of raw transaction to daily-panel and customer-label reconstruction.
- [ ] New forward/externally untouched period for confirmatory model selection.
- [ ] Stock ledger, supplier lead times and service-level outcomes for RQ1-to-RQ3 lead-time policy replay.
- [ ] Consented SME-owner explanation study for RQ4.
- [ ] Versioned model-serving integration, security tests and actual outcome feedback.
- [ ] Real application screenshots; journal-level reference/format verification.
- [ ] Compliance with institutional page limits: a separate split-source PDF exceeds the earlier 70-page target rather than hiding important results.
