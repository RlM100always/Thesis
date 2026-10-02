"""Commission rate lookup and the earn/clawback arithmetic (SRD Panel H05).

A flat percentage of net sale revenue, credited to whoever rang up the sale.
Off (``active=False``) by default, same as loyalty -- sales post identically
either way, this is additive.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain_models import CommissionEntry, CommissionRule

ZERO = Decimal("0")
DEFAULT_RATE_PERCENT = Decimal("2.00")


def seed_default_rule(db: Session, org_id: str) -> None:
    if db.scalar(select(CommissionRule.id).where(CommissionRule.organization_id == org_id)):
        return
    db.add(CommissionRule(organization_id=org_id, rate_percent=DEFAULT_RATE_PERCENT, active=False))


def get_rule(db: Session, org_id: str) -> CommissionRule | None:
    return db.scalar(select(CommissionRule).where(CommissionRule.organization_id == org_id))


def commission_for(rule: CommissionRule | None, net_sale_amount: Decimal) -> Decimal:
    if rule is None or not rule.active or net_sale_amount <= 0:
        return ZERO
    return (net_sale_amount * rule.rate_percent / Decimal("100")).quantize(Decimal("0.01"))


def earned_for_sale(db: Session, org_id: str, sales_order_id: str) -> CommissionEntry | None:
    """The original earn entry for a sale, if commission was active when it was made."""
    return db.scalar(select(CommissionEntry).where(
        CommissionEntry.organization_id == org_id, CommissionEntry.sales_order_id == sales_order_id,
        CommissionEntry.reason == "earned",
    ))


def clawed_back_for_sale(db: Session, org_id: str, sales_order_id: str) -> Decimal:
    from sqlalchemy import func
    total = db.scalar(select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
        CommissionEntry.organization_id == org_id, CommissionEntry.sales_order_id == sales_order_id,
        CommissionEntry.reason == "clawback"))
    return -Decimal(total)  # clawback amounts are stored negative; return as a positive "already taken back"


def balance_for(db: Session, org_id: str, user_id: str) -> Decimal:
    from sqlalchemy import func
    total = db.scalar(select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(
        CommissionEntry.organization_id == org_id, CommissionEntry.user_id == user_id))
    return Decimal(total)
