# B-SMART thesis research data — current source

The thesis research uses the Bangladesh data package supplied through the project Google Drive folder. Its manifest claims real SME data, but a generation seed and “modeled world” wording leave source provenance unverified. The package covers 2023–2025 and contains shop, product, customer, sales, payment, procurement, inventory, return, promotion and calendar data.

## Research datasets

- RQ1: 699,220 positive-sale SKU records. Missing SKU-date rows are not automatically zero.
- RQ2: 72,146 customer snapshots across 10,613 unique customers, with separate TRAIN and TEST assignments.
- RQ3: 2,500 replenishment policy scenarios. Scenario comparisons are separate from the participating owner's actual policy.
- RQ4: 1,800 explanation cases. The human_rating column is not, by itself, evidence of a completed participant study.

## Repository and data separation

- Raw source files remain in the private Google Drive folder.
- GitHub stores research code, model configurations, run manifests, non-sensitive aggregate outputs and figures.
- Do not commit raw customer identities, contact details or other personal records.
- Keep each RQ's data, target definition, split and evaluation protocol separate.

## Current work — 9 November 2026

RQ1 has a completed exposure-conditioned Q4 diagnostic, but its period was previously inspected and it does not beat the 28-day exposed-sales mean on WAPE; an untouched test and independent stock validation remain. RQ2 has a reproducible temporal model comparison and zero label mismatches on 72,146 snapshots. RQ3 has a paired comparison on 2,500 generated-demand scenarios; owner-policy replay and validated realised outcomes remain. RQ4 has a mechanical audit of 1,800 prepared cases; a consented participant study remains necessary for any human-feedback result.

Use the current research documentation in research/forecasting/README.md and docs/REAL_DATA_ONBOARDING.md. Do not use older reset notes as the description of the current dataset.