# Research clean restart — B-SMART October 2026

**Previous research was removed from main and preserved in the backup branch [archive/pre-new-bsmart-dataset-2026-10-25](https://github.com/RlM100always/Thesis/tree/archive/pre-new-bsmart-dataset-2026-10-25).**

The only selected *new* integrated dataset is **B-SMART Bangladesh SME Research Simulation v1**, a synthetic, Bangladesh-context multi-table FMCG scenario. **It is not field-collected data.** Its source ZIP was generated and shared in the conversation but has **NOT been uploaded to GitHub or the deployed app**; see [manifest](../research/new_dataset/manifest.json) for checksum and dimensions. No new trained model is installed.

## Retired from main
Old pharmacy fixture, public secondary CSVs, old seven-sector generators, root forecasting/churn/classification scripts, legacy `predict.py` and `upload_service.py`, `ml/real_pipeline.py`, previously saved `.joblib/.pkl` artifacts, previous forecasting/segmentation plots and benchmark JSON. Old experimental results cannot be silently reused. Docker no longer generates the previous seven datasets.

## Preserved
Operational FastAPI + React business app, backend/database models and migrations, access control, shop sales and inventory operations, live rule-based recommendation fallback, existing test suite, thesis report sources and generated thesis PDF. Existing databases and Cloudflare R2 objects are **not touched by deleting GitHub files**.

## Rebuild plan
1. Locally extract the source ZIP and verify SHA-256 `d15074a1ada30bfdd0cf9c06a32ff0639fde9cf898ef314acb511cd99190f9c5`; run included dataset validation.
2. Build a **multi-CSV relational loader**, retaining all foreign keys and synthetic provenance flags. New package includes shops, customers, SKU products, sales orders/lines, stock lots/movements, purchase orders/lines, payments, returns, promotions and RQ4 explanation cases.
3. Rebuild RQ1 using chronological shop×SKU or shop×category forecasting with honest seasonal baselines, leakage checks and WAPE/MASE.
4. Rebuild RQ2 customer inactivity using as-of-T cutoff features, follow-up windows, PR-AUC, lift and Brier scores.
5. Rebuild RQ3 with explicit **offline simulations** and purchase/stock constraints. Do not claim measured real business savings.
6. Rebuild RQ4 **technical explainability** with generated mechanical decision cases. This cannot prove real owner comprehension or usability without participants.
7. Connect training, evaluation and manifest registry to the Research Portal only after new code and artifact checks are implemented; new metrics must be actual recomputations.
8. Amend original thesis pharmacy/field-validation scope with supervisor approval before claiming thesis completion.

Old research endpoints respond as **retired** or **not ready**. Operational app stays, but full deployment regression testing remains required. No new dataset or model is claimed loaded.
