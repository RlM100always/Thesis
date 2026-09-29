# B-SMART Business OS — the full-SME vision and how it maps onto this repo

The user's direction (2026-09-29): B-SMART stops being "a pharmacy tool with other
verticals bolted on" and becomes a **universal SME Business OS** — one core engine
(sales, stock, money, staff, customers, reports, audit, approvals, AI) plus 15
**industry packs** (grocery, pharmacy, fashion, wholesale, restaurant, electronics,
hardware, manufacturing, service/repair, salon, clinic admin, coaching, agro,
transport, rental/event), each with its own terminology, workflow and AI metric,
selected by a setup wizard at signup. This document is the honest bridge between
that full blueprint and what exists in this repo today — **read this before
claiming a vertical or a Universal Core module is "done."**

This does not replace `docs/THESIS_PRODUCT_MASTER_PLAN.md` (the thesis-scoped
Wave 1 plan, weeks 15-28) or `docs/BSMART_ARCHITECTURE.md` (the 10-layer research
architecture). It sits above them: the thesis stays pharmacy-first and
Wave-1-scoped; this document is the **product** roadmap Waves 2-3 grow into, now
specified in much more detail than the master plan's section 9B/10 sketch.

## Scale, honestly

Section-by-section, this blueprint is a legitimate multi-quarter SaaS product for
a small team — not a task list one coding session finishes. "Sob step by step"
(everything, step by step) is the right instinct, but it means: **one real,
tested, working step at a time**, never 15 verticals half-built at once. A
half-built vertical pack (menu items that go nowhere, a wizard branch with no
screen behind it) is worse than not having it — CLAUDE.md's own rule ("no fake
buttons") applies doubly here.

## What already exists that this vision reuses directly

