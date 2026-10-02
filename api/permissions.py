"""Role → permission matrix for tenant-scoped API routes.

Every route checks a *permission* (``resource:action``), never a role name, so
adding a role or moving a capability is one edit here. ``owner`` holds every
permission. The matrix is enforced server-side; hiding a button in the UI is a
convenience, not a control.

Design notes
------------
* ``cashier`` deliberately has no ``dashboard:read``/``expenses:read``/
  ``ledger:read``: a till operator does not need cost, profit or payables.
* ``manager`` cannot pay suppliers or manage staff (matches the behaviour the
  routes had before this matrix existed).
* ``evaluator`` is a read-only research role for a supervisor or examiner.
* B-SMART decisions are owner/manager only; a ``viewer`` or ``evaluator`` can
  read recommendations and monitoring but can never record a decision.
"""

from __future__ import annotations

from fastapi import HTTPException

ROLES: tuple[str, ...] = (
    "owner", "manager", "cashier", "accountant", "stock_keeper", "viewer", "evaluator", "rider",
)

ALL_PERMISSIONS: frozenset[str] = frozenset({
    "catalog:read", "catalog:write",
    "inventory:read", "inventory:adjust",
    "sales:read", "sales:create", "sales:void",
    "orders:read", "orders:create", "orders:fulfill",
    "returns:read", "returns:create",
    "customers:read", "customers:write",
    "suppliers:read", "suppliers:write",
    "purchases:read", "purchases:create", "purchases:receive",
    "purchase_returns:read", "purchase_returns:create", "purchase_returns:dispatch", "purchase_returns:settle",
    "payments:customer", "payments:supplier",
    "expenses:read", "expenses:write",
    "ledger:read",
    "dashboard:read", "recommendations:read",
    "bsmart:read", "bsmart:import", "bsmart:decide", "bsmart:outcome",
    "monitoring:read",
    "imports:write", "dataset:export", "model:train",
    "branches:write",
    "staff:read", "staff:manage",
    "audit:read",
    "cash:read", "cash:close",
    "inventory:transfer",
    "settings:write",
    "notifications:read", "notifications:send",
    "approvals:read", "approvals:decide",
    "tickets:read", "tickets:write",
    "leads:read", "leads:write",
    "feedback:read", "feedback:write",
    "attendance:read", "attendance:correct",
    "leave:read", "leave:decide",
    "roster:write",
    "commission:read",
    "targets:write",
    "deliveries:read", "deliveries:write",
    "advances:read", "advances:write",
    "payroll:read", "payroll:write", "payroll:approve", "payroll:pay",
    "period:close",
})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": ALL_PERMISSIONS,
    "manager": ALL_PERMISSIONS - {
        "staff:manage", "payments:supplier", "settings:write",
        "payroll:approve", "payroll:pay",  # maker-checker: manager drafts, owner approves, accountant pays
        "period:close",  # owner-only: closing/reopening the books
    },
    "accountant": frozenset({
        "catalog:read", "inventory:read", "sales:read", "returns:read",
        "orders:read", "orders:create",
        "customers:read", "customers:write", "suppliers:read", "suppliers:write",
        "purchases:read", "purchases:create", "purchase_returns:read", "purchase_returns:settle",
        "payments:customer", "payments:supplier",
        "expenses:read", "expenses:write", "ledger:read",
        "cash:read", "cash:close",
        "notifications:read", "notifications:send",
        "dashboard:read", "recommendations:read", "bsmart:read", "monitoring:read",
        "imports:write", "dataset:export", "model:train",
        "approvals:read",
        "tickets:read", "tickets:write",
        "leads:read", "leads:write",
        "feedback:read", "feedback:write",
        "commission:read",
        "advances:read",
        "payroll:read", "payroll:pay",
    }),
    "cashier": frozenset({
        "catalog:read", "inventory:read", "sales:read", "sales:create",
        "returns:read", "returns:create",
        "customers:read", "customers:write", "payments:customer",
        "notifications:send",
        "cash:read", "cash:close",
        "tickets:read", "tickets:write",
        "leads:read", "leads:write",
        "feedback:read", "feedback:write",
    }),
    "stock_keeper": frozenset({
        "catalog:read", "inventory:read", "inventory:adjust", "inventory:transfer",
        "suppliers:read", "purchases:read", "purchases:receive",
        "purchase_returns:read", "purchase_returns:create", "purchase_returns:dispatch",
    }),
    "viewer": frozenset({
        "catalog:read", "inventory:read", "sales:read", "returns:read",
        "orders:read",
        "customers:read", "suppliers:read", "purchases:read", "purchase_returns:read",
        "expenses:read", "ledger:read", "cash:read",
        "dashboard:read", "recommendations:read", "bsmart:read", "monitoring:read",
        "approvals:read",
        "notifications:read",
        "tickets:read",
        "leads:read",
        "feedback:read",
    }),
    "evaluator": frozenset({
        "dashboard:read", "recommendations:read", "bsmart:read", "monitoring:read",
    }),
    # Deliberately minimal: delivery_routes.py's start/complete/handover actions
    # are gated by "is this delivery assigned to me" (ownership), not a broad
    # permission, so a rider needs almost nothing from this matrix to do their
    # job -- just enough to see the Fulfilment page and their own assignments.
    "rider": frozenset({
        "orders:read", "notifications:read",
    }),
}

# Sanity check at import time: a typo in the matrix must fail loudly, not
# silently grant or deny a capability.
for _role, _perms in ROLE_PERMISSIONS.items():
    _unknown = _perms - ALL_PERMISSIONS
    assert not _unknown, f"{_role} references unknown permissions: {sorted(_unknown)}"
assert set(ROLE_PERMISSIONS) == set(ROLES)


def permissions_for(role: str) -> frozenset[str]:
    """Permissions for ``role``; an unknown role holds none (deny by default)."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: str) -> bool:
    return permission in permissions_for(role)


def require_permission(membership, permission: str) -> None:
    """Raise 403 unless the caller's role holds ``permission``."""
    if permission not in ALL_PERMISSIONS:
        # A route asking for a permission that does not exist is a programming
        # error; refuse rather than silently allowing.
        raise RuntimeError(f"Unknown permission requested: {permission}")
    if not has_permission(membership.role, permission):
        raise HTTPException(status_code=403, detail="Your role cannot perform this action")


def assigned_branch_ids(db, membership) -> set[str] | None:
    """Branches this membership is restricted to, or ``None`` for org-wide access.

    SRD 2.3 ABAC: ``branch_id in assigned_branches (unless org-wide permission)``.
    A membership with no ``MembershipBranch`` rows has never been scoped, so it
    keeps today's org-wide behaviour -- this is additive, not a breaking change.
    """
    from sqlalchemy import select

    from .domain_models import MembershipBranch

    rows = db.scalars(
        select(MembershipBranch.branch_id).where(MembershipBranch.membership_id == membership.id)
    ).all()
    return set(rows) if rows else None


def require_branch_access(db, membership, branch_id: str | None) -> None:
    """Raise 403 if this membership is branch-scoped and ``branch_id`` isn't in it.

    A ``None`` branch_id (an org-wide record/report) is always allowed through;
    callers that operate on one specific branch's data must pass it.
    """
    if branch_id is None:
        return
    allowed = assigned_branch_ids(db, membership)
    if allowed is not None and branch_id not in allowed:
        raise HTTPException(status_code=403, detail="Your account is not assigned to this branch")
