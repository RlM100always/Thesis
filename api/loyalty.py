"""Loyalty points: earn on sale, redeem as a discount, an append-only ledger
for the balance — the same discipline `LedgerEntry` already uses for baki.

Off by default (``DEFAULT_RATE`` seeds an inactive rule) — a shop that never
turns it on sells exactly as before, no points, no surprise line on a receipt.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .domain_models import LoyaltyEntry, LoyaltyRule

ZERO = Decimal("0")
# 1 point per ৳100 spent, each point worth ৳0.50 when redeemed — inactive until the owner turns it on.
DEFAULT_RATE = (Decimal("100"), Decimal("0.50"))


def seed_default_rule(db: Session, org_id: str) -> None:
    if db.scalar(select(LoyaltyRule.id).where(LoyaltyRule.organization_id == org_id)):
        return
    points_per_taka, redemption_value = DEFAULT_RATE
    db.add(LoyaltyRule(
        organization_id=org_id, points_per_taka=points_per_taka,
        redemption_value=redemption_value, active=False,
    ))


def get_rule(db: Session, org_id: str) -> LoyaltyRule | None:
    return db.scalar(select(LoyaltyRule).where(LoyaltyRule.organization_id == org_id))


def balance(db: Session, org_id: str, customer_id: str) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(LoyaltyEntry.points_delta), 0)).where(
        LoyaltyEntry.organization_id == org_id, LoyaltyEntry.customer_id == customer_id))
    return Decimal(total)


class RedemptionPlan(NamedTuple):
    points: Decimal
    discount: Decimal


def plan_redemption(rule: LoyaltyRule | None, available_points: Decimal, requested_points: Decimal) -> RedemptionPlan:
    """How many points can actually be spent, and what they are worth — never
    more than the customer has, never more than the rule allows right now."""
    if rule is None or not rule.active or requested_points <= 0:
        return RedemptionPlan(ZERO, ZERO)
    points = min(requested_points, available_points)
    if points <= 0:
        return RedemptionPlan(ZERO, ZERO)
    return RedemptionPlan(points, (points * rule.redemption_value).quantize(Decimal("0.01")))


def points_earned(rule: LoyaltyRule | None, net_sale_amount: Decimal) -> Decimal:
    """Whole points only — a customer never sees a fraction of a point."""
    if rule is None or not rule.active or rule.points_per_taka <= 0 or net_sale_amount <= 0:
        return ZERO
    return (net_sale_amount / rule.points_per_taka).to_integral_value(rounding=ROUND_DOWN)
