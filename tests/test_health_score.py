"""Business Health Score: five explainable scores, null (not guessed) when data is missing."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def product(self, sku, stock=100, price="100", reorder="5"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "reorder_level": reorder})
        if stock:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def sale(self, product, qty, sold_at):
        self.n += 1
        unit = Decimal(product["selling_price"])
        paid = unit * qty
        return self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"HS-{self.n}",
            "sold_at": sold_at.isoformat(), "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(paid)}],
        })


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_fresh_organization_has_mostly_insufficient_data(shop):
    body = shop.get("/health-score")
    assert body["scores"]["cash"]["insufficient_data"] is True
    assert body["scores"]["sales"]["insufficient_data"] is True
    # Control health is always computable (zero exceptions/approvals is itself a fact),
    # so it alone drives "overall" even when nothing else has data yet.
    assert body["scores"]["control"]["insufficient_data"] is False
    assert body["scores"]["control"]["score"] == 100.0
    assert body["overall"] == 100.0


def test_stock_health_reflects_reorder_levels(shop):
    # The `world` fixture already seeds one healthy product (RICE-1); add one more
    # healthy and one below its reorder level, then check the ratio moved accordingly.
    before = shop.get("/health-score")["scores"]["stock"]["score"]
    shop.product("HS-1", stock=100, reorder="5")   # healthy
    shop.product("HS-2", stock=0, reorder="10")    # below reorder
    after = shop.get("/health-score")["scores"]["stock"]["score"]
    assert after < before
    assert after == pytest.approx(66.7, abs=0.1)  # 2 of 3 products healthy


def test_sales_health_reflects_growth(shop):
    product = shop.product("HS-3")
    # Prior period sale (31-60 days ago) and this period sale (now), this period 2x bigger.
    shop.sale(product, 1, NOW - timedelta(days=45))
    shop.sale(product, 2, NOW - timedelta(days=1))
    body = shop.get("/health-score")
    assert body["scores"]["sales"]["insufficient_data"] is False
    assert body["scores"]["sales"]["score"] == 100.0  # this (200) > prior (100), clamped at 100


def test_customer_health_is_perfect_with_no_balance(shop):
    shop.post("/customers", {"code": "HS-CUST"})
    body = shop.get("/health-score")
    assert body["scores"]["customer"]["insufficient_data"] is False
    assert body["scores"]["customer"]["score"] == 100.0


def test_customer_health_drops_with_overdue_balance(shop):
    product = shop.product("HS-4")
    customer = shop.post("/customers", {"code": "HS-CUST-2"})
    shop.c.post("/api/app/sales", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "invoice_number": "HS-OVERDUE", "customer_id": customer["id"],
        "sold_at": (NOW - timedelta(days=60)).isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1", "unit_price": "100"}],
        "payments": [],
    })
    body = shop.get("/health-score")
    assert body["scores"]["customer"]["score"] == 0.0  # entirely overdue


def test_control_health_drops_with_risk_actions(shop, world):
    product = shop.product("HS-5", stock=0)
    shop.post("/inventory/adjust", {"branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "5", "reason": "found stock"})
    body = shop.get("/health-score")
    assert body["scores"]["control"]["score"] == 95.0  # exactly one inventory.adjusted flag


def test_overall_is_the_average_of_available_scores(shop):
    shop.post("/customers", {"code": "HS-OVERALL"})  # customer health = 100 (no balance)
    body = shop.get("/health-score")
    # Only customer (100) and control (100) are computable here -> overall 100.
    assert body["scores"]["sales"]["insufficient_data"] is True
    assert body["overall"] == 100.0


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("cashier", False), ("stock_keeper", False)])
def test_who_may_read_the_health_score(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/health-score", headers=headers).status_code == 200) == allowed
