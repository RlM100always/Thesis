"""The Approval Inbox: a threshold-gated action waits for a qualified role
instead of executing immediately.

Only one rule kind exists today — ``expense_amount`` — deliberately: the
blueprint names many (discount, refund, void, purchase, stock adjustment,
credit limit, price change), but each needs its own "hold and replay" wiring
into its own route, and a half-wired approval gate (a rule that silently does
nothing) is worse than an honest single flow. Add a kind here, seed a default
in ``DEFAULT_RULES``, and wire its route the way ``finance_routes.create_expense``
does, when the next one is built.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain_models import ApprovalRule, Membership, User
from .security import verify_password

# kind, threshold, approver_role. Seeded once per organization at creation
# (and by a one-off migration for organizations that existed before this).
DEFAULT_RULES: list[tuple[str, Decimal, str]] = [
    ("expense_amount", Decimal("5000"), "owner"),
    ("discount_percent", Decimal("10"), "manager"),
    ("refund_amount", Decimal("1000"), "manager"),
]

# A role's standing to approve, highest first. Someone at or above the rule's
# ``approver_role`` needs no one else's sign-off — they already are the authority.
RANK: dict[str, int] = {
    "evaluator": 0, "viewer": 0, "cashier": 1, "stock_keeper": 1,
    "accountant": 2, "manager": 3, "owner": 4,
}


def seed_default_rules(db: Session, org_id: str) -> None:
    existing = set(db.scalars(select(ApprovalRule.kind).where(ApprovalRule.organization_id == org_id)))
    for kind, threshold, approver_role in DEFAULT_RULES:
        if kind in existing:
            continue
        db.add(ApprovalRule(organization_id=org_id, kind=kind, threshold=threshold, approver_role=approver_role))


def needs_approval(db: Session, org_id: str, kind: str, amount: Decimal, requester_role: str) -> ApprovalRule | None:
    """The rule that holds this action back, or ``None`` if it may proceed now."""
    rule = db.scalar(select(ApprovalRule).where(
        ApprovalRule.organization_id == org_id, ApprovalRule.kind == kind, ApprovalRule.active.is_(True)))
    if rule is None or amount < rule.threshold:
        return None
    if RANK.get(requester_role, 0) >= RANK.get(rule.approver_role, 4):
        return None
    return rule


def verify_override(db: Session, org_id: str, rule: ApprovalRule, email: str | None, password: str | None) -> bool:
    """A qualifying manager/owner types their own credentials inline, right at the
    till, instead of the sale sitting in an async inbox — a checkout cannot wait
    for someone to open a separate screen. Returns whether that person is real,
    entered their own password, belongs to this business, and ranks high enough.
    """
    if not email or not password:
        return False
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        return False
    membership = db.scalar(select(Membership).where(
        Membership.organization_id == org_id, Membership.user_id == user.id, Membership.active.is_(True)))
    if membership is None:
        return False
    return RANK.get(membership.role, 0) >= RANK.get(rule.approver_role, 4)
