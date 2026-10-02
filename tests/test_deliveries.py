"""Deliveries and COD handover: rider self-service, and the cash-shift reconciliation link."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


def _staff_user_id(client_for, role):
    owner, headers = client_for("owner")
    staff = owner.get("/api/app/staff", headers=headers).json()
    return next(s["user_id"] for s in staff if s["role"] == role)


_order_counter = [0]


def _make_order(owner, headers, world):
    _order_counter[0] += 1
    n = _order_counter[0]
    product = owner.post("/api/app/products", headers=headers, json={
        "sku": f"DEL-{n}", "name": "Package", "selling_price": "300",
    }).json()
    owner.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "10", "reason": "stock in",
    })
    customer = owner.post("/api/app/customers", headers=headers, json={"code": f"DEL-CUST-{n}"}).json()
    order = owner.post("/api/app/sales", headers=headers, json={
        "branch_id": world["branch_a"], "invoice_number": f"DEL-INV-{n}", "customer_id": customer["id"],
        "sold_at": NOW.isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "300"}],
        "payments": [],  # COD: nothing collected at sale time
    }).json()
    return order


def test_full_delivery_and_handover_flow(client_for, world):
    owner, oheaders = client_for("owner")
    stock_keeper, skheaders = client_for("stock_keeper")  # stands in as "rider"
    cashier, cheaders = client_for("cashier")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")

    order = _make_order(owner, oheaders, world)
    delivery = owner.post("/api/app/deliveries", headers=oheaders, json={
        "sales_order_id": order["id"], "rider_user_id": rider_user_id, "cod_amount_expected": "300",
    })
    assert delivery.status_code == 200
    delivery = delivery.json()
    assert delivery["status"] == "assigned"

    started = stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/out-for-delivery", headers=skheaders)
    assert started.status_code == 200 and started.json()["status"] == "out_for_delivery"

    completed = stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/complete", headers=skheaders, json={
        "status": "delivered", "cod_collected": "300", "proof_note": "OTP confirmed",
    })
    assert completed.status_code == 200
    assert completed.json()["status"] == "delivered"
    assert Decimal(str(completed.json()["cod_amount_collected"])) == 300

    cashier.post("/api/app/shifts/open", headers=cheaders, json={"branch_id": world["branch_a"], "opening_cash": "0"})
    shift = cashier.get("/api/app/shifts/current", headers=cheaders, params={"branch_id": world["branch_a"]}).json()
    # "delivered" alone must not yet show up as cash anywhere.
    assert Decimal(str(shift["opening_cash"])) == 0

    handover = cashier.post(f"/api/app/deliveries/{delivery['id']}/handover", headers=cheaders, json={
        "shift_id": shift["id"], "handed_over_amount": "300",
    })
    assert handover.status_code == 200
    assert Decimal(str(handover.json()["shortage_amount"])) == 0

    # The cash movement actually landed on the shift.
    close = cashier.post(f"/api/app/shifts/{shift['id']}/close", headers=cheaders, json={"counted_cash": "300"})
    assert close.status_code == 200
    assert Decimal(str(close.json()["variance"])) == 0


def test_shortage_is_computed_not_assumed(client_for, world):
    owner, oheaders = client_for("owner")
    cashier, cheaders = client_for("cashier")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")
    stock_keeper, skheaders = client_for("stock_keeper")

    order = _make_order(owner, oheaders, world)
    delivery = owner.post("/api/app/deliveries", headers=oheaders, json={
        "sales_order_id": order["id"], "rider_user_id": rider_user_id, "cod_amount_expected": "300",
    }).json()
    stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/out-for-delivery", headers=skheaders)
    stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/complete", headers=skheaders,
                      json={"status": "delivered", "cod_collected": "300"})

    cashier.post("/api/app/shifts/open", headers=cheaders, json={"branch_id": world["branch_a"], "opening_cash": "0"})
    shift_id = cashier.get("/api/app/shifts/current", headers=cheaders, params={"branch_id": world["branch_a"]}).json()["id"]
    handover = cashier.post(f"/api/app/deliveries/{delivery['id']}/handover", headers=cheaders, json={
        "shift_id": shift_id, "handed_over_amount": "250",  # rider only hands over 250 of the 300 collected
    })
    assert Decimal(str(handover.json()["shortage_amount"])) == 50


def test_cod_cannot_be_handed_over_twice(client_for, world):
    owner, oheaders = client_for("owner")
    cashier, cheaders = client_for("cashier")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")
    stock_keeper, skheaders = client_for("stock_keeper")

    order = _make_order(owner, oheaders, world)
    delivery = owner.post("/api/app/deliveries", headers=oheaders, json={
        "sales_order_id": order["id"], "rider_user_id": rider_user_id, "cod_amount_expected": "300",
    }).json()
    stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/out-for-delivery", headers=skheaders)
    stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/complete", headers=skheaders,
                      json={"status": "delivered", "cod_collected": "300"})
    cashier.post("/api/app/shifts/open", headers=cheaders, json={"branch_id": world["branch_a"], "opening_cash": "0"})
    shift_id = cashier.get("/api/app/shifts/current", headers=cheaders, params={"branch_id": world["branch_a"]}).json()["id"]
    cashier.post(f"/api/app/deliveries/{delivery['id']}/handover", headers=cheaders,
                json={"shift_id": shift_id, "handed_over_amount": "300"})
    second = cashier.post(f"/api/app/deliveries/{delivery['id']}/handover", headers=cheaders,
                          json={"shift_id": shift_id, "handed_over_amount": "300"})
    assert second.status_code == 409


def test_failed_delivery_requires_a_reason(client_for, world):
    owner, oheaders = client_for("owner")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")
    stock_keeper, skheaders = client_for("stock_keeper")
    order = _make_order(owner, oheaders, world)
    delivery = owner.post("/api/app/deliveries", headers=oheaders, json={
        "sales_order_id": order["id"], "rider_user_id": rider_user_id,
    }).json()
    stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/out-for-delivery", headers=skheaders)
    failed = stock_keeper.post(f"/api/app/deliveries/{delivery['id']}/complete", headers=skheaders,
                               json={"status": "failed"})
    assert failed.status_code == 422


def test_an_unassigned_person_cannot_act_on_someone_elses_delivery(client_for, world):
    owner, oheaders = client_for("owner")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")
    cashier, cheaders = client_for("cashier")
    order = _make_order(owner, oheaders, world)
    delivery = owner.post("/api/app/deliveries", headers=oheaders, json={
        "sales_order_id": order["id"], "rider_user_id": rider_user_id,
    }).json()
    response = cashier.post(f"/api/app/deliveries/{delivery['id']}/out-for-delivery", headers=cheaders)
    assert response.status_code == 403


def test_cannot_assign_a_second_active_delivery_to_the_same_order(client_for, world):
    owner, oheaders = client_for("owner")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")
    order = _make_order(owner, oheaders, world)
    owner.post("/api/app/deliveries", headers=oheaders,
              json={"sales_order_id": order["id"], "rider_user_id": rider_user_id})
    dup = owner.post("/api/app/deliveries", headers=oheaders,
                     json={"sales_order_id": order["id"], "rider_user_id": rider_user_id})
    assert dup.status_code == 409


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_assign_deliveries(client_for, world, role, allowed):
    owner, oheaders = client_for("owner")
    rider_user_id = _staff_user_id(client_for, "stock_keeper")
    order = _make_order(owner, oheaders, world)
    client, headers = client_for(role)
    response = client.post("/api/app/deliveries", headers=headers,
                           json={"sales_order_id": order["id"], "rider_user_id": rider_user_id})
    assert (response.status_code == 200) == allowed
