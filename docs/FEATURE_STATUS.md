# B-SMART implementation status

The current deliverable is a complete local thesis MVP for inventory-based
Bangladeshi retail SMEs. It is not represented as a finished commercial ERP.

## Complete end-to-end flows

- Local owner workspace; organization and branch isolation without Google sign-in.
- Product catalogue, cost/selling price, units, barcode and reorder level.
- Customer consent flag, privacy-preserving phone hash, supplier and lead time.
- Opening stock/adjustments and append-only stock movement history.
- Point of sale with Cash, bKash, Nagad, Bangla QR, card and due-sales support.
- Purchase order, partial/full receiving, stock update and supplier payable.
- Sales return, optional restocking, refund and receivable adjustment.
- Expenses, payable/receivable/expense ledgers and 30-day operational dashboard.
- Durable CSV/XLSX import provenance and canonical real-sales export.
- Leakage-free real-data demand and future-repeat training command.
- Forecast/churn/segmentation research views, model metrics and SHAP artifacts.
- Constraint-aware reorder and consent-safe retention action ranking, driven by
  the trained real-data demand model when one exists for the organization and
  by a labelled 28-day baseline otherwise (`ml/serving.py`).
- Explicit synthetic scalability benchmark separated from real model evidence.

## Scientific guardrails

- Operational recommendations display `baseline` until a sufficient real-data
  model artifact is trained; the UI does not relabel a heuristic as AI. Once
  `artifacts/real/<org_id>/demand_model.joblib` exists, those actions switch to
  `confidence: model` and say so in their Bangla explanation.
- Real model evaluation is chronological and future-repeat labels are horizon-purged.
- Synthetic scalability rows are labelled `synthetic_scalability_only`.
- Existing synthetic research results remain demonstration/preliminary evidence,
  not the primary thesis result.

## Intentionally deferred

- Google or other external sign-in, public multi-user deployment and billing.
- VAT/NBR fiscal integration, bank reconciliation and statutory accounting.
- Native mobile/offline synchronization, barcode hardware and receipt printers.
- Automated campaigns; the prototype only ranks consented customers.
- A model cannot be declared production-ready until consenting real SME data,
  calibration, drift and pilot business-impact evaluation are complete.

## Commands

```powershell
python run_api.py
cd frontend
npm run dev
```

Real-data experiments:

```powershell
python -m ml.real_pipeline --input path\to\bsmart_sales_anonymized.csv
python -m ml.scalability_benchmark --scales 100 500 1000 10000 100000 1000000
```
