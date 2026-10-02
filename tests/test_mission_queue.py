"""Today Mission Queue: live-pulled, permission-aware, priority-sorted task list."""

from datetime import date, datetime, timedelta, timezone

import pytest

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w = client, headers, world

    def post(self, path, body):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_empty_queue_for_a_quiet_business(shop):
    body = shop.get("/mission-queue")
    assert body["items"] == []


def test_urgent_ticket_appears_and_outranks_a_normal_one(shop):
    shop.post("/tickets", {"subject": "Routine question"})
    shop.post("/tickets", {"subject": "Everything is on fire", "priority": "urgent"})
    body = shop.get("/mission-queue")
    types = [i["type"] for i in body["items"]]
    assert "ticket" in types
    ticket_items = [i for i in body["items"] if i["type"] == "ticket"]
    assert len(ticket_items) == 1  # the normal-priority one is excluded
    assert "fire" in ticket_items[0]["title"]


def test_pending_leave_request_appears(shop):
    shop.post("/leave", {"start_date": "2026-11-01", "end_date": "2026-11-02"})
    body = shop.get("/mission-queue")
    assert any(i["type"] == "leave" for i in body["items"])


def test_low_stock_product_appears(shop):
    shop.post("/products", {"sku": "MQ-1", "name": "Low Item", "selling_price": "10", "reorder_level": "50"})
    body = shop.get("/mission-queue")
    assert any(i["type"] == "low_stock" and "Low Item" in i["title"] for i in body["items"])


def test_overdue_receivable_appears_but_recent_due_does_not(shop):
    product = shop.post("/products", {"sku": "MQ-2", "name": "P", "selling_price": "100"})
    shop.post("/inventory/adjust", {"branch_id": shop.w["branch_a"], "product_id": product["id"], "quantity_delta": "10", "reason": "open"})
    old_customer = shop.post("/customers", {"code": "MQ-OLD"})
    recent_customer = shop.post("/customers", {"code": "MQ-NEW"})
    shop.c.post("/api/app/sales", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "invoice_number": "MQ-OLD-SALE", "customer_id": old_customer["id"],
        "sold_at": (NOW - timedelta(days=45)).isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "100"}], "payments": [],
    })
    shop.c.post("/api/app/sales", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "invoice_number": "MQ-NEW-SALE", "customer_id": recent_customer["id"],
        "sold_at": (NOW - timedelta(days=2)).isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "100"}], "payments": [],
    })
    body = shop.get("/mission-queue")
    overdue_titles = " ".join(i["title"] for i in body["items"] if i["type"] == "overdue_receivable")
    assert "MQ-OLD" in overdue_titles
    assert "MQ-NEW" not in overdue_titles


def test_pending_expense_approval_appears(client_for):
    accountant, aheaders = client_for("accountant")  # ranks below the expense approver_role (owner)
    owner, oheaders = client_for("owner")
    accountant.post("/api/app/expenses", headers=aheaders, json={
        "category": "ভাড়া", "amount": "6000", "payment_method": "cash", "incurred_at": NOW.isoformat(),
    })
    body = owner.get("/api/app/mission-queue", headers=oheaders).json()
    assert any(i["type"] == "approval" for i in body["items"])


def test_cashier_does_not_see_approvals_or_receivables(client_for):
    cashier, headers = client_for("cashier")
    body = cashier.get("/api/app/mission-queue", headers=headers).json()
    types = {i["type"] for i in body["items"]}
    assert "approval" not in types and "overdue_receivable" not in types


def test_limit_caps_the_returned_items(shop):
    for i in range(5):
        shop.post("/tickets", {"subject": f"Urgent issue {i}", "priority": "urgent"})
    body = shop.get("/mission-queue", limit=2)
    assert len(body["items"]) == 2
    assert body["total_before_limit"] >= 5
