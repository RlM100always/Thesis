"""The permission matrix: static guarantees and per-role enforcement on live routes."""

import re
from pathlib import Path

import pytest

from api.permissions import (
    ALL_PERMISSIONS, ROLE_PERMISSIONS, ROLES, has_permission, permissions_for,
)

# ── static guarantees ────────────────────────────────────────────────────────

# What each write permission allowed before the matrix existed (five legacy
# roles only). Refactoring role checks into permissions must not silently widen
# or narrow anyone's access.
LEGACY_WRITE_ACCESS = {
    "catalog:write": {"owner", "manager"},
    "inventory:adjust": {"owner", "manager"},
    "sales:create": {"owner", "manager", "cashier"},
    "branches:write": {"owner", "manager"},
    "staff:manage": {"owner"},
    "staff:read": {"owner", "manager"},
    "suppliers:write": {"owner", "manager", "accountant"},
    "purchases:create": {"owner", "manager", "accountant"},
    "purchases:receive": {"owner", "manager"},
    "payments:supplier": {"owner", "accountant"},
    "payments:customer": {"owner", "manager", "accountant", "cashier"},
    "returns:create": {"owner", "manager", "cashier"},
    "expenses:write": {"owner", "manager", "accountant"},
    "imports:write": {"owner", "manager", "accountant"},
    "model:train": {"owner", "manager", "accountant"},
}
LEGACY_ROLES = {"owner", "manager", "cashier", "accountant", "viewer"}


@pytest.mark.parametrize("permission,allowed", LEGACY_WRITE_ACCESS.items())
def test_matrix_preserves_pre_matrix_access(permission, allowed):
    granted = {role for role in LEGACY_ROLES if has_permission(role, permission)}
    assert granted == allowed


def test_owner_holds_every_permission():
    assert permissions_for("owner") == ALL_PERMISSIONS


def test_unknown_role_is_denied_everything():
    assert permissions_for("intern") == frozenset()


def test_read_only_roles_hold_no_write_permission():
    write_markers = (
        ":write", ":create", ":adjust", ":receive", ":decide", ":outcome",
        ":import", ":manage", "payments:", "imports:", "model:train",
    )
    for role in ("viewer", "evaluator"):
        writes = [p for p in permissions_for(role) if any(m in p for m in write_markers)]
        assert writes == [], f"{role} must be read-only, holds {writes}"


def test_cashier_cannot_see_money_behind_the_till():
    for permission in ("dashboard:read", "expenses:read", "ledger:read",
                       "recommendations:read", "bsmart:decide", "dataset:export"):
        assert not has_permission("cashier", permission)


def test_only_owner_and_manager_can_decide_recommendations():
    deciders = {role for role in ROLES if has_permission(role, "bsmart:decide")}
    assert deciders == {"owner", "manager"}


def test_every_route_requests_a_known_permission():
    """A typo in a route's permission string would raise at request time; catch it here."""
    pattern = re.compile(r'require_permission\(\s*membership,\s*"([^"]+)"')
    requested = set()
    for path in Path("api").glob("*.py"):
        requested |= set(pattern.findall(path.read_text(encoding="utf-8")))
    assert requested, "no route calls require_permission"
    assert requested <= ALL_PERMISSIONS, f"unknown: {sorted(requested - ALL_PERMISSIONS)}"


def test_every_permission_is_enforced_somewhere_or_reserved():
    """Permissions defined but never requested by any route are dead weight."""
    pattern = re.compile(r'require_permission\(\s*membership,\s*"([^"]+)"')
    requested = set()
    for path in Path("api").glob("*.py"):
        requested |= set(pattern.findall(path.read_text(encoding="utf-8")))
    assert ALL_PERMISSIONS <= requested, sorted(ALL_PERMISSIONS - requested)


# ── enforcement on real routes ───────────────────────────────────────────────

ALL_ROLES = list(ROLES)

