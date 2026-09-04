# Bangladesh SME feature research — what B-SMART's Operations Layer should cover

Answers the "কী কী ফিচার লাগে একটা SME ম্যানেজ করার জন্য, এবং UI/UX বাংলাদেশ
কনটেক্সটে কেমন হওয়া উচিত" question with what's already built, what's
genuinely missing, and why — grounded in the research pulled together for
[THESIS_PRODUCT_MASTER_PLAN.md](THESIS_PRODUCT_MASTER_PLAN.md) §9. This is a
planning document, not a schema — see `api/domain_models.py` for what
actually exists in code.

## Already built (verify against `api/domain_models.py` before assuming a gap)

The domain model already covers a real inventory-retail SME's daily
operations: `Organization`/`Branch` (multi-branch), `Product` (cost/sell
price, reorder level, barcode), `Customer` (consent flag, phone hash),
`Supplier`, `SalesOrder`/`SalesOrderItem` (POS), `Payment` (cash, bKash,
Nagad, Bangla QR, card, due), `StockMovement`/`InventoryBalance`
(append-only ledger), `Expense`, `PurchaseOrder`/`PurchaseOrderItem`,
`LedgerEntry` (payables/receivables), `SalesReturn`/`Refund`, `AuditLog`,
`ImportBatch`. This is not a toy — it's close to a minimal viable retail ERP.
Do not propose rebuilding any of this; propose additions or UX fixes.

## Confirmed real gaps

1. **No Google/external sign-in.** `api/auth.py` only has a dev-mode bypass
   and raw JWT — no OAuth flow, no `/auth/login` endpoint at all. The
   supervisor's product vision explicitly wants Gmail-based login. This is
   currently an *intentionally deferred* item per `docs/FEATURE_STATUS.md`,
   but if the product vision now requires it, it needs to move from
   "deferred" to "planned" — that's a scope decision to confirm before
   building, since it adds an external dependency (Google OAuth
   credentials, consent screen, redirect URI management) the thesis
   environment may not want to depend on for grading/demo reliability.
2. **No custom-dataset comparison feature yet.** The idea ("ইউজার চাইলে
   কাস্টম ডেটাসেট এনে মডেল কেমন পারফর্ম করছে সেটা মাপা যাবে") is partially
   supported already: `/api/app/datasets/sales.csv` exports an org's own
   operational data in the canonical schema, and `ml/real_pipeline.py`
   trains and reports metrics on whatever canonical CSV it's given. What's
   missing is a UI to run that comparison and display per-dataset metrics
   side by side — not a new ML capability, just a results view.
3. **UI is not Bangladesh-first everywhere yet.** Some newer pages
   (`BusinessSetup.jsx`) are already Bangla-labelled; others (`Overview.jsx`,
   `Segments.jsx`, `Forecast.jsx`, `ModelReport.jsx` — the older
   thesis-pipeline pages) are English-only research views. That split is
   fine *if* it's deliberate (research/model-report pages stay technical;
   operational pages the owner touches daily are Bangla) — but it should be
   a stated design decision, not an accident of two systems growing
   independently. See "UI/UX recommendation" below.

## UI/UX recommendation for the Bangladeshi SME context

Backed by the research in the master plan (§9): SME digital maturity is
moderate (~0.45/1) and adoption barriers are cost, skills, and trust, not
willingness — so the UI should minimize what a non-technical owner has to
learn, not add features they won't use.

- **Bangla-first for anything the owner touches daily** (POS, inventory,
  dashboard, recommendations) — already the direction `BusinessSetup.jsx`
  and `OperationalDashboard.jsx` are going. Keep English for
  research/model-report pages aimed at evaluators, not shop owners.
- **Payment methods as first-class UI, not an afterthought** — bKash, Nagad,
  Rocket, Upay, and cash-on-hand should be visually equal options in the POS
  flow, matching how dominant mobile wallets already are in this market
  (per §9's MFS research) — `Payment.method` in the schema already supports
  this; confirm the POS UI surfaces all of them equally rather than
  defaulting to "cash" first.
- **Calendar awareness surfaced to the owner, not just the model** — Eid/
  Ramadan/Puja demand spikes should show as a visible dashboard annotation
  ("এই সপ্তাহে ঈদের কারণে বিক্রি বাড়তে পারে"), not just a hidden feature
  column in the forecasting model. This is both a UX trust-builder and a
  direct way to demonstrate the "Bangladesh-context-aware" thesis claim in a
  screenshot.
- **Low-friction data entry over completeness** — a shopkeeper mid-sale will
  not fill an 8-field form; the POS/sale-creation form should default
  aggressively (last-used branch, common payment method, quantity 1) and
  make everything but SKU/quantity/price optional at entry time, matching
  the "non-technical user adoption" barrier the literature flags.
- **Explanations in plain Bangla, not model jargon** — "confidence 0.82" or
  "SHAP value" means nothing to a shop owner; "প্রায় নিশ্চিত" / "মাঝারি
  নিশ্চিত" with a one-line reason is what the thesis's Chapter 3 RQ4
  (do Bangla explanations improve task completion/confidence) is actually
  testing — worth prototyping this framing now on `OperationalDashboard.jsx`
  and `Actions.jsx` rather than leaving it for later.

## Recommendation

Treat items 1–2 above as scope decisions, not silent additions — Google
login in particular pulls in an external dependency that should be a
deliberate choice, not something added because it was mentioned once. The
UI/UX points can be applied incrementally to existing pages without a
redesign, since the Bangla-first direction is already underway on the new
B-SMART pages.
