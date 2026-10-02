"""Operational KPIs and constraint-aware B-SMART action candidates.

These endpoints use only the active tenant's canonical records.  With little
history they deliberately return transparent statistical baselines; a trained
real-data model can later replace the forecast estimate without changing the
action contract or the UI.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import pandas as pd

from ml.serving import (
    predict_churn_proba, predict_daily_rates, predict_return_risk, predict_segments,
)

from .auth import CurrentMembership
from .permissions import require_permission
from .canonical_sales import canonical_sales_frame
from .database import get_db
from .domain_models import (
    Branch, Customer, Expense, InventoryBalance, LedgerEntry, Product,
    PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem, SalesReturn,
    Supplier,
)

router = APIRouter(prefix="/api/app")
Db = Annotated[Session, Depends(get_db)]


def _money(value) -> float:
    return round(float(value or 0), 2)


@router.get("/dashboard", tags=["business-analytics"])
def operational_dashboard(
    membership: CurrentMembership, db: Db,
    branch_id: str | None = None, days: int = Query(default=30, ge=7, le=365),
):
    require_permission(membership, "dashboard:read")
    org_id = membership.organization_id
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    sales_filters = [SalesOrder.organization_id == org_id, SalesOrder.sold_at >= start]
    expense_filters = [Expense.organization_id == org_id, Expense.incurred_at >= start]
    if branch_id:
        sales_filters.append(SalesOrder.branch_id == branch_id)
        expense_filters.append(Expense.branch_id == branch_id)

    sales_total = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(*sales_filters))
    sale_count = db.scalar(select(func.count(SalesOrder.id)).where(*sales_filters)) or 0
    expenses = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(*expense_filters))
    returns_filters = [SalesReturn.organization_id == org_id, SalesReturn.returned_at >= start]
    if branch_id:
        returns_filters.append(SalesReturn.branch_id == branch_id)
    returns = db.scalar(select(func.coalesce(func.sum(SalesReturn.total), 0)).where(*returns_filters))

    item_statement = select(
        func.coalesce(func.sum(SalesOrderItem.line_total), 0),
        func.coalesce(func.sum(SalesOrderItem.unit_cost_at_sale * SalesOrderItem.quantity), 0),
    ).join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id).where(*sales_filters)
    revenue_lines, cost = db.execute(item_statement).one()
    # A product sold without a recorded cost would otherwise look 100% profit. Report
    # the profit on lines whose cost IS known, and how much of the revenue that covers.
    known_revenue, known_cost = db.execute(item_statement.where(SalesOrderItem.unit_cost_at_sale > 0)).one()
    cost_coverage = float(known_revenue) / float(revenue_lines) if revenue_lines else None

    inventory_filters = [Product.organization_id == org_id, Product.active.is_(True)]
    balance_join = (
        (InventoryBalance.product_id == Product.id)
        & (InventoryBalance.organization_id == org_id)
    )
    if branch_id:
        balance_join = balance_join & (InventoryBalance.branch_id == branch_id)
    inventory_rows = db.execute(
        select(Product, func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .outerjoin(InventoryBalance, balance_join)
        .where(*inventory_filters).group_by(Product.id)
    ).all()
    low_stock = sum(1 for product, qty in inventory_rows if qty <= product.reorder_level)
    stock_value = sum(Decimal(str(qty or 0)) * product.cost_price for product, qty in inventory_rows)

    ledger = {}
    for ledger_type in ("receivable", "payable"):
        ledger[ledger_type] = db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount_delta), 0)).where(
            LedgerEntry.organization_id == org_id, LedgerEntry.ledger_type == ledger_type,
        ))

    daily_rows = db.execute(select(
        func.date(SalesOrder.sold_at), func.sum(SalesOrder.total), func.count(SalesOrder.id)
    ).where(*sales_filters).group_by(func.date(SalesOrder.sold_at)).order_by(func.date(SalesOrder.sold_at))).all()
    daily_map = {str(day): (_money(total), count) for day, total, count in daily_rows}
    daily = []
    for offset in range(days - 1, -1, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        total, count = daily_map.get(day, (0.0, 0))
        daily.append({"date": day, "sales": total, "orders": count})

    return {
        "period_days": days,
        "sales": _money(sales_total), "net_sales": _money(sales_total - returns),
        "orders": sale_count, "average_order_value": _money(sales_total / sale_count if sale_count else 0),
        "gross_profit_before_expenses": _money(revenue_lines - cost - returns),
        "gross_profit_known": _money(known_revenue - known_cost), "cost_coverage": cost_coverage,
        "expenses": _money(expenses),
        "estimated_operating_result": _money(revenue_lines - cost - returns - expenses),
        "returns": _money(returns), "stock_value_at_cost": _money(stock_value),
        "low_stock_products": low_stock, "product_count": len(inventory_rows),
        "customer_count": db.scalar(select(func.count(Customer.id)).where(Customer.organization_id == org_id)) or 0,
        "supplier_count": db.scalar(select(func.count(Supplier.id)).where(Supplier.organization_id == org_id)) or 0,
        "receivable": _money(ledger["receivable"]), "payable": _money(ledger["payable"]),
        "daily_sales": daily,
    }


@router.get("/recommendations", tags=["strategy-optimization"])
def recommendations(
    membership: CurrentMembership, db: Db,
    branch_id: str | None = None, top_k: int = Query(default=20, ge=1, le=100),
):
    """Rank feasible inventory, retention, and anomaly actions by transparent utility."""
    require_permission(membership, "recommendations:read")
    org_id = membership.organization_id
    now = datetime.now(timezone.utc)
    history_start = now - timedelta(days=28)
    branches = list(db.scalars(select(Branch).where(
        Branch.organization_id == org_id, Branch.active.is_(True),
        *([Branch.id == branch_id] if branch_id else []),
    )))
    supplier_leads = list(db.scalars(select(Supplier.typical_lead_days).where(
        Supplier.organization_id == org_id, Supplier.typical_lead_days > 0,
    )))
    default_lead = max(1, round(sum(supplier_leads) / len(supplier_leads))) if supplier_leads else 7
    actions = []

    sales_frame = canonical_sales_frame(db, org_id)
    modeled_rates = predict_daily_rates(org_id, sales_frame)
    return_risk = predict_return_risk(org_id, sales_frame)
    churn_probs = predict_churn_proba(org_id, sales_frame)
    segments = predict_segments(org_id, sales_frame)
    customer_tier = (segments or {}).get("customer_tier", {})
    tier_weight = {"VIP": 1.5, "High value": 1.2, "Moderate value": 1.0, "Low value": 0.7}

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
            observed_days = 28
            modeled_rate = modeled_rates.get((branch.id, product.sku))
            using_model = modeled_rate is not None
            daily_rate = modeled_rate if using_model else float(sold or 0) / observed_days
            lead_demand = daily_rate * default_lead
            safety = max(float(product.reorder_level), daily_rate * 3)
            reorder = max(0, math.ceil(lead_demand + safety - float(stock or 0) - float(incoming or 0)))
            if reorder:
                margin = max(0.0, float(product.selling_price - product.cost_price))
                avoided_margin = min(reorder, math.ceil(lead_demand)) * margin
                carrying_risk = reorder * float(product.cost_price) * 0.02
                risk_prob = return_risk.get((branch.id, product.sku))
                return_risk_cost = (risk_prob or 0.0) * reorder * float(product.cost_price) * 0.5
                utility = avoided_margin - carrying_risk - return_risk_cost
                basis_bn = "trained demand model-এর পূর্বাভাস অনুযায়ী দৈনিক চাহিদা" if using_model else "গত ২৮ দিনের বিক্রি থেকে দৈনিক চাহিদা"
                risk_note_bn = f" এই পণ্যে return হওয়ার সম্ভাবনা {risk_prob*100:.0f}%, তাই utility কমানো হয়েছে।" if risk_prob else ""
                actions.append({
                    "type": "reorder", "priority": "high" if float(stock or 0) <= float(product.reorder_level) else "medium",
                    "title_bn": f"{product.name} পুনরায় অর্ডার করুন",
                    "explanation_bn": f"{basis_bn} {daily_rate:.2f} ইউনিট। {default_lead} দিনের lead time, safety stock, বর্তমান stock ও incoming stock ধরে হিসাব করা হয়েছে।{risk_note_bn}",
                    "branch_id": branch.id, "branch_name": branch.name, "entity_id": product.id,
                    "recommended_quantity": reorder, "current_stock": float(stock or 0),
                    "return_risk_probability": round(risk_prob, 3) if risk_prob is not None else None,
                    "incoming_stock": float(incoming or 0), "forecast_lead_demand": round(lead_demand, 2),
                    "utility_bdt": round(utility, 2), "confidence": "model" if using_model else "baseline",
                    "method": "trained demand model (ml/real_pipeline.py)" if using_model else "28-day demand-rate baseline + inventory constraints",
                })

    customer_rows = db.execute(select(
        Customer, func.max(SalesOrder.sold_at), func.sum(SalesOrder.total), func.count(SalesOrder.id)
    ).join(SalesOrder, SalesOrder.customer_id == Customer.id).where(
        Customer.organization_id == org_id
    ).group_by(Customer.id)).all()
    consent_excluded = 0
    for customer, last_sale, total, orders in customer_rows:
        inactive = (now - last_sale.replace(tzinfo=last_sale.tzinfo or timezone.utc)).days
        if inactive < 60:
            continue
        if not customer.marketing_consent:
            consent_excluded += 1
            continue
        avg_order = float(total or 0) / max(1, orders)
        contact_cost = 5.0
        tier = customer_tier.get(customer.id)
        weight = tier_weight.get(tier, 1.0)
        churn_prob = churn_probs.get(customer.id)
        using_churn_model = churn_prob is not None
        retention_uplift = (1 - churn_prob) if using_churn_model else 0.12
        expected_recovery = avg_order * retention_uplift * weight
        basis_bn = f"trained churn model অনুযায়ী ফেরার সম্ভাবনা {(1-churn_prob)*100:.0f}%" if using_churn_model else "baseline ১২% retention uplift ধরে"
        tier_note_bn = f" এই কাস্টমার \"{tier}\" tier-এ (live segmentation), তাই মান {weight}× adjust করা হয়েছে।" if tier else ""
        actions.append({
            "type": "retention", "priority": "high" if inactive >= 90 else "medium",
            "title_bn": f"{customer.display_name or customer.code}-এর সঙ্গে যোগাযোগ করুন",
            "explanation_bn": f"শেষ কেনাকাটা {inactive} দিন আগে। {basis_bn}; সম্ভাব্য লাভ থেকে ৳{contact_cost:.0f} যোগাযোগ খরচ বাদ দিয়ে rank করা হয়েছে।{tier_note_bn}",
            "entity_id": customer.id, "inactive_days": inactive, "customer_tier": tier,
            "churn_probability": round(1 - churn_prob, 3) if using_churn_model else None,
            "lifetime_sales": _money(total), "utility_bdt": round(expected_recovery-contact_cost, 2),
            "confidence": "model" if using_churn_model else "baseline",
            "method": "trained churn model (ml/real_pipeline.py)" if using_churn_model else "recency-value expected-utility baseline",
        })

    # Compare the latest complete day with the preceding four weeks.
    day_rows = db.execute(select(
        func.date(SalesOrder.sold_at), func.sum(SalesOrder.total)
    ).where(SalesOrder.organization_id == org_id, SalesOrder.sold_at >= history_start,
            *([SalesOrder.branch_id == branch_id] if branch_id else [])
    ).group_by(func.date(SalesOrder.sold_at)).order_by(func.date(SalesOrder.sold_at))).all()
    values = [float(total) for _, total in day_rows]
    anomaly = None
    if len(values) >= 8:
        reference, latest = values[:-1], values[-1]
        mean = sum(reference) / len(reference)
        variance = sum((x-mean) ** 2 for x in reference) / len(reference)
        z = (latest-mean) / math.sqrt(variance) if variance > 0 else 0
        if abs(z) >= 2:
            anomaly = {"date": str(day_rows[-1][0]), "sales": latest, "z_score": round(z, 2),
                       "direction": "high" if z > 0 else "low",
                       "message_bn": "অস্বাভাবিক বেশি বিক্রি যাচাই করুন" if z > 0 else "অস্বাভাবিক কম বিক্রির কারণ যাচাই করুন"}

    actions.sort(key=lambda item: item.get("utility_bdt", 0), reverse=True)
    all_confidences = [a["confidence"] for a in actions if a["type"] in ("reorder", "retention")]
    if all_confidences and all(c == "model" for c in all_confidences):
        model_status = "model"
    elif any(c == "model" for c in all_confidences):
        model_status = "mixed"
    else:
        model_status = "baseline"
    model_notes_bn = {
        "model": "প্রশিক্ষিত demand model-এর পূর্বাভাস সরাসরি ব্যবহার করা হয়েছে।",
        "mixed": "কিছু পণ্যে প্রশিক্ষিত model, বাকিগুলোতে baseline ব্যবহার করা হয়েছে (যথেষ্ট history না থাকায়)।",
        "baseline": "যথেষ্ট real historical data দিয়ে model train না হওয়া পর্যন্ত স্বচ্ছ baseline ব্যবহৃত হচ্ছে; এটি ML prediction হিসেবে দাবি করা হচ্ছে না।",
    }
    return {
        "generated_at": now.isoformat(), "actions": actions[:top_k], "anomaly": anomaly,
        "contact_without_consent_excluded": consent_excluded,
        "model_status": model_status,
        "model_note_bn": model_notes_bn[model_status],
        "segments_available": segments is not None,
        "return_risk_available": bool(return_risk),
    }


@router.get("/segments", tags=["strategy-optimization"])
def live_segments(membership: CurrentMembership, db: Db):
    """Live K-Means customer tiers for this organization's own data, trained by
    `python -m ml.real_pipeline` (or the "AI মডেল প্রশিক্ষণ" button). Returns
    `available: false` with a reason when no segment model has been trained yet
    -- never a guessed tier."""
    require_permission(membership, "recommendations:read")
    org_id = membership.organization_id
    sales_frame = canonical_sales_frame(db, org_id)
    segments = predict_segments(org_id, sales_frame)
    if segments is None:
        return {
            "available": False,
            "reason": "এই organization-এর জন্য segmentation model এখনো train হয়নি। "
                      '"AI মডেল প্রশিক্ষণ" চালান অথবা python -m ml.real_pipeline চালান।',
        }
    customers = db.execute(select(Customer.id, Customer.display_name, Customer.code).where(
        Customer.organization_id == org_id,
    )).all()
    name_map = {row.id: (row.display_name or row.code) for row in customers}
    tiers: dict[str, list[dict]] = {}
    for customer_id, tier in segments["customer_tier"].items():
        tiers.setdefault(tier, []).append({"customer_id": customer_id, "name": name_map.get(customer_id, customer_id)})
    return {
        "available": True, "k": segments["k"],
        "tiers": {tier: {"count": len(members), "members": members[:50]} for tier, members in tiers.items()},
    }
