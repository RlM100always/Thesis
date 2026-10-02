"""Public online-storefront checkout, on top of the existing SalesDocument
order workflow (see api/order_routes.py). An anonymous buyer places an order
through ``public_router`` with no membership/organization header at all; the
owner then sees it land in the usual sales-documents list and confirms it
through the authenticated router, same as any staff-created order.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from api.domain_models import Branch


def _checkout(client, org_id, product_id, qty="1", **overrides):
    payload = {
        "shipping_name": "Karim Uddin",
        "shipping_phone": "01700000000",
        "shipping_address": "House 12, Road 4, Dhanmondi, Dhaka",
        "items": [{"product_id": product_id, "quantity": qty}],
    }
    payload.update(overrides)
    return client.post(f"/api/public/orders/{org_id}", json=payload)


def test_anonymous_checkout_creates_a_placed_order(world, client_for):
    client, _ = client_for("owner")
    response = _checkout(client, world["org_a"], world["product_a"], qty="2")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "placed"
    assert body["order_number"].startswith("WEB-")
    assert body["access_token"]
    assert Decimal(str(body["total"])) == Decimal("160.00")  # 2 * 80, server-priced, not client-priced
    assert Decimal(str(body["items"][0]["quantity"])) == Decimal("2")


def test_checkout_ignores_a_client_supplied_price(world, client_for):
    """``PublicOrderItem`` has no unit_price field at all — a buyer cannot name
    their own price. Pins that an extra field in the body is simply ignored
    and the stored line is priced off Product.selling_price."""
    client, _ = client_for("owner")
    response = client.post(
        f"/api/public/orders/{world['org_a']}",
        json={
            "shipping_name": "Karim", "shipping_phone": "0170", "shipping_address": "Dhaka",
            "items": [{"product_id": world["product_a"], "quantity": "1", "unit_price": "1"}],
        },
    )
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total"])) == Decimal("80.00")


def test_checkout_rejects_unknown_organization(world, client_for):
    client, _ = client_for("owner")
    response = _checkout(client, "does-not-exist", world["product_a"])
    assert response.status_code == 404


def test_checkout_rejects_unknown_product(world, client_for):
    client, _ = client_for("owner")
    response = _checkout(client, world["org_a"], "nope")
    assert response.status_code == 404


def test_checkout_rejects_duplicate_product_lines(world, client_for):
    client, _ = client_for("owner")
    response = client.post(
        f"/api/public/orders/{world['org_a']}",
        json={
            "shipping_name": "X", "shipping_phone": "0170", "shipping_address": "X",
            "items": [
                {"product_id": world["product_a"], "quantity": "1"},
                {"product_id": world["product_a"], "quantity": "2"},
            ],
        },
    )
    assert response.status_code == 422


def test_checkout_fails_cleanly_with_no_active_branch(engine, world, client_for):
    with Session(engine) as db:
        for branch in db.query(Branch).filter(Branch.organization_id == world["org_a"]):
            branch.active = False
        db.commit()
    client, _ = client_for("owner")
    response = _checkout(client, world["org_a"], world["product_a"])
    assert response.status_code == 409


def test_customer_can_look_up_their_own_order_status_by_token(world, client_for):
    client, _ = client_for("owner")
    placed = _checkout(client, world["org_a"], world["product_a"]).json()
    status = client.get(f"/api/public/orders/{world['org_a']}/status/{placed['access_token']}")
    assert status.status_code == 200
    assert status.json()["order_number"] == placed["order_number"]
    assert status.json()["status"] == "placed"


def test_wrong_token_or_wrong_org_returns_404_not_someone_elses_order(world, client_for):
    client, _ = client_for("owner")
    placed = _checkout(client, world["org_a"], world["product_a"]).json()
    assert client.get(f"/api/public/orders/{world['org_a']}/status/wrong-token").status_code == 404
    assert client.get(f"/api/public/orders/{world['org_b']}/status/{placed['access_token']}").status_code == 404


def test_owner_sees_placed_online_order_and_can_confirm_it(world, client_for):
    owner, headers = client_for("owner")
    placed = _checkout(owner, world["org_a"], world["product_a"]).json()

    listing = owner.get("/api/app/sales-documents", params={"channel": "online"}, headers=headers)
    assert listing.status_code == 200
    [doc] = [d for d in listing.json() if d["document_number"] == placed["order_number"]]
    assert doc["status"] == "placed"
    assert doc["is_online_order"] is True
    assert doc["shipping_phone"] == "01700000000"

    confirm = owner.post(f"/api/app/sales-documents/{doc['id']}/status", json={"status": "confirmed"}, headers=headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    # It now follows the ordinary order lifecycle — same states a
    # staff-created order already uses to get a delivery out the door.
    assert owner.post(f"/api/app/sales-documents/{doc['id']}/status", json={"status": "ready"}, headers=headers).status_code == 200
    assert owner.post(f"/api/app/sales-documents/{doc['id']}/status", json={"status": "dispatched"}, headers=headers).status_code == 200
    assert owner.post(f"/api/app/sales-documents/{doc['id']}/status", json={"status": "delivered"}, headers=headers).status_code == 200


def test_a_cashier_cannot_confirm_an_online_order_without_fulfill_permission(world, client_for):
    owner, owner_headers = client_for("owner")
    cashier, cashier_headers = client_for("cashier")
    placed = _checkout(owner, world["org_a"], world["product_a"]).json()
    listing = owner.get("/api/app/sales-documents", params={"channel": "online"}, headers=owner_headers).json()
    [doc] = [d for d in listing if d["document_number"] == placed["order_number"]]
    response = cashier.post(
        f"/api/app/sales-documents/{doc['id']}/status", json={"status": "confirmed"}, headers=cashier_headers,
    )
    assert response.status_code == 403


def test_online_order_can_be_invoiced_after_confirmation(world, client_for):
    """Confirming an online order is only half the story — the shop still
    needs it to turn into a real invoice/payment, exactly like a
    staff-created order (``SalesDocumentInvoice``). An online order has no
    linked Customer record, so (same rule a staff-created order already
    follows) it must be paid in full at invoicing time rather than left as a
    receivable with nobody to bill — realistic for cash-on-delivery, which is
    the only settlement this codebase can honestly claim without a payment
    gateway."""
    owner, headers = client_for("owner")
    placed = _checkout(owner, world["org_a"], world["product_a"]).json()
    listing = owner.get("/api/app/sales-documents", params={"channel": "online"}, headers=headers).json()
    [doc] = [d for d in listing if d["document_number"] == placed["order_number"]]
    owner.post(f"/api/app/sales-documents/{doc['id']}/status", json={"status": "confirmed"}, headers=headers)

    invoiced = owner.post(
        f"/api/app/sales-documents/{doc['id']}/invoice",
        json={
            "invoice_number": "INV-WEB-1", "sold_at": "2026-10-01T10:00:00Z",
            "payments": [{"method": "cod", "amount": "80.00"}],
        },
        headers=headers,
    )
    assert invoiced.status_code == 200, invoiced.text
    assert Decimal(str(invoiced.json()["total"])) == Decimal("80.00")

    # And invoicing without full payment correctly fails, same as it would
    # for any walk-in order with no customer on file.
    placed2 = _checkout(owner, world["org_a"], world["product_a"]).json()
    listing2 = owner.get("/api/app/sales-documents", params={"channel": "online"}, headers=headers).json()
    [doc2] = [d for d in listing2 if d["document_number"] == placed2["order_number"]]
    owner.post(f"/api/app/sales-documents/{doc2['id']}/status", json={"status": "confirmed"}, headers=headers)
    unpaid = owner.post(
        f"/api/app/sales-documents/{doc2['id']}/invoice",
        json={"invoice_number": "INV-WEB-2", "sold_at": "2026-10-01T10:00:00Z", "payments": []},
        headers=headers,
    )
    assert unpaid.status_code == 422
