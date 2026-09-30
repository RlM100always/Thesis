from datetime import datetime, timezone
from decimal import Decimal


def _payload(world, operation_id="device-a:0001"):
    return {
        "client_operation_id": operation_id,
        "branch_id": world["branch_a"], "invoice_number": "OFFLINE-0001",
        "sold_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"product_id": world["product_a"], "quantity": "2"}],
        "payments": [{"method": "cash", "amount": "160"}],
    }


def test_exact_offline_retry_returns_original_sale_without_double_stock_deduction(client_for, world):
    cashier, headers = client_for("cashier")
    payload = _payload(world)
    first = cashier.post("/api/app/sales", headers=headers, json=payload)
    second = cashier.post("/api/app/sales", headers=headers, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    inventory = cashier.get("/api/app/inventory", headers=headers, params={"branch_id": world["branch_a"]}).json()
    assert Decimal(next(row for row in inventory if row["product_id"] == world["product_a"])["quantity"]) == Decimal("8")


def test_reused_operation_id_with_changed_payload_is_a_visible_conflict(client_for, world):
    cashier, headers = client_for("cashier")
    payload = _payload(world)
    assert cashier.post("/api/app/sales", headers=headers, json=payload).status_code == 200
    payload["items"][0]["quantity"] = "3"
    response = cashier.post("/api/app/sales", headers=headers, json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "sync_conflict"
