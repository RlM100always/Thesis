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
    "owner", "manager", "cashier", "accountant", "stock_keeper", "viewer", "evaluator",
)

ALL_PERMISSIONS: frozenset[str] = frozenset({
    "catalog:read", "catalog:write",
    "inventory:read", "inventory:adjust",
    "sales:read", "sales:create", "sales:void",
    "returns:read", "returns:create",
    "customers:read", "customers:write",
    "suppliers:read", "suppliers:write",
    "purchases:read", "purchases:create", "purchases:receive",
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
    "approvals:read", "approvals:decide",
})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": ALL_PERMISSIONS,
    "manager": ALL_PERMISSIONS - {"staff:manage", "payments:supplier", "settings:write"},  # keeps approvals:decide
    "accountant": frozenset({
        "catalog:read", "inventory:read", "sales:read", "returns:read",
        "customers:read", "customers:write", "suppliers:read", "suppliers:write",
        "purchases:read", "purchases:create",
        "payments:customer", "payments:supplier",
        "expenses:read", "expenses:write", "ledger:read",
        "cash:read", "cash:close",
        "dashboard:read", "recommendations:read", "bsmart:read", "monitoring:read",
        "imports:write", "dataset:export", "model:train",
        "approvals:read",
    }),
    "cashier": frozenset({
        "catalog:read", "inventory:read", "sales:read", "sales:create",
        "returns:read", "returns:create",
        "customers:read", "customers:write", "payments:customer",
        "cash:read", "cash:close",
    }),
    "stock_keeper": frozenset({
        "catalog:read", "inventory:read", "inventory:adjust", "inventory:transfer",
        "suppliers:read", "purchases:read", "purchases:receive",
    }),
    "viewer": frozenset({
        "catalog:read", "inventory:read", "sales:read", "returns:read",
        "customers:read", "suppliers:read", "purchases:read",
        "expenses:read", "ledger:read", "cash:read",
        "dashboard:read", "recommendations:read", "bsmart:read", "monitoring:read",
        "approvals:read",
    }),
    "evaluator": frozenset({
        "dashboard:read", "recommendations:read", "bsmart:read", "monitoring:read",
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
