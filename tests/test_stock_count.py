"""Stock take: snapshot the system quantity, enter what's actually on the
shelf, apply the difference as one reviewed batch."""

from decimal import Decimal

import pytest


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w = client, headers, world

    def post(self, path, body, status=200):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def patch(self, path, body, status=200):
        r = self.c.patch(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, status=200, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == status, r.text
        return r.json()

    def product(self, sku, stock=100, cost="10", **extra):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": "20", "cost_price": cost, **extra})
        if stock:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def trial_balance(self):
        return self.get("/accounting/trial-balance")


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_starting_a_count_snapshots_the_current_system_quantity(shop):
    product = shop.product("SC-1", stock=40)
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line = next(ln for ln in count["lines"] if ln["product_id"] == product["id"])
    assert Decimal(line["system_qty"]) == 40 and line["counted_qty"] is None


def test_expiry_tracked_products_are_left_out_of_the_count(shop):
    shop.post("/products", {"sku": "SC-2", "name": "SC-2", "selling_price": "20", "cost_price": "10", "track_expiry": True})
    shop.product("SC-3", stock=5)
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    skus = {ln["sku"] for ln in count["lines"]}
    assert "SC-2" not in skus and "SC-3" in skus


def test_only_one_open_count_per_branch_at_a_time(shop):
    shop.product("SC-4", stock=1)
    shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    r = shop.c.post("/api/app/inventory/stock-counts", headers=shop.h, json={"branch_id": shop.w["branch_a"]})
    assert r.status_code == 409


def test_entering_a_count_and_completing_applies_the_variance(shop):
    product = shop.product("SC-5", stock=40, cost="10")
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line = next(ln for ln in count["lines"] if ln["product_id"] == product["id"])
    updated = shop.patch(f"/inventory/stock-counts/{count['id']}/lines/{line['id']}", {"counted_qty": "35"})
    assert Decimal(updated["variance"]) == -5

    result = shop.post(f"/inventory/stock-counts/{count['id']}/complete", {})
    assert result["adjusted_lines"] == 1 and Decimal(result["shrinkage_value"]) == 50 and Decimal(result["gain_value"]) == 0

    stock = {r["sku"]: Decimal(r["quantity"]) for r in shop.get("/inventory", branch_id=shop.w["branch_a"])}
    assert stock["SC-5"] == 35


def test_found_extra_stock_posts_as_a_gain_not_a_negative_shrinkage(shop):
    product = shop.product("SC-6", stock=10, cost="10")
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line = next(ln for ln in count["lines"] if ln["product_id"] == product["id"])
    shop.patch(f"/inventory/stock-counts/{count['id']}/lines/{line['id']}", {"counted_qty": "13"})
    result = shop.post(f"/inventory/stock-counts/{count['id']}/complete", {})
    assert Decimal(result["gain_value"]) == 30 and Decimal(result["shrinkage_value"]) == 0


def test_uncounted_lines_are_left_untouched(shop):
    a = shop.product("SC-7", stock=10)
    b = shop.product("SC-8", stock=20)
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line_a = next(ln for ln in count["lines"] if ln["product_id"] == a["id"])
    shop.patch(f"/inventory/stock-counts/{count['id']}/lines/{line_a['id']}", {"counted_qty": "9"})
    result = shop.post(f"/inventory/stock-counts/{count['id']}/complete", {})
    assert result["adjusted_lines"] == 1
    stock = {r["sku"]: Decimal(r["quantity"]) for r in shop.get("/inventory", branch_id=shop.w["branch_a"])}
    assert stock["SC-7"] == 9 and stock["SC-8"] == 20


def test_the_variance_posts_to_the_books(shop):
    product = shop.product("SC-9", stock=50, cost="8")
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line = next(ln for ln in count["lines"] if ln["product_id"] == product["id"])
    shop.patch(f"/inventory/stock-counts/{count['id']}/lines/{line['id']}", {"counted_qty": "45"})
    shop.post(f"/inventory/stock-counts/{count['id']}/complete", {})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["5910"]["balance"]) == 40 and Decimal(tb["1200"]["balance"]) == -40   # 5 units * 8


def test_a_completed_count_cannot_be_entered_or_completed_again(shop):
    product = shop.product("SC-10", stock=10)
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line = next(ln for ln in count["lines"] if ln["product_id"] == product["id"])
    shop.patch(f"/inventory/stock-counts/{count['id']}/lines/{line['id']}", {"counted_qty": "9"})
    shop.post(f"/inventory/stock-counts/{count['id']}/complete", {})
    again = shop.c.post(f"/api/app/inventory/stock-counts/{count['id']}/complete", headers=shop.h, json={})
    assert again.status_code == 409
    re_enter = shop.c.patch(f"/api/app/inventory/stock-counts/{count['id']}/lines/{line['id']}", headers=shop.h, json={"counted_qty": "1"})
    assert re_enter.status_code == 409


def test_the_history_lists_counts_with_a_variance_summary(shop):
    product = shop.product("SC-11", stock=10)
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    line = next(ln for ln in count["lines"] if ln["product_id"] == product["id"])
    shop.patch(f"/inventory/stock-counts/{count['id']}/lines/{line['id']}", {"counted_qty": "8"})
    shop.post(f"/inventory/stock-counts/{count['id']}/complete", {})
    history = shop.get("/inventory/stock-counts", branch_id=shop.w["branch_a"])
    row = next(r for r in history if r["id"] == count["id"])
    assert row["status"] == "completed" and row["counted"] == 1 and row["with_variance"] == 1
    assert row["started_by"] == "owner A"


def test_another_business_cannot_see_or_touch_our_count(shop, client_for):
    shop.product("SC-12", stock=10)
    count = shop.post("/inventory/stock-counts", {"branch_id": shop.w["branch_a"]})
    other, oheaders = client_for("owner", org="org_b")
    assert other.get(f"/api/app/inventory/stock-counts/{count['id']}", headers=oheaders).status_code == 404
    assert other.post(f"/api/app/inventory/stock-counts/{count['id']}/complete", headers=oheaders, json={}).status_code == 404


@pytest.mark.parametrize("role,can_read,can_adjust", [
    ("owner", True, True), ("manager", True, True), ("stock_keeper", True, True),
    ("cashier", True, False), ("viewer", True, False), ("accountant", True, False)])
def test_who_may_run_a_stock_count(client_for, world, role, can_read, can_adjust):
    client, headers = client_for(role)
    started = client.post("/api/app/inventory/stock-counts", headers=headers, json={"branch_id": world["branch_a"]})
    assert (started.status_code == 200) == can_adjust
    listed = client.get("/api/app/inventory/stock-counts", headers=headers, params={"branch_id": world["branch_a"]})
    assert (listed.status_code == 200) == can_read
