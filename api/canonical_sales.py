"""Builds an organization's sales history into the canonical schema
ml/real_pipeline.py and ml/serving.py expect. Shared by analytics_routes.py
(live recommendations) and data_import_routes.py (CSV export and the
train-on-my-own-data endpoint) so there is exactly one query, not two that
could drift apart.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain_models import Product, SalesOrder, SalesOrderItem


def canonical_sales_frame(db: Session, organization_id: str) -> pd.DataFrame:
    rows = db.execute(
        select(SalesOrder, SalesOrderItem, Product)
        .join(SalesOrderItem, SalesOrderItem.order_id == SalesOrder.id)
        .join(Product, Product.id == SalesOrderItem.product_id)
        .where(SalesOrder.organization_id == organization_id)
    ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "organization_id": order.organization_id, "branch_id": order.branch_id,
        "invoice_id": order.id, "line_id": line.id, "sold_at": order.sold_at,
        "customer_pseudo_id": order.customer_id or "ANONYMOUS", "sku": product.sku,
        "category": product.category or "", "quantity": float(line.quantity),
        "unit_price": float(line.unit_price), "unit_cost_at_sale": float(line.unit_cost_at_sale),
        "discount_amount": float(line.discount_amount), "line_total": float(line.line_total),
        "channel": order.channel, "status": order.status,
    } for order, line, product in rows])
