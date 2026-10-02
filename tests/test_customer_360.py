"""Customer 360: one read model pulling together sales, dues, loyalty, tickets and feedback."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


@pytest.fixture()
def owner(client_for):
    return client_for("owner")


def _customer(client, headers, code="CUST-360"):
    return client.post("/api/app/customers", headers=headers, json={"code": code, "display_name": "Full View Co"}).json()


def test_360_view_of_a_fresh_customer_is_empty_but_not_missing(owner):
    client, headers = owner
    customer = _customer(client, headers)
    view = client.get(f"/api/app/customers/{customer['id']}/360", headers=headers)
    assert view.status_code == 200
    body = view.json()
    assert body["customer"]["id"] == customer["id"]
    assert Decimal(body["lifetime_sales_total"]) == 0
    assert body["recent_orders"] == [] and body["open_tickets"] == [] and body["feedback"] == []
    assert Decimal(body["loyalty_balance"]) == 0
    assert body["originated_from_lead_id"] is None


def test_360_aggregates_sale_due_ticket_and_feedback(owner, world):
    client, headers = owner
    customer = _customer(client, headers, code="CUST-AGG")
    product = client.post("/api/app/products", headers=headers, json={
        "sku": "P-360", "name": "Widget", "selling_price": "100",
    }).json()
    client.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "10", "reason": "stock in",
    })
    client.post("/api/app/sales", headers=headers, json={
        "branch_id": world["branch_a"], "invoice_number": "INV-360-1", "customer_id": customer["id"],
        "sold_at": NOW.isoformat(),
        "items": [{"product_id": product["id"], "quantity": "2", "unit_price": "100"}],
        "payments": [],
    })
    ticket = client.post("/api/app/tickets", headers=headers,
                         json={"subject": "Delivery delay", "customer_id": customer["id"]}).json()
    client.post("/api/app/feedback", headers=headers, json={"score": 8, "customer_id": customer["id"]})

    view = client.get(f"/api/app/customers/{customer['id']}/360", headers=headers).json()
    assert Decimal(view["lifetime_sales_total"]) == 200
    assert len(view["recent_orders"]) == 1
    assert Decimal(view["customer"]["balance"]) == 200  # fully on due
    assert [t["id"] for t in view["open_tickets"]] == [ticket["id"]]
    assert len(view["feedback"]) == 1 and view["feedback"][0]["score"] == 8


def test_360_shows_originating_lead_after_conversion(owner):
    client, headers = owner
    lead = client.post("/api/app/leads", headers=headers, json={"name": "Converted Shop"}).json()
    customer = client.post(f"/api/app/leads/{lead['id']}/convert", headers=headers).json()
    view = client.get(f"/api/app/customers/{customer['id']}/360", headers=headers).json()
    assert view["originated_from_lead_id"] == lead["id"]


def test_resolved_tickets_do_not_appear_in_open_tickets(owner):
    client, headers = owner
    customer = _customer(client, headers, code="CUST-RESOLVED")
    ticket = client.post("/api/app/tickets", headers=headers,
                         json={"subject": "Will be resolved", "customer_id": customer["id"]}).json()
    client.patch(f"/api/app/tickets/{ticket['id']}", headers=headers, json={"status": "resolved"})
    view = client.get(f"/api/app/customers/{customer['id']}/360", headers=headers).json()
    assert view["open_tickets"] == []


def test_unknown_customer_is_404(owner):
    client, headers = owner
    assert client.get("/api/app/customers/not-real/360", headers=headers).status_code == 404


def test_cannot_view_another_organizations_customer(client_for):
    owner_a, headers_a = client_for("owner", org="org_a")
    owner_b, headers_b = client_for("owner", org="org_b")
    customer = _customer(owner_a, headers_a)
    assert owner_b.get(f"/api/app/customers/{customer['id']}/360", headers=headers_b).status_code == 404