# (method, path, json, permission). Allowed = role holds the permission; the
# handler may still answer 404/422 for missing data, but never 403.
ENDPOINTS = [
    ("GET", "/api/app/dashboard", None, "dashboard:read"),
    ("GET", "/api/app/recommendations", None, "recommendations:read"),
    ("GET", "/api/app/bsmart/recommendations", None, "bsmart:read"),
    ("GET", "/api/app/bsmart/monitoring", None, "monitoring:read"),
    ("GET", "/api/app/bsmart/recommendations/missing/explain", None, "bsmart:read"),
    ("POST", "/api/app/bsmart/recommendations/missing/decision", {"decision": "accept"}, "bsmart:decide"),
    ("POST", "/api/app/bsmart/recommendations/missing/outcome", {}, "bsmart:outcome"),
    ("POST", "/api/app/bsmart/recommendations/missing/measure", {}, "bsmart:outcome"),
    ("POST", "/api/app/bsmart/run", None, "bsmart:import"),
    ("GET", "/api/app/products", None, "catalog:read"),
    ("GET", "/api/app/sales", None, "sales:read"),
    ("GET", "/api/app/returns", None, "returns:read"),
    ("GET", "/api/app/customers", None, "customers:read"),
    ("GET", "/api/app/suppliers", None, "suppliers:read"),
    ("GET", "/api/app/purchases", None, "purchases:read"),
    ("GET", "/api/app/purchase-returns", None, "purchase_returns:read"),
    ("GET", "/api/app/expenses", None, "expenses:read"),
    ("GET", "/api/app/ledger/payable", None, "ledger:read"),
    ("GET", "/api/app/staff", None, "staff:read"),
    ("GET", "/api/app/audit", None, "audit:read"),
    ("GET", "/api/app/datasets/sales.csv", None, "dataset:export"),
    ("POST", "/api/app/staff", {"email": "new@a.example", "display_name": "New Person", "role": "cashier"}, "staff:manage"),
]


@pytest.mark.parametrize("role", ALL_ROLES)
@pytest.mark.parametrize("method,path,body,permission", ENDPOINTS)
def test_route_enforces_permission_matrix(client_for, role, method, path, body, permission):
    client, headers = client_for(role)
    response = client.request(method, path, headers=headers, json=body)
    if has_permission(role, permission):
        assert response.status_code != 403, (role, path, response.text)
    else:
        assert response.status_code == 403, (role, path, response.status_code, response.text)


@pytest.mark.parametrize("role", ["manager", "accountant", "cashier", "stock_keeper", "viewer", "evaluator"])
def test_import_run_is_owner_manager_only(client_for, role):
    client, headers = client_for(role)
    response = client.post("/api/app/bsmart/import-run", headers=headers)
    expected_forbidden = not has_permission(role, "bsmart:import")
    assert (response.status_code == 403) == expected_forbidden


# ── tenant isolation ─────────────────────────────────────────────────────────

def test_owner_of_one_shop_cannot_use_another_shops_id(client_for, world):
    client, _ = client_for("owner", org="org_b")  # owner of B ...
    response = client.get("/api/app/products", headers={"X-Organization-ID": world["org_a"]})
    assert response.status_code == 404  # ... asking for A: indistinguishable from "no such shop"


def test_missing_organization_header_is_rejected(client_for):
    client, _ = client_for("owner")
    assert client.get("/api/app/products").status_code == 400


def test_tenant_only_sees_its_own_rows(client_for, world):
    client_a, headers_a = client_for("owner", org="org_a")
    client_b, headers_b = client_for("owner", org="org_b")
    assert [p["sku"] for p in client_a.get("/api/app/products", headers=headers_a).json()] == ["RICE-1"]
    assert client_b.get("/api/app/products", headers=headers_b).json() == []


def test_permissions_endpoint_reports_the_callers_role(client_for):
    client, headers = client_for("cashier")
    body = client.get("/api/app/auth/permissions", headers=headers).json()
    assert body["role"] == "cashier"
    assert "sales:create" in body["permissions"]
    assert "dashboard:read" not in body["permissions"]
