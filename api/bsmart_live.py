"""B-SMART Algorithm 1, run on an organization's own live data.

`13_bsmart_recommendation_engine.py` is the thesis's frozen-dataset run --
real medicine catalogue, real BD demand shape, but a research CSV, not any
particular shop's own sales. Before this module, a tenant's "B-SMART
সুপারিশ" page (`api/bsmart_routes.py::import_run`) could only *import* that
research run; there was no way to run Algorithm 1 against the shop's own
operational database. `/api/app/recommendations` (`analytics_routes.py`)
already ranks reorder/retention actions live, but it is a separate, simpler
endpoint for the "আজকের করণীয়" page and does not feed the
Recommendation/decision/outcome tables the B-SMART page and thesis
monitoring loop depend on, and it has no near-expiry action type.

This module is deliberately a second implementation of the reorder/retention
scoring, not a shared call into `analytics_routes.recommendations()`: that
endpoint is already tested and in daily use on "আজকের করণীয়", and unifying
the two risks changing its behaviour for an unrelated feature. The formulas
here mirror it (same lead-time/safety-stock/carrying-cost shape, same
consent gate) plus the thesis engine's near-expiry action type and quota
system, built from data this operational schema actually has: `Batch`/
`BatchStock` for expiry, `Supplier.typical_lead_days` for lead time.

Unlike the CSV engine, there is no pack size, MOQ, cold-chain flag or
storage capacity field on `Product` yet (see docs/FEATURE_STATUS.md "not
built yet"), so those constraints are simply absent here rather than
approximated -- an honest reduction in scope, not a silent one.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ml.serving import predict_daily_rates

from .batches import NEAR_EXPIRY_DAYS
from .canonical_sales import canonical_sales_frame
from .domain_models import (
    Batch, BatchStock, Branch, Customer, InventoryBalance, Product,
    PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem, Supplier,
)

ASSUMPTIONS = {
    "history_days": 28,
    "safety_stock_multiple_days": 3,   # matches analytics_routes.recommendations
    "carrying_rate": 0.02,             # matches analytics_routes.recommendations
    "contact_cost_bdt": 5.0,           # matches analytics_routes.recommendations
    "retention_uplift": 0.12,          # matches analytics_routes.recommendations
    "retention_inactive_days": 60,     # matches analytics_routes.recommendations
    "near_expiry_days": NEAR_EXPIRY_DAYS,
    "expiry_markdown_pct": 0.30,       # matches 13_bsmart_recommendation_engine.py
    "expiry_writeoff_share": 0.60,     # matches 13_bsmart_recommendation_engine.py
    "lambda_risk": 0.5,                # matches 13_bsmart_recommendation_engine.py
    "top_k": 15,
    "top_k_quota": {"reorder": 5, "expiry": 5, "retention": 5},
}


def _money(value) -> float:
    return round(float(value or 0), 2)


def _default_lead_days(db: Session, org_id: str) -> int:
    leads = list(db.scalars(select(Supplier.typical_lead_days).where(
        Supplier.organization_id == org_id, Supplier.typical_lead_days > 0)))
    return max(1, round(sum(leads) / len(leads))) if leads else 7


def build_reorder_candidates(db: Session, org_id: str, branches: list[Branch], now: datetime) -> list[dict]:
    history_start = now - timedelta(days=ASSUMPTIONS["history_days"])
    default_lead = _default_lead_days(db, org_id)
    modeled_rates = predict_daily_rates(org_id, canonical_sales_frame(db, org_id))
    candidates = []
    for branch in branches:
        rows = db.execute(
            select(Product, func.coalesce(InventoryBalance.quantity, 0))
            .outerjoin(InventoryBalance, (
                (InventoryBalance.product_id == Product.id)
                & (InventoryBalance.organization_id == org_id)
                & (InventoryBalance.branch_id == branch.id)
            ))
            .where(Product.organization_id == org_id, Product.active.is_(True))
        ).all()
        for product, stock in rows:
            sold = db.scalar(select(func.coalesce(func.sum(SalesOrderItem.quantity), 0))
                .join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id)
                .where(SalesOrder.organization_id == org_id, SalesOrder.branch_id == branch.id,
                       SalesOrder.sold_at >= history_start, SalesOrderItem.product_id == product.id))
            incoming = db.scalar(select(func.coalesce(func.sum(
                PurchaseOrderItem.quantity - PurchaseOrderItem.received_quantity
            ), 0)).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id).where(
                PurchaseOrder.organization_id == org_id, PurchaseOrder.branch_id == branch.id,
                PurchaseOrder.status.in_(["ordered", "partial"]),
                PurchaseOrderItem.product_id == product.id,
            ))
            modeled_rate = modeled_rates.get((branch.id, product.sku))
            using_model = modeled_rate is not None
            daily_rate = modeled_rate if using_model else float(sold or 0) / ASSUMPTIONS["history_days"]
            lead_demand = daily_rate * default_lead
            safety = max(float(product.reorder_level), daily_rate * ASSUMPTIONS["safety_stock_multiple_days"])
            reorder_qty = max(0, math.ceil(lead_demand + safety - float(stock or 0) - float(incoming or 0)))
            if reorder_qty <= 0:
                continue

            margin = max(0.0, float(product.selling_price - product.cost_price))
            unit_cost = float(product.cost_price)
            benefit = min(reorder_qty, math.ceil(lead_demand)) * margin
            cost = reorder_qty * unit_cost * ASSUMPTIONS["carrying_rate"]
            risk = ASSUMPTIONS["lambda_risk"] * cost   # no residual-std estimate live yet; carrying cost stands in as the uncertainty proxy
            utility = benefit - cost - risk
            basis = ("trained demand model-এর পূর্বাভাস অনুযায়ী দৈনিক চাহিদা" if using_model
                      else f"গত {ASSUMPTIONS['history_days']} দিনের বিক্রি থেকে দৈনিক চাহিদা")

            candidates.append({
                "type": "reorder", "sku": product.sku, "division": branch.name,
                "confidence": "model" if using_model else "baseline",
                "reorder_qty": reorder_qty,
                "unit_cost_bdt": round(unit_cost, 2), "margin_per_unit_bdt": round(margin, 2),
                "benefit_bdt": _money(benefit), "action_cost_bdt": _money(cost), "risk_bdt": _money(risk),
                "utility_bdt": _money(utility), "reorder_cost_bdt": _money(reorder_qty * unit_cost),
                "reason": (f"{product.name} ({branch.name}): {basis} {daily_rate:.2f} ইউনিট। "
                           f"{default_lead} দিনের lead time, safety stock, বর্তমান ও incoming stock ধরে {reorder_qty} ইউনিট অর্ডার প্রয়োজন।"),
                "explanation": {
                    "action": f"Order {reorder_qty} units of {product.name} ({branch.name})",
                    "why": {
                        "forecast_demand_over_lead_time": round(lead_demand, 1),
                        "safety_stock": round(safety, 1),
                        "incoming_stock": float(incoming or 0),
                        "lead_time_days": default_lead,
                        "current_stock": float(stock or 0),
                        "demand_model": "trained demand model" if using_model else f"{ASSUMPTIONS['history_days']}-day sales rate baseline",
                    },
                    "constraints": {"budget": "not gated (no owner-declared budget yet)"},
                    "confidence": "model" if using_model else "baseline",
                },
                "evidence_source": "organization's own sales/inventory/purchase records",
            })
    return candidates


def build_expiry_candidates(db: Session, org_id: str, branches: list[Branch], today: date) -> list[dict]:
    near_days = ASSUMPTIONS["near_expiry_days"]
    horizon = today + timedelta(days=near_days)
    branch_ids = [b.id for b in branches]
    rows = db.execute(
        select(Batch, BatchStock, Product, Branch)
        .join(BatchStock, BatchStock.batch_id == Batch.id)
        .join(Product, Product.id == Batch.product_id)
        .join(Branch, Branch.id == BatchStock.branch_id)
        .where(
            Batch.organization_id == org_id, BatchStock.branch_id.in_(branch_ids),
            BatchStock.quantity > 0, Batch.status == "active",
            Batch.expiry_date.is_not(None), Batch.expiry_date > today, Batch.expiry_date <= horizon,
        )
    ).all()
    candidates = []
    for batch, stock, product, branch in rows:
        units = float(stock.quantity)
        if units <= 0:
            continue
        price = float(product.selling_price)
        unit_cost = float(batch.unit_cost) if batch.unit_cost is not None else float(product.cost_price)
        days_left = (batch.expiry_date - today).days

        markdown_price = price * (1 - ASSUMPTIONS["expiry_markdown_pct"])
        margin_if_marked_down = max(markdown_price - unit_cost, 0.0) * units
        loss_if_ignored = units * ASSUMPTIONS["expiry_writeoff_share"] * unit_cost
        benefit = margin_if_marked_down + loss_if_ignored * ASSUMPTIONS["expiry_writeoff_share"]
        cost = units * max(price - markdown_price, 0.0) * ASSUMPTIONS["expiry_writeoff_share"]
        urgency_risk = 1.0 - (days_left / near_days)
        risk = ASSUMPTIONS["lambda_risk"] * urgency_risk * benefit
        utility = benefit - cost - risk
        if utility <= 0:
            continue  # marking down would destroy more value than it saves

        candidates.append({
            "type": "expiry", "sku": product.sku, "division": branch.name,
            "target_sku": product.id, "confidence": "rule",
            "units_at_risk": round(units, 1), "days_to_earliest_expiry": days_left,
            "unit_cost_bdt": round(unit_cost, 2),
            "benefit_bdt": _money(benefit), "action_cost_bdt": _money(cost), "risk_bdt": _money(risk),
            "utility_bdt": _money(utility),
            "reason": (f"{product.name} ({branch.name}, ব্যাচ {batch.batch_no}): {units:.0f} ইউনিট "
                       f"{near_days} দিনের মধ্যে মেয়াদ শেষ হবে (সবচেয়ে কাছেরটি {days_left} দিনে)। "
                       f"{ASSUMPTIONS['expiry_markdown_pct']*100:.0f}% ছাড়ে বিক্রি করুন, নাহলে "
                       f"{ASSUMPTIONS['expiry_writeoff_share']*100:.0f}% মেয়াদোত্তীর্ণ হয়ে নষ্ট হতে পারে।"),
            "evidence_source": "organization's own batch/expiry ledger",
            "batch_id": batch.id,
        })
    return candidates


def build_retention_candidates(db: Session, org_id: str, now: datetime) -> tuple[list[dict], int]:
    rows = db.execute(select(
        Customer, func.max(SalesOrder.sold_at), func.sum(SalesOrder.total), func.count(SalesOrder.id)
    ).join(SalesOrder, SalesOrder.customer_id == Customer.id).where(
        Customer.organization_id == org_id
    ).group_by(Customer.id)).all()
    candidates = []
    consent_excluded = 0
    for customer, last_sale, total, orders in rows:
        inactive = (now - last_sale.replace(tzinfo=last_sale.tzinfo or timezone.utc)).days
        if inactive < ASSUMPTIONS["retention_inactive_days"]:
            continue
        if not customer.marketing_consent:
            consent_excluded += 1
            continue
        monetary = float(total or 0)
        avg_order = monetary / max(1, orders)
        benefit = ASSUMPTIONS["retention_uplift"] * avg_order
        cost = ASSUMPTIONS["contact_cost_bdt"]
        risk = ASSUMPTIONS["lambda_risk"] * cost   # no churn-probability estimate live yet; contact cost stands in as the uncertainty proxy
        utility = benefit - cost - risk
        candidates.append({
            "type": "retention", "customer_id": customer.id, "confidence": "baseline",
            "monetary_bdt": round(monetary, 2), "inactive_days": inactive,
            "benefit_bdt": _money(benefit), "action_cost_bdt": _money(cost), "risk_bdt": _money(risk),
            "utility_bdt": _money(utility),
            "reason": (f"শেষ কেনাকাটা {inactive} দিন আগে। Marketing consent আছে; "
                       f"গড় বিলের {ASSUMPTIONS['retention_uplift']*100:.0f}% ফেরত-লাভ ধরে "
                       f"৳{cost:.0f} যোগাযোগ খরচ বাদ দেওয়া হয়েছে।"),
            "evidence_source": "organization's own sales history",
            "marketing_consent": True,
        })
    return candidates, consent_excluded


def feasibility_and_rank(
    reorder: list[dict], expiry: list[dict], retention: list[dict], budget_bdt: float | None = None,
) -> tuple[list[dict], list[dict]]:
    """Reorder budget cap, applied only when the owner has actually declared
    one (``OrganizationSetting.reorder_budget_bdt``, Settings -> কাজ ও পেমেন্ট).

    The research-CSV engine declares its budget as a fraction of the *total*
    identified need across hundreds of SKUs -- a reasonable stand-in when no
    real figure exists. That formula degenerates for one live shop's much
    smaller candidate set: a shop with a single item needing reorder has
    ``total_need == that item's own cost``, so a 40%-of-total cap always
    blocks it. Rather than fabricate a number, a live shop that has not set
    a real budget gets every reorder/expiry/retention candidate feasible by
    construction, same as before; only the quota decides R_t. Once a real
    budget exists, it caps reorder the honest way: highest-utility items
    first, until the declared BDT figure runs out.
    """
    audit = []
    for a in expiry + retention:
        a["feasible"], a["infeasible_reason"] = True, None
        audit.append(a)

    if budget_bdt is None:
        for a in reorder:
            a["feasible"], a["infeasible_reason"] = True, None
            a["explanation"]["constraints"]["budget"] = "not gated (no owner-declared budget yet)"
            audit.append(a)
    else:
        spent = 0.0
        for a in sorted(reorder, key=lambda x: x["utility_bdt"], reverse=True):
            cost = a["reorder_cost_bdt"]
            if spent + cost <= budget_bdt:
                a["feasible"], a["infeasible_reason"] = True, None
                spent += cost
                a["explanation"]["constraints"]["budget"] = f"ok (৳{cost:,.0f} of ৳{budget_bdt:,.0f})"
            else:
                a["feasible"] = False
                a["infeasible_reason"] = f"মাসিক রিঅর্ডার বাজেট (৳{budget_bdt:,.0f}) শেষ; ৳{spent:,.0f} ইতিমধ্যে বেশি-উপযোগী পণ্যে খরচ হয়েছে"
                a["explanation"]["constraints"]["budget"] = f"BLOCKED (৳{budget_bdt:,.0f} cap reached)"
            audit.append(a)

    feasible = [a for a in audit if a["feasible"]]
    feasible.sort(key=lambda a: a["utility_bdt"], reverse=True)

    quota = dict(ASSUMPTIONS["top_k_quota"])
    by_type = {t: [a for a in feasible if a["type"] == t] for t in quota}
    top_k, used = [], set()
    for t, want in quota.items():
        take = by_type[t][:want]
        top_k.extend(take)
        used.update(id(a) for a in take)
    if len(top_k) < ASSUMPTIONS["top_k"]:
        for a in feasible:
            if len(top_k) >= ASSUMPTIONS["top_k"]:
                break
            if id(a) not in used:
                top_k.append(a)
                used.add(id(a))
    top_k.sort(key=lambda a: a["utility_bdt"], reverse=True)
    return top_k, audit


def generate(db: Session, org_id: str, branches: list[Branch], budget_bdt: float | None = None) -> dict[str, Any]:
    """Run Algorithm 1 against this organization's own operational data.

    ``budget_bdt`` comes from ``OrganizationSetting.reorder_budget_bdt``
    (Settings -> কাজ ও পেমেন্ট) -- ``None`` when the owner never set one,
    which leaves reorder unconstrained rather than fabricating a cap.

    Returns the same shape `13_bsmart_recommendation_engine.py` writes to
    `output/bsmart_recommendations.json`, so `api/bsmart_routes.py` can
    persist either source through one code path.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    reorder = build_reorder_candidates(db, org_id, branches, now)
    expiry = build_expiry_candidates(db, org_id, branches, today)
    retention, consent_excluded = build_retention_candidates(db, org_id, now)
    r_t, audit = feasibility_and_rank(reorder, expiry, retention, budget_bdt)
    return {
        "cutoff": today.isoformat(),
        "assumptions": ASSUMPTIONS,
        "R_t": r_t,
        "summary": {
            "cutoff": today.isoformat(),
            "reorder_candidates_generated": len(reorder),
            "expiry_candidates_generated": len(expiry),
            "retention_candidates_generated": len(retention),
            "retention_consent_excluded": consent_excluded,
            "total_candidates": len(audit),
            "top_k_size": len(r_t),
            "r_t_type_mix": {t: sum(1 for a in r_t if a["type"] == t) for t in ("reorder", "expiry", "retention")},
        },
    }
