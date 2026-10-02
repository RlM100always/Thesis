"""Sales targets: progress computed live from the sales ledger, never stored."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)
MONTH_START, MONTH_END = "2026-10-01", "2026-10-31"


def _cashier_user_id(client_for):
    owner, headers = client_for("owner")
    staff = owner.get("/api/app/staff", headers=headers).json()
    return next(s["user_id"] for s in staff if s["role"] == "cashier")


def test_create_target_and_see_zero_progress(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    created = owner.post("/api/app/targets", headers=headers, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END,
        "target_amount": "10000",
    })
    assert created.status_code == 200
    body = created.json()
    assert body["achieved_amount"] == 0 and body["progress_percent"] == 0.0


def test_progress_reflects_actual_sales_by_that_person(client_for, world):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    owner.post("/api/app/targets", headers=oheaders, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END,
        "target_amount": "1000",
    })
    product = owner.post("/api/app/products", headers=oheaders, json={
        "sku": "TGT-1", "name": "Widget", "selling_price": "500",
    }).json()
    owner.post("/api/app/inventory/adjust", headers=oheaders, json={
        "branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "10", "reason": "stock in",
    })
    cashier.post("/api/app/sales", headers=cheaders, json={
        "branch_id": world["branch_a"], "invoice_number": "TGT-SALE-1",
        "sold_at": datetime(2026, 10, 15, tzinfo=timezone.utc).isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "500"}],
        "payments": [{"method": "cash", "amount": "500"}],
    })
    mine = cashier.get("/api/app/targets/me", headers=cheaders).json()
    assert Decimal(str(mine[0]["achieved_amount"])) == 500
    assert mine[0]["progress_percent"] == 50.0


def test_sale_outside_the_period_does_not_count(client_for, world):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    owner.post("/api/app/targets", headers=oheaders, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END,
        "target_amount": "1000",
    })
    product = owner.post("/api/app/products", headers=oheaders, json={
        "sku": "TGT-2", "name": "Widget", "selling_price": "500",
    }).json()
    owner.post("/api/app/inventory/adjust", headers=oheaders, json={
        "branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "10", "reason": "stock in",
    })
    cashier.post("/api/app/sales", headers=cheaders, json={
        "branch_id": world["branch_a"], "invoice_number": "TGT-SALE-OUT",
        "sold_at": datetime(2026, 11, 2, tzinfo=timezone.utc).isoformat(),  # next month
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "500"}],
        "payments": [{"method": "cash", "amount": "500"}],
    })
    mine = cashier.get("/api/app/targets/me", headers=cheaders).json()
    assert mine[0]["achieved_amount"] == 0


def test_duplicate_target_for_same_person_and_period_is_rejected(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    owner.post("/api/app/targets", headers=headers, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END, "target_amount": "1000",
    })
    dup = owner.post("/api/app/targets", headers=headers, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END, "target_amount": "2000",
    })
    assert dup.status_code == 409


def test_update_target_amount(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    target = owner.post("/api/app/targets", headers=headers, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END, "target_amount": "1000",
    }).json()
    updated = owner.patch(f"/api/app/targets/{target['id']}", headers=headers, json={"target_amount": "2000"})
    assert updated.status_code == 200 and Decimal(str(updated.json()["target_amount"])) == 2000


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_create_targets(client_for, role, allowed):
    client, headers = client_for(role)
    cashier_user_id = _cashier_user_id(client_for)
    response = client.post("/api/app/targets", headers=headers, json={
        "user_id": cashier_user_id, "period_start": MONTH_START, "period_end": MONTH_END, "target_amount": "1000",
    })
    assert (response.status_code == 200) == allowed


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("cashier", False)])
def test_who_may_view_team_targets(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/targets", headers=headers).status_code == 200) == allowed
