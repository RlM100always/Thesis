# Real SME data onboarding and thesis evidence boundary

Status: 2 November 2026. This document records the data decision for the
current multi-sector SME thesis and is the handoff contract for the real data
that will be collected next.

## Current GitHub state

The current `main` tree contains no CSV, Parquet, XLSX, model pickle, Joblib
artifact or generated research dataset. Earlier synthetic research files exist
only in repository history and are not part of the current checkout. They must
not be restored or cited as real observations.

The operational application and the thesis algorithm are separate evidence
paths. The application may exercise its CRUD, tenant isolation and reporting
tools with local fixtures. Thesis model metrics require an approved dataset and
an immutable run manifest; a tool demo is not an empirical result.

## Audit of the supplied files

The supplied `manifest.json` identifies the package as
`B-SMART Bangladesh-context SME Integrated Research Simulation` and states:

> `100% SYNTHETIC / simulated; NO observed SME sales or real people`

The manifest also declares a fixed seed (`20261025`), 32 shops, 11,000
synthetic customers, 480 synthetic products, 56 synthetic suppliers and a
2023-01-01 to 2025-12-31 simulation period. Every row inspected in the supplied
tables carries `synthetic_flag=YES`; the supplied `shops.csv`, `products.csv`,
`customers.csv`, `suppliers.csv`, `purchase_orders.csv`, `purchase_lines.csv`,
`inventory_lots.csv`, `payments.csv`, `returns.csv`, `promotions.csv` and
`calendar.csv` are therefore simulation artifacts, regardless of whether the
file names resemble exports from a live business.

`rq4_explanation_cases.csv` contains generated cases and explicitly marks
`synthetic_case_not_human_rating=YES`. It cannot establish owner comprehension
or usability. `simulated_unmet_demand.csv` is labelled hidden truth and may be
used only for a controlled simulation check. The large sales and movement files
were not imported into this environment because the transfer limit is 32 MiB;
the manifest already classifies them as synthetic, so that limitation does not
change the evidence decision.

These files can be retained outside the thesis evidence set for schema tests,
join tests, rare-event simulation, UI development and scalability checks. They
must not be used to report real-world accuracy, Bangladesh SME behaviour,
business value, owner usability or cross-sector generalisation.

## Required real-data package

Each future package must include a manifest with the source business or public
repository, collection and receipt dates, licence or consent basis, sector,
geographic scope, date coverage, timezone/currency, row counts, schema version,
checksums, anonymisation procedure, missingness notes and a field-level
classification of observed, derived, public-reference and generated values.
The manifest must explicitly say whether any row is synthetic. A claim that a
file is real is not sufficient without provenance that can be audited.

The minimum algorithm input is a canonical event history:

- business, branch and sector identifiers;
- event date/time and source ingestion time;
- product or service identifier, quantity, unit price and discount where
  applicable;
- order/invoice identifier and status, including cancellation and return;
- cost or purchase information when margin or procurement is evaluated;
- inventory or capacity state when a reorder or capacity recommendation is
  evaluated;
- supplier/lead-time, budget, pack or minimum-order and other owner constraints
  only where those values are actually recorded;
- stable pseudonymous customer ID and consent only when customer analysis is
  authorised and follow-up is possible.

Optional tables such as payments, promotions, returns, inventory lots,
suppliers and calendar context are joined by stable keys and retained with
their own provenance. Service businesses may provide bookings, completion,
staff/equipment capacity and delivery duration instead of inventory fields.
Non-applicable fields are represented as missing/not-applicable; they are never
filled with simulated values.

## Algorithm and report workflow after real data arrives

1. Freeze the received package and checksum it. Produce a data-quality report
   covering keys, joins, duplicates, missingness, date coverage, correction
   status and business/sector counts.
2. Build one canonical, auditable event schema. Keep raw records, transformed
   records and feature snapshots separate. Do not mix generated fixtures with a
   real evaluation period.
3. Split by time before fitting encoders, imputers, scalers or models. Where
   enough independent businesses exist, add held-out-business and held-out-sector
   evaluation. Report per-business and per-sector results before pooled means.
4. Establish transparent baselines first: seasonal/moving demand, inactivity
   base rate, simple segments and current business policy. Promote a complex
   model only after a stable, material improvement on untouched data.
5. Run only eligible tasks: demand or capacity forecasting, inactivity risk,
   segmentation, anomaly analysis and constraint-aware recommendation. A task
   with insufficient fields receives an explicit “not evaluable” result.
6. Separate predictions from actions. The algorithm estimates demand/risk; the
   strategy layer checks the business's actual constraints and ranks feasible
   actions. Every recommendation stores cutoff, model/baseline version,
   explanation, constraints, owner decision and later outcome.
7. Update the report's Implementation and Experimental Results chapters only
   from frozen run artifacts. No number is copied from a simulation, demo UI or
   unverified tool log.

The operational “real tools” part will use the same canonical identifiers but
will keep tenant data isolated. It will display whether an output is a live
business result, a research result or a synthetic demo. Live recommendation
outcomes are measured from the business ledger where possible; unmeasured
outcomes remain null.

## What is still needed

The supplied package is not yet the real-data package required for the thesis.
Please provide the actual exports and provenance manifest. `sales_orders.csv`,
`sales_lines.csv` and `inventory_movements.csv` exceeded the current 32 MiB
transfer limit, so split each into parts smaller than 32 MiB (with headers and
stable part ordering) or provide a compressed archive whose extracted files are
each below that limit. Once the actual real files arrive, the canonical mapper,
algorithm runner, report tables/figures and live tools integration can be built
and validated against them.
