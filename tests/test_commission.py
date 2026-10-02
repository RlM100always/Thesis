"""Commission: off by default, earns on a sale once enabled, and clawbacks on void/return."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body, status=200):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def patch(self, path, body, status=200):
        r = self.c.patch(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def product(self, sku, stock=100, price="100", cost="60"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost})
        self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def sale(self, product, qty, status=200):
        self.n += 1
        unit = Decimal(product["selling_price"])
        paid = unit * qty
        r = self.c.post("/api/app/sales", headers=self.h, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"COM-{self.n}",
            "sold_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(paid)}],
        })
        assert r.status_code == status, r.text
        return r.json()


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_commission_is_off_by_default(shop):
    rule = shop.get("/commission/rule")
    assert rule["active"] is False

    product = shop.product("COM-1")
    shop.sale(product, 2)
    mine = shop.get("/commission/me")
    assert mine["balance"] == "0" or Decimal(mine["balance"]) == 0
    assert mine["entries"] == []


def test_enabling_commission_earns_on_the_next_sale(shop):
    shop.patch("/commission/rule", {"active": True, "rate_percent": "5"})
    product = shop.product("COM-2", price="100")
    shop.sale(product, 2)  # net revenue 200, 5% = 10
    mine = shop.get("/commission/me")
    assert Decimal(mine["balance"]) == Decimal("10.00")
    assert mine["entries"][0]["reason"] == "earned"


def test_voiding_a_commissioned_sale_claws_it_back(shop):
    shop.patch("/commission/rule", {"active": True, "rate_percent": "5"})
    product = shop.product("COM-3", price="100")
    sale = shop.sale(product, 2)  # earns 10
    assert Decimal(shop.get("/commission/me")["balance"]) == Decimal("10.00")

    shop.post(f"/sales/{sale['id']}/void", {"reason": "customer changed mind"})
    after = shop.get("/commission/me")
    assert Decimal(after["balance"]) == Decimal("0.00")
    reasons = [e["reason"] for e in after["entries"]]
    assert reasons.count("earned") == 1 and reasons.count("clawback") == 1


def test_partial_return_claws_back_proportionally(shop):
    shop.patch("/commission/rule", {"active": True, "rate_percent": "10"})
    product = shop.product("COM-4", price="100")
    sale = shop.sale(product, 4)  # net 400, earns 40
    line_id = shop.get("/sales")[0]["items"][0]["id"]
    shop.post(f"/sales/{sale['id']}/returns", {
        "return_number": "RET-COM-1", "reason": "one defective", "returned_at": NOW.isoformat(), "refund_method": "cash",
        "items": [{"sales_order_item_id": line_id, "quantity": "1", "restock": True}],
    })
    # returned 1 of 4 units = 100 net returned, 10% = 10 clawback
    after = shop.get("/commission/me")
    assert Decimal(after["balance"]) == Decimal("30.00")


def test_clawback_never_exceeds_what_was_earned(shop):
    """Guards against a rate increase after the sale over-clawing on return."""
    shop.patch("/commission/rule", {"active": True, "rate_percent": "5"})
    product = shop.product("COM-5", price="100")
    sale = shop.sale(product, 1)  # earns 5
    shop.patch("/commission/rule", {"rate_percent": "50"})  # rate goes way up
    line_id = next(i["id"] for o in shop.get("/sales") if o["id"] == sale["id"] for i in o["items"])
    shop.post(f"/sales/{sale['id']}/returns", {
        "return_number": "RET-COM-2", "reason": "defective", "returned_at": NOW.isoformat(), "refund_method": "cash",
        "items": [{"sales_order_item_id": line_id, "quantity": "1", "restock": True}],
    })
    after = shop.get("/commission/me")
    assert Decimal(after["balance"]) == Decimal("0.00")  # clawed back exactly the 5 earned, not 50


def test_team_view_shows_everyones_balance(shop, client_for):
    shop.patch("/commission/rule", {"active": True, "rate_percent": "5"})
    product = shop.product("COM-6", price="100")
    shop.sale(product, 1)
    team = shop.get("/commission")
    assert any(Decimal(row["balance"]) == Decimal("5.00") for row in team)


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("cashier", False), ("stock_keeper", False)])
def test_who_may_read_team_commission(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/commission", headers=headers).status_code == 200) == allowed


def test_only_owner_may_change_the_rule(client_for):
    manager, headers = client_for("manager")
    response = manager.patch("/api/app/commission/rule", headers=headers, json={"active": True})
    assert response.status_code == 403
