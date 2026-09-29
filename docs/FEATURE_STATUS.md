# B-SMART implementation status

The current deliverable is a local thesis MVP whose revised target vertical is
**Bangladeshi retail pharmacies**. It is not a finished pharmacy ERP or a
universal SME model. The existing generic-retail features are the prototype
foundation; the pharmacy-specific schema, pooled multi-pharmacy model and full
constraint lifecycle remain planned. See
[the revised scope](PHARMACY_VERTICAL_SCOPE_AND_SUPERVISOR_GUIDELINE.md).

## Complete end-to-end flows

- Local owner workspace; organization and branch isolation without Google sign-in.
- Batch and expiry stock (2026-09-28): expiry-tracked products hold stock in batches; sales are first-expiry-first-out and never take an expired or blocked batch; purchase receipt needs batch number + expiry; returns go back to the batch they came from; recall/quarantine blocking; expiry board with money at risk; stock reconciliation report (balance vs ledger vs batches). Pack conversion (box/strip/piece) and cold-chain/Rx flags are still not built.
- Point of sale with a multi-item cart, barcode/Enter add, split of paid/change/due, printable receipt (shop address/phone/VAT/footer from the owner's own profile), cart draft survives a refresh, hold/resume a bill to serve another customer, wholesale price tier repricing, and a credit-limit guard that blocks a due sale before it is created (not after).
- Audit trail with a reader (owner/manager) covering staff, sales, returns, purchases, payments, expenses, imports, exports, model training and B-SMART decisions.
- Browser end-to-end tests (`e2e/`, Playwright + Edge): pharmacist batch lifecycle, cashier invite and role-limited UI, phone layout, login errors, signup → business onboarding → guided dashboard, credit sale → baki collection → expense → return, B-SMART decision + outcome, **every role signing in and seeing exactly its own panels**, a non-pharmacy (clothing) business, and the features below.
- Any-business support: business type chosen at signup sets defaults and wording (expiry tracking on by default for pharmacy/grocery/cosmetics, optional for others); the expiry screens appear for any business once a product tracks expiry.
- Morning brief (yesterday vs the 7-day usual, what to buy, expiry, who owes, what is waiting) shareable as text/WhatsApp; alert bell for every role (only what the role may see); honest profit (reported on lines whose cost is known, with coverage %, never a made-up margin).
- Daily cash count per branch (books vs drawer, variance needs a reason, one close per day, audited); sales history with search and reprint; customer detail with a ready polite baki message; supplier scorecard from real orders (delivery time, punctuality, price movement, `null`/"not measured" when there is no data); branch-to-branch stock transfer (batch-aware); CSV reports Excel can read.
- **Offline point of sale**: bills made without internet are kept on the device with their own invoice number and sent when the connection returns, exactly once (the server refuses a repeated invoice number).
- **Void a sale** (2026-09-29, owner/manager only, `sales:void`): cancels a whole invoice through the same code path as a return, so stock/batches, refunds and receivables stay consistent with one implementation; refuses a second void, a tax-bearing invoice (a return handles tax; void does not), or an invoice that already has a partial return.
- **Editing after the fact**: products (price, wholesale price, cost, reorder level, category, barcode, archive) and customers (name, phone, credit limit, price tier, marketing consent) can be changed post-creation; price/limit changes are written to the audit trail, the SKU and a customer's phone hash never silently change.
- **Wholesale price tier and per-customer credit limit**: a customer flagged `wholesale` is billed the product's wholesale price automatically (an explicit line price still wins); a customer with a credit limit is refused a due sale that would push their outstanding balance over it, checked against the live receivable ledger, not a cached balance.
- **Baki ageing** (`/accounts` → কাস্টমারের বাকি): buckets every customer's outstanding receivable into 0–30/31–60/61–90/90+ days, with payments applied FIFO (oldest debt first) the way a shopkeeper actually collects, so the bucketing is arithmetic on the ledger, not an estimate.
- **Bulk data import** (`/import`, owner/manager/accountant per kind): products, customers and opening stock from a CSV/XLSX with English-or-Bangla header guessing and Bengali-digit parsing; a two-step preview → confirmed-mapping → commit flow reports every rejected row by its line number and reason, and accepts the rest.
- **"কী কিনবেন" reorder planner** (`/reorder`): `suggested = ceil(daily_rate × (lead_days + cover_days) − sellable_stock − already_on_order)`, excluding expired/blocked batches from "sellable" and stock already on order from the suggestion; one tap creates one purchase order per supplier, editable before sending.
- **Shop profile** (`/setup`, owner only): address, phone, VAT/BIN number and a receipt footer, printed on the POS and sales-history receipts.
- **Not built yet:** accepting a recommendation does not create a purchase order (the reorder planner above creates one directly from arithmetic on stock, not from an accepted B-SMART recommendation); no LLM layer; no SMS/WhatsApp API (messages are copied or opened by the owner, and phone numbers are not stored); reports are CSV + browser print, not PDF; pack conversion (box/strip/piece), cold-chain/prescription flags, constraint-profile screen, consent register screen; engine still reads the research artifact, not live tenant data; forecast/segments/upload pages still show research-dataset demos; no Postgres row-level security or deployment package; no held-bill sync across devices (a held bill lives in this browser's storage only); no price-tier below "retail/wholesale" (no per-customer negotiated price list) and no purchase-return/expiry-claim-to-supplier flow yet.
- Email + password accounts with short-lived access tokens, rotating refresh tokens and logout that revokes every token; a role → permission matrix enforced on every tenant route (owner, manager, cashier, accountant, stock_keeper, viewer, evaluator) and a permission-aware Bangla UI. Not yet built: staff-invite acceptance, password reset, branch-scoped roles, audit-log viewer, Postgres row-level security.
- Persistent recommendation accept/reject/modify/defer decisions (append-only) and observed-outcome records, with a monitoring summary that reports `null` for anything unmeasured.
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
- A model cannot be declared production-ready until consenting multi-pharmacy data,
  calibration, drift and pilot business-impact evaluation are complete.

## Revised pharmacy extension — required, not yet complete

- Multi-pharmacy de-identified research dataset and held-out-shop evaluation.
- Pharmacy product attributes, pack/unit conversion, batch/lot and expiry.
- Cold-chain/storage, MOQ, purchasing budget and category-limit inputs.
- Baseline versus pooled pharmacy model versus shop-adapted model selection.
- Outcome measured automatically from the stock ledger (today outcome fields are hand-entered, and accepting a recommendation records the decision but does not yet create a purchase order, price change or reminder).
- Monitored scheduled/drift-triggered retraining, model promotion and rollback.
- Business recommendations only; no diagnosis, prescription or dosage advice.

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
