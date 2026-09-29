"""Cash-Locked Meter, ABC-XYZ classification, and the supplier price-watch."""

from datetime import date, datetime, timedelta, timezone
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

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def product(self, sku, stock=1000, price="10", cost="6", **extra):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost, **extra})
        if stock:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def customer(self, code, **extra):
        return self.post("/customers", {"code": code, "display_name": code, **extra})

    def sale(self, product, qty, customer=None, paid=None, days_ago=0, price=None):
        self.n += 1
        item = {"product_id": product["id"], "quantity": str(qty)}
        if price is not None:
            item["unit_price"] = str(price)
        unit = Decimal(price if price is not None else product["selling_price"])
        paid = unit * qty if paid is None else paid
        r = self.c.post("/api/app/sales", headers=self.h, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "customer_id": customer["id"] if customer else None,
            "sold_at": (NOW - timedelta(days=days_ago)).isoformat(), "items": [item],
            "payments": [{"method": "cash", "amount": str(paid)}] if paid else []})
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


# ── cash-locked meter ────────────────────────────────────────────────────────

def test_stock_that_has_not_sold_in_two_months_counts_as_dead(shop):
    fresh = shop.product("FRESH", stock=10, cost="5")           # sold recently: not dead
    shop.sale(fresh, 1, days_ago=1)
    stale = shop.product("STALE", stock=20, cost="8")           # sold, but 90 days ago
    shop.sale(stale, 1, days_ago=90)

    report = shop.get("/insights/cash-locked")
    dead = {i["sku"]: i for i in report["dead_stock"]["top"]}
    assert "FRESH" not in dead
    assert Decimal(dead["STALE"]["value"]) == 19 * Decimal("8")     # 20 minus the 1 sold
    assert Decimal(report["dead_stock"]["value"]) == 19 * 8


def test_a_brand_new_unsold_product_is_not_flagged_dead(shop):
    shop.product("NEW", stock=15, cost="4")                     # created just now, never sold
    report = shop.get("/insights/cash-locked")
    assert "NEW" not in {i["sku"] for i in report["dead_stock"]["top"]}


