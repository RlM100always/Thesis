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
- **Cash-Locked Meter** (dashboard, owner/manager/accountant): one BDT figure = dead-stock value (no sale in 60 days, valued at cost, new arrivals excluded) + near-expiry/expired batch value + baki over 60 days old, each part links to where to act.
- **ইনসাইটস** (`/insights`): ABC classification by revenue share and XYZ by demand steadiness (coefficient of variation over 3+ weeks of sales, else "not enough data" rather than a guess), a dead-stock flag per product, and a supplier price-watch that flags a ≥5%-configurable purchase-price move between a product's last two receipts from the same supplier — never on a single purchase. Tab visibility respects role (a role without `sales:read` sees only the price-watch tab, not a permission error).
- **Stock take / cycle count** (2026-09-29, `/stock-count`): snapshot the system's quantity for every non-expiry-tracked product at a branch, enter what's actually on the shelf, and complete the count to apply every variance as one reviewed batch — never a silent one-off correction. Posts to the books (a new `5910 Inventory Shrinkage/Adjustment` account, contra like the sales-returns account: a shortage debits it, found stock credits it back). Only one open count per branch at a time; an uncounted line is left untouched, not zeroed. Expiry-tracked products are deliberately out of scope — a variance there needs a batch to attribute it to, which "মেয়াদ ও ব্যাচ" already owns.
- **Guided setup wizard** (2026-09-29): signup no longer drops the owner straight into an empty dashboard. A 4-step wizard runs right after the business is created — receipt profile (address/phone/VAT/footer) and staff invites, both skippable — before landing on the dashboard. Later steps operate on the already-created organization (`BusinessContext`'s `wizardActive` flag keeps the app shell from switching over the instant the org exists, so the wizard isn't cut off mid-flow). Opening stock and a real onboarding checklist are not yet part of the wizard (bulk import and the "শুরু করুন — ৪টি ধাপে প্রস্তুত" checklist on the dashboard cover that separately).
- **Purchase-order approval** (2026-09-29, fourth approval-rule kind: `purchase_amount`, default ৳20,000, owner): a PO at or above the threshold is not time-critical like a till sale, so it uses the async inbox (same as expenses) — held, shows up at `/approvals`, and approving creates the exact PO that was requested. Only the direct "নতুন ক্রয় অর্ডার" form is gated; the "কী কিনবেন" reorder-planner's one-tap PO creation is a known gap (`docs/BUSINESS_OS_VISION.md`).
- **Refund override** (2026-09-29, third approval-rule kind: `refund_amount`, default ৳1,000, manager): a cash/mobile-banking refund at or above the threshold — on a return, or a void, which is a return under the hood — needs the same inline manager/owner credentials as a discount override, verified for real. Recorded to the audit trail (`refund.override`).
- **Discount override at the till** (2026-09-29, second approval-rule kind: `discount_percent`, default 10%, manager): a POS discount at or above the threshold cannot complete the sale — a qualifying manager/owner types their own email and password inline (nothing async; a checkout cannot sit in a queue), verified against their real password hash and their membership's role, not just accepted on faith. Recorded to the audit trail (`sale.discount_override`, who approved it). The owner can change the threshold or who must approve from the same `/approvals` page as the expense rule.
- **Approval Inbox** (2026-09-29, `/approvals`, `api/approvals.py` + `api/approval_routes.py`): the first working instance of a configurable approval gate — an expense at or above an owner-set threshold (default ৳5,000) by someone below the required role is held as a pending `ApprovalRequest` instead of posting, shows up in the owner's/manager's inbox with who asked and why, and approving it posts through the exact same code path an unheld expense would have used (so an approved expense is indistinguishable from one nobody needed to approve). The owner can change the threshold, who must approve, or turn a rule off from the same page. Only `expense_amount` is wired so far — discount, refund, void, purchase and credit-limit-increase gates from `docs/BUSINESS_OS_VISION.md`'s blueprint are not yet built; add a kind at a time, never half-wire several.
- **Double-entry accounting engine** (2026-09-29, `api/accounting.py`, `/accounting`): a real chart of accounts (seeded per organization), posted alongside — never instead of — the existing payable/receivable/expense subledgers, so nothing that already worked can break. Every sale, return/void, purchase receipt, expense and customer/supplier settlement now also posts a balanced journal entry (`post_journal` refuses an entry whose debits and credits don't match, or that names an unknown account code). Trial balance, profit & loss and a balance sheet are read straight off the journal, never re-derived by hand. This is the first slice of `docs/BUSINESS_OS_VISION.md`'s "universal core" accounting module — still missing: a chart-of-accounts editor for the owner, bank-statement reconciliation, VAT return export, and posting cash-close variance to a dedicated account (today a cash-count variance is recorded but not yet journaled).
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