| Piece of the vision | Existing code | Status |
|---|---|---|
| "Universal Core: same engine, per-business language" | `BusinessContext.jsx`, `verticals.js`, `Organization.sector` | PARTIAL — sector picks *labels and one flag* (`expiry`) today, not menus/workflow |
| Business-type-aware defaults | `BUSINESS_TYPES` in `verticals.js`, signup sets `sector` | IMPLEMENTED for pharmacy/grocery/cosmetics expiry default only |
| Role × permission matrix | `api/permissions.py`, `PermissionContext.jsx` | IMPLEMENTED (owner/manager/cashier/accountant/stock_keeper/viewer/evaluator) |
| Multi-business per user | `Membership` table, business switcher in sidebar | IMPLEMENTED |
| Sales → stock → payment → receivable → audit as one transaction | `api/commerce_routes.py::create_sale` | IMPLEMENTED (the "one sale updates everything" rule is already true for POS→stock→payment→receivable→audit; loyalty/AI-demand-history/commission are not) |
| Offline POS with idempotent sync | `frontend/src/pages/Pos.jsx` (invoice-number idempotency, localStorage outbox) | IMPLEMENTED for single-device; no cross-device stock-conflict detection yet |
| Void → approval-shaped flow | `api/finance_routes.py::void_sale` (owner/manager only, reason required, reuses the return path) | IMPLEMENTED as a permission gate, not a generalised approval-inbox |
| Cash day-close with variance + reason | `api/insights_routes.py::cash_close` | IMPLEMENTED |
| Dead-stock / ABC-XYZ / price-watch / Cash-Locked Meter | `api/insights_advanced_routes.py` (2026-09-29) | IMPLEMENTED |
| Baki ageing (FIFO) | `api/receivables_routes.py` | IMPLEMENTED |
| Reorder planner → PO in one tap | `api/planning_routes.py` | IMPLEMENTED (reorder only; no purchase-request→approval chain yet) |
| Bulk CSV/XLSX onboarding import | `api/bulk_import_routes.py` | IMPLEMENTED for products/customers/opening stock |
| Batch/expiry/FEFO (pharmacy pack) | `api/batches.py` | IMPLEMENTED |
| SQLite dev / Postgres prod | `api/database.py`, `DATABASE_URL` | PARTIAL — code is DB-portable; **no Postgres deployment exists, dev is SQLite only** |
| Double-entry accounting engine | `api/accounting.py`, `api/accounting_routes.py`, `Account`/`JournalEntry`/`JournalLine` (2026-09-29) | IMPLEMENTED (first slice): chart of accounts, balanced journal posting from sale/return/void/purchase-receipt/expense/settlement, trial balance, P&L, balance sheet. Still missing: an accounts editor, bank reconciliation, VAT export, cash-close-variance posting |
| Approval inbox / configurable approval rules | `api/approvals.py`, `api/approval_routes.py`, `ApprovalRule`/`ApprovalRequest` (2026-09-29) | IMPLEMENTED (first slice): `expense_amount` only. Discount/refund/void/purchase/credit-limit-increase gates from the blueprint are not yet wired — add one kind at a time, per `api/approvals.py`'s module docstring |
| Workforce (attendance, commission, payroll, targets) | none | NOT BUILT |
| SMS/WhatsApp/payment-gateway/printer/barcode-hardware integration | none live (messages are copy/open links only) | NOT BUILT |
| Vertical packs beyond pharmacy (fashion variants, restaurant recipe/KDS, wholesale price tiers+route, electronics serial/IMEI, manufacturing BOM, service job-card, salon booking, clinic admin, coaching, agro, transport, rental) | none | NOT BUILT — `verticals.js` only distinguishes "has expiry" today |
| Signup → 8-12 step wizard with opening balances/staff invite | `Onboarding.jsx` creates one org + one branch; no multi-step wizard | PARTIAL |
| AI Copilot (Bangla Q&A grounded in the shop's own data) | none | NOT BUILT (this is `docs/THESIS_PRODUCT_MASTER_PLAN.md` section 7, L1/L2) |

## Build order (reconciling the user's "10 most important things" with what exists)

The user's own priority list is sound and matches this repo's actual gaps. Adjusted
for what's already done:

1. ~~Login, organization, branch, staff role, security~~ — **done** (`api/auth*.py`, `api/permissions.py`).
2. ~~POS, invoice, payment, due, return~~ — **done**, plus void, wholesale tier, credit limit.
3. ~~Stock, purchase, supplier, warehouse, transfer~~ — **done** for single-warehouse-per-branch; no multi-warehouse-per-branch yet.
4. ~~Accounting engine (journal, ledger, trial balance, P&L, balance sheet)~~ — **done** (2026-09-29, `api/accounting.py`): first slice, see the table above for what's still missing.
5. ~~Approval Inbox + configurable approval rules~~ — **done** (2026-09-29, `expense_amount` only): the mechanism is real and reusable; the next real step is adding a second kind (discount-percent on a POS line is the best next candidate — it is the blueprint's own first example and touches the sale flow, which is the highest-traffic path, so proving the pattern holds there matters most).
6. **Offline multi-device conflict detection** (two devices oversell the same unit) — partially covered by the DB's row-level stock lock, but no explicit conflict UI/alert when it happens offline-to-offline.
7. **Real integrations**: SMS provider (adapter interface, non-masking default), payment-gateway webhook (bKash/Nagad confirmation), printer/barcode-hardware — currently zero live integrations.
8. **Business-setup wizard v2** (the 8-12 step flow with opening balances, staff invite, receipt design, in one guided pass) — today's `Onboarding.jsx` is a single form.
9. **First non-pharmacy vertical pack built for real** (candidate: **Fashion/Boutique** — variant matrix, exchange, seasonal collection — good stress-test of "vertical = configuration, not a fork") or **Restaurant** (table/KDS/recipe) — either proves the framework; do one well before a second.
10. **Postgres + RLS + deployment container** — needed before any of the above matters outside a single laptop demo.
11. Remaining 13 vertical packs, AI Copilot, mobile-native wrapper — Wave 3, after 1-10 above are real.

**Do not build items 9+ before 4-5.** A vertical pack without a real accounting
engine and approval system under it is a shinier POS, not a Business OS — the
exact trap the user is trying to get out of.

## Next concrete step

**A second approval kind: `discount_percent`.** Wire `commerce_routes.create_sale`
so a line discount at or above an owner-set percentage held back by
`needs_approval(db, org_id, "discount_percent", ...)` does not complete the sale
immediately — but unlike an expense, a POS sale cannot simply sit "pending" while
a queue waits, so this needs a synchronous manager-override design (a manager PIN
or a second login confirms in the same request) rather than the async inbox
pattern `expense_amount` uses. Work out that UX before writing the route: it is
the harder half of this step, not the approval-rule plumbing itself.
