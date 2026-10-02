"""Fiscal period close: a closed month refuses new postings everywhere, reopen restores them."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body):
        return self.c.post(f"/api/app{path}", headers=self.h, json=body)

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def product(self, sku, stock=100, price="100", cost="60"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost}).json()
        self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def sale(self, product, qty, sold_at):
        self.n += 1
        unit = Decimal(product["selling_price"])
        paid = unit * qty
        return self.c.post("/api/app/sales", headers=self.h, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"PC-{self.n}",
            "sold_at": sold_at.isoformat(), "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(paid)}],
        })


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


SEPTEMBER = datetime(2026, 9, 15, tzinfo=timezone.utc)
OCTOBER = datetime(2026, 10, 15, tzinfo=timezone.utc)


def test_closing_a_month_blocks_a_sale_backdated_into_it(shop):
    close = shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    assert close.status_code == 200

    product = shop.product("PC-1")
    blocked = shop.sale(product, 1, SEPTEMBER)
    assert blocked.status_code == 409
    assert "closed" in blocked.text.lower()

    # A sale in the still-open month works normally.
    allowed = shop.sale(product, 1, OCTOBER)
    assert allowed.status_code == 200


def test_closing_a_month_blocks_an_expense(shop):
    shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    blocked = shop.post("/expenses", {
        "category": "ভাড়া", "amount": "500", "payment_method": "cash", "incurred_at": SEPTEMBER.isoformat(),
    })
    assert blocked.status_code == 409


def test_closing_a_month_blocks_a_purchase_receipt(shop):
    shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    product = shop.product("PC-2", stock=0)
    supplier = shop.post("/suppliers", {"code": "PC-SUP", "name": "Sup"}).json()
    order = shop.post("/purchases", {
        "branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PC-PO-1",
        "ordered_at": OCTOBER.isoformat(),
        "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": "10"}],
    }).json()
    line = shop.get("/purchases")[0]["items"][0]["id"]
    blocked = shop.post(f"/purchases/{order['id']}/receive", {
        "received_at": SEPTEMBER.isoformat(),
        "items": [{"purchase_order_item_id": line, "quantity": "10"}],
    })
    assert blocked.status_code == 409


def test_already_posted_entries_are_unaffected_by_a_later_close(shop):
    product = shop.product("PC-3")
    before_close = shop.sale(product, 1, SEPTEMBER)
    assert before_close.status_code == 200
    close = shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    assert close.status_code == 200
    tb = shop.get("/accounting/trial-balance")
    assert any(Decimal(str(a["balance"])) != 0 for a in tb["accounts"])  # the earlier sale is still in the books


def test_cannot_close_the_same_month_twice(shop):
    shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    again = shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    assert again.status_code == 409


def test_reopen_restores_posting_and_is_audited(shop):
    closed = shop.post("/accounting/periods/close", {"period_month": "2026-09-01"}).json()
    periods = shop.get("/accounting/periods")
    period_id = next(p["id"] for p in periods if p["status"] == "closed")

    reopened = shop.post(f"/accounting/periods/{period_id}/reopen", {"reason": "found a missed adjustment"})
    assert reopened.status_code == 200 and reopened.json()["status"] == "reopened"

    product = shop.product("PC-4")
    now_allowed = shop.sale(product, 1, SEPTEMBER)
    assert now_allowed.status_code == 200

    trail = shop.get("/audit", actions="accounting.period_reopened")
    assert len(trail["items"]) == 1
    assert trail["items"][0]["details"]["reason"] == "found a missed adjustment"


def test_reopen_requires_a_reason(shop):
    shop.post("/accounting/periods/close", {"period_month": "2026-09-01"})
    periods = shop.get("/accounting/periods")
    period_id = periods[0]["id"]
    response = shop.post(f"/accounting/periods/{period_id}/reopen", {"reason": ""})
    assert response.status_code == 422


def test_cannot_reopen_a_period_that_was_never_closed(shop):
    product = shop.product("PC-5")
    shop.sale(product, 1, OCTOBER)  # just to have a real id scheme; period never closed
    response = shop.post("/accounting/periods/not-a-real-id/reopen", {"reason": "no such period"})
    assert response.status_code == 404


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", False), ("accountant", False), ("cashier", False)])
def test_who_may_close_a_period(client_for, role, allowed):
    client, headers = client_for(role)
    response = client.post("/api/app/accounting/periods/close", headers=headers, json={"period_month": "2026-09-01"})
    assert (response.status_code == 200) == allowed
