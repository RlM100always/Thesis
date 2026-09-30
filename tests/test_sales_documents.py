from datetime import datetime, timezone


def _create(client, headers, world, kind="quotation", number="QT-001"):
    return client.post("/api/app/sales-documents", headers=headers, json={
        "document_type": kind, "document_number": number,
        "branch_id": world["branch_a"], "issued_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"product_id": world["product_a"], "quantity": "2", "discount_amount": "10"}],
    })


def test_quote_converts_to_order_and_invoice_through_canonical_sale(client_for, world):
    owner, headers = client_for("owner")
    quote_response = _create(owner, headers, world)
    assert quote_response.status_code == 200, quote_response.text
    quote = quote_response.json()
    assert quote["total"] == 150.0

    order_response = owner.post(
        f"/api/app/sales-documents/{quote['id']}/convert-to-order", headers=headers,
        json={"order_number": "SO-001"},
    )
    assert order_response.status_code == 200, order_response.text
    order = order_response.json()
    assert order["status"] == "confirmed"

    invoice_response = owner.post(
        f"/api/app/sales-documents/{order['id']}/invoice", headers=headers,
        json={"invoice_number": "INV-FROM-SO", "sold_at": datetime.now(timezone.utc).isoformat(),
              "payments": [{"method": "cash", "amount": "150"}]},
    )
    assert invoice_response.status_code == 200, invoice_response.text
    assert invoice_response.json()["total"] == "150.00" or invoice_response.json()["total"] == 150.0
    documents = owner.get("/api/app/sales-documents", headers=headers).json()
    assert {row["status"] for row in documents} == {"converted", "invoiced"}


def test_order_delivery_state_machine_rejects_skips(client_for, world):
    manager, headers = client_for("manager")
    order = _create(manager, headers, world, "order", "SO-STATE").json()
    skipped = manager.post(f"/api/app/sales-documents/{order['id']}/status", headers=headers, json={"status": "delivered"})
    assert skipped.status_code == 409
    for status in ("ready", "dispatched", "delivered"):
        response = manager.post(f"/api/app/sales-documents/{order['id']}/status", headers=headers, json={"status": status})
        assert response.status_code == 200, response.text


def test_cashier_cannot_create_quote_and_tenants_are_isolated(client_for, world):
    cashier, headers = client_for("cashier")
    assert _create(cashier, headers, world).status_code == 403
    owner_b, headers_b = client_for("owner", "org_b")
    assert owner_b.get("/api/app/sales-documents", headers=headers_b).json() == []