def test_near_expiry_and_overdue_baki_add_into_the_total(shop):
    tracked = shop.post("/products", {"sku": "EXP-1", "name": "EXP-1", "selling_price": "10", "cost_price": "5", "track_expiry": True})
    shop.post("/inventory/adjust", {"branch_id": shop.w["branch_a"], "product_id": tracked["id"], "quantity_delta": "30", "reason": "open",
                                    "batch_no": "B1", "expiry_date": (date.today() + timedelta(days=20)).isoformat()})
    customer = shop.customer("OWES")
    old = shop.product("OLDPAY", cost="6")
    shop.sale(old, 5, customer=customer, paid=0, days_ago=95)   # 50 owed, 95 days old -> overdue
    recent = shop.product("NEWPAY", cost="6")
    shop.sale(recent, 2, customer=customer, paid=0, days_ago=5)  # 20 owed, 5 days old -> not overdue

    report = shop.get("/insights/cash-locked")
    assert Decimal(report["near_expiry"]["value"]) == 30 * Decimal("5")
    assert Decimal(report["overdue_baki"]["value"]) == 50
    assert report["overdue_baki"]["customers"] == 1
    assert Decimal(report["total"]) == Decimal(report["dead_stock"]["value"]) + 30 * 5 + 50


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("cashier", False), ("stock_keeper", False)])
def test_who_may_see_the_cash_locked_meter(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/insights/cash-locked", headers=headers).status_code == 200) == allowed


def test_cash_locked_is_isolated_per_business(client_for):
    a, ha = client_for("owner", org="org_a")
    b, hb = client_for("owner", org="org_b")
    a.post("/api/app/products", headers=ha, json={"sku": "ISO-1", "name": "ISO-1", "selling_price": "10", "cost_price": "9"})
    report_b = b.get("/api/app/insights/cash-locked", headers=hb).json()
    assert "ISO-1" not in {i["sku"] for i in report_b["dead_stock"]["top"]}


# ── ABC-XYZ ──────────────────────────────────────────────────────────────────

def test_abc_ranks_by_cumulative_revenue_share(shop):
    big = shop.product("BIG", cost="4", price="100")
    small = shop.product("SMALL", cost="1", price="5")
    shop.sale(big, 10)     # 1000 revenue
    shop.sale(small, 2)    # 10 revenue
    report = shop.get("/insights/abc-xyz")
    by_sku = {r["sku"]: r for r in report["items"]}
    assert by_sku["BIG"]["abc"] == "A"
    assert by_sku["SMALL"]["abc"] in ("B", "C")
    assert by_sku["BIG"]["revenue_share"] > by_sku["SMALL"]["revenue_share"]


def test_xyz_needs_at_least_three_weeks_of_sales_or_it_abstains(shop):
    steady = shop.product("STEADY", cost="2", price="10")
    for week in range(4):
        shop.sale(steady, 10, days_ago=week * 7)          # same qty every week -> low CV
    once = shop.product("ONCE", cost="2", price="10")
    shop.sale(once, 5)                                     # a single sale: not enough weeks
    report = shop.get("/insights/abc-xyz")
    by_sku = {r["sku"]: r for r in report["items"]}
    assert by_sku["STEADY"]["xyz"] == "X"
    assert by_sku["ONCE"]["xyz"] is None


def test_a_product_never_sold_in_the_window_gets_no_abc_class(shop):
    shop.product("IDLE", stock=1, cost="1")
    report = shop.get("/insights/abc-xyz")
    assert next(r for r in report["items"] if r["sku"] == "IDLE")["abc"] is None


def test_dead_stock_flag_matches_the_cash_locked_meter(shop):
    stale = shop.product("DEADFLAG", stock=10, cost="3")
    shop.sale(stale, 1, days_ago=90)
    report = shop.get("/insights/abc-xyz")
    row = next(r for r in report["items"] if r["sku"] == "DEADFLAG")
    assert row["dead_stock"] is True and Decimal(row["stock_value"]) == 27


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("cashier", True), ("viewer", True), ("stock_keeper", False), ("accountant", True)])
def test_who_may_see_abc_xyz(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/insights/abc-xyz", headers=headers).status_code == 200) == allowed


# ── supplier price-watch ─────────────────────────────────────────────────────

def test_a_price_rise_between_the_last_two_purchases_is_flagged(shop):
    product = shop.product("PW-1")
    supplier = shop.post("/suppliers", {"code": "S1", "name": "Square"})
    for cost, days_ago in [("10", 60), ("11.5", 5)]:            # 15% rise
        shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": f"PO-{days_ago}",
                                 "ordered_at": (NOW - timedelta(days=days_ago)).isoformat(),
                                 "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": cost}]})
    report = shop.get("/insights/price-watch")
    row = next(i for i in report["items"] if i["sku"] == "PW-1")
    assert row["supplier_name"] == "Square" and abs(row["change"] - 0.15) < 0.001
    assert Decimal(row["previous_cost"]) == Decimal("10") and Decimal(row["latest_cost"]) == Decimal("11.5")


def test_one_purchase_is_not_a_trend_and_small_moves_are_not_flagged(shop):
    product = shop.product("PW-2")
    steady = shop.product("PW-3")
    supplier = shop.post("/suppliers", {"code": "S2", "name": "One"})
    shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-1",
                             "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "1", "unit_cost": "10"}]})
    for cost in ("10", "10.2"):                                  # 2% move, under the 5% default threshold
        shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": f"PO-{cost}",
                                 "ordered_at": NOW.isoformat(), "items": [{"product_id": steady["id"], "quantity": "1", "unit_cost": cost}]})
    report = shop.get("/insights/price-watch")
    skus = {i["sku"] for i in report["items"]}
    assert "PW-2" not in skus and "PW-3" not in skus


def test_a_lower_threshold_catches_smaller_moves(shop):
    product = shop.product("PW-4")
    supplier = shop.post("/suppliers", {"code": "S3", "name": "Two"})
    for cost in ("10", "10.2"):
        shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": f"PO-{cost}",
                                 "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "1", "unit_cost": cost}]})
    assert {i["sku"] for i in shop.get("/insights/price-watch", threshold="0.01")["items"]} == {"PW-4"}


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("stock_keeper", True), ("cashier", False)])
def test_who_may_see_price_watch(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/insights/price-watch", headers=headers).status_code == 200) == allowed
