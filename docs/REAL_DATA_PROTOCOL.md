# Real-data acquisition protocol

## Purpose and scope

The primary thesis evidence will come from consenting Bangladeshi retail SMEs.
Synthetic records are permitted only for tests, demonstrations, rare scenarios,
and explicitly separated scalability experiments.

## Minimum target

- 3–5 businesses from one comparable retail vertical.
- 12–24 months per business.
- Invoice line items, not monthly summaries.
- Target 50,000+ lines, 500+ SKUs, and 2,000+ pseudonymous customers.
- Preserve stockouts, returns, cancellations, discounts, and missingness.

## Required files

1. Business and branch profile.
2. Product/SKU master with units and categories.
3. Sales invoice header and line items.
4. Inventory receipts, sales, returns, adjustments, and stock counts.
5. Purchases and supplier lead times.
6. Expenses and payment channel totals.
7. Optional anonymized customer identifiers and marketing consent.

## Privacy rules

- Obtain university ethics approval and a signed data-sharing agreement first.
- Never place raw names, phone numbers, email, NID, account or wallet numbers in
  a training table or the repository.
- Generate a different salted pseudonymous customer ID for each organization.
- Store the re-identification mapping, if one is necessary, under the business's
  control and outside this project.
- Record purpose, lawful/consented use, retention date, permitted researchers,
  and deletion procedure.
- Publish only aggregates or a separately reviewed de-identified research set.

## Provenance manifest

Every imported source must record: organization, date range, export system,
collector, received date, checksum, row count, license/permission, schema
version, cleaning steps, exclusions, and known limitations.

## Leakage-safe observation design

- Demand: branch–SKU–day, evaluated forward in time.
- Churn: features frozen at cutoff T; label is no purchase in (T, T+H].
- No outcome or post-outcome field may enter a prediction feature.
- Fit encoders, imputers, and scalers on training folds only.
- Keep the final time period untouched until model selection is complete.
- Report per-business results and leave-one-business-out generalization.

## Acceptance checks

- Unique tenant, branch, invoice, line, SKU, and timestamp keys.
- Monetary identities reconcile within an agreed rounding tolerance.
- Sales and returns reconcile with stock movements.
- No cross-tenant identifier collision or query result.
- Missingness and outliers are profiled, not silently replaced.
- Deleted/cancelled records remain auditable without entering revenue.
