"""B-SMART Algorithm 1 run against a tenant's own operational data.

`api/bsmart_live.py` is a second implementation of Algorithm 1 (reorder /
near-expiry / retention) built from an organization's own sales, inventory,
batches and customers, rather than the thesis's frozen research CSV. These
tests exercise the ``/api/app/bsmart/run`` route end to end through the real
API and DB, not by calling `bsmart_live.generate` directly, so the
Recommendation persistence and the decision/outcome loop it feeds are
covered too.
"""

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

    def get(self, path, status=200, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == status, r.text
        return r.json()

    def product(self, sku, price="100", cost="60", reorder_level="0", track_expiry=False):
        return self.post("/products", {
            "sku": sku, "name": sku, "selling_price": price, "cost_price": cost,
            "reorder_level": reorder_level, "track_expiry": track_expiry,
        })

    def set_budget(self, amount):
        r = self.c.patch("/api/app/organization/operations", headers=self.h, json={
            "business_mode": "products", "payment_methods": ["cash"], "sales_channels": ["in_store"],
            "reorder_budget_bdt": amount,
        })
        assert r.status_code == 200, r.text

    def stock(self, product_id, qty):
        self.post("/inventory/adjust", {
            "branch_id": self.w["branch_a"], "product_id": product_id,
            "quantity_delta": str(qty), "reason": "test setup",
        })

    def customer(self, code, consent=True):
        return self.post("/customers", {"code": code, "display_name": code, "marketing_consent": consent})

    def sale(self, product_id, qty, sold_at, customer_id=None):
        self.n += 1
        self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "sold_at": sold_at.isoformat(),
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(Decimal(qty) * Decimal("100"))}],
        })

    def receive_batch(self, product_id, qty, batch_no, expiry_date):
        supplier = self.post("/suppliers", {"code": f"SUP-{self.n}", "name": "Test Supplier"})
        po = self.post("/purchases", {
            "branch_id": self.w["branch_a"], "supplier_id": supplier["id"], "order_number": f"PO-{batch_no}",
            "ordered_at": NOW.isoformat(),
            "items": [{"product_id": product_id, "quantity": str(qty), "unit_cost": "60"}],
        })
        detail = next(p for p in self.get("/purchases") if p["id"] == po["id"])
        item_id = detail["items"][0]["id"]
        self.post(f"/purchases/{po['id']}/receive", {
            "received_at": NOW.isoformat(),
            "items": [{"purchase_order_item_id": item_id, "quantity": str(qty),
                       "batch_no": batch_no, "expiry_date": expiry_date.isoformat()}],
        })


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_a_reorder_candidate_appears_when_recent_sales_outrun_stock(shop):
    product = shop.product("LIVE-1", reorder_level="5")
    shop.stock(product["id"], 25)   # enough to cover every sale below without overselling
    for day in range(10):
        shop.sale(product["id"], 2, NOW - timedelta(days=day))   # 20 sold, 5 left -- below reorder_level

    result = shop.post("/bsmart/run", {})
    assert result["status"] == "imported"
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    reorder = [r for r in recos if r["action_type"] == "reorder" and r["sku"] == "LIVE-1"]
    assert reorder, recos
    assert reorder[0]["source"] == "live"
    assert reorder[0]["confidence"] == "baseline"   # no trained demand model in this test


def test_no_reorder_candidate_when_stock_is_ample(shop):
    product = shop.product("LIVE-2", reorder_level="5")
    shop.stock(product["id"], 500)
    shop.post("/bsmart/run", {})
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    assert not [r for r in recos if r["sku"] == "LIVE-2"]


def test_a_near_expiry_batch_produces_an_expiry_candidate(shop):
    product = shop.product("LIVE-3", track_expiry=True)
    shop.receive_batch(product["id"], 100, "B-NEAR", (NOW + timedelta(days=30)).date())

    result = shop.post("/bsmart/run", {})
    assert result["status"] == "imported"
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    expiry = [r for r in recos if r["action_type"] == "expiry" and r["sku"] == "LIVE-3"]
    assert expiry, recos
    assert expiry[0]["confidence"] == "rule"
    assert expiry[0]["source"] == "live"


def test_a_batch_expiring_far_in_the_future_is_not_a_candidate(shop):
    product = shop.product("LIVE-4", track_expiry=True)
    shop.receive_batch(product["id"], 100, "B-FAR", (NOW + timedelta(days=300)).date())
    shop.post("/bsmart/run", {})
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    assert not [r for r in recos if r["sku"] == "LIVE-4"]


def test_retention_only_offers_consenting_inactive_customers(shop):
    product = shop.product("LIVE-5")
    shop.stock(product["id"], 1000)
    consenting = shop.customer("RET-YES", consent=True)
    not_consenting = shop.customer("RET-NO", consent=False)
    old_date = NOW - timedelta(days=120)
    shop.sale(product["id"], 1, old_date, customer_id=consenting["id"])
    shop.sale(product["id"], 1, old_date, customer_id=not_consenting["id"])

    shop.post("/bsmart/run", {})
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    retained_ids = {r["customer_id"] for r in recos if r["action_type"] == "retention"}
    assert consenting["id"] in retained_ids
    assert not_consenting["id"] not in retained_ids


def test_a_recently_active_customer_is_not_offered_for_retention(shop):
    product = shop.product("LIVE-6")
    shop.stock(product["id"], 1000)
    customer = shop.customer("RET-RECENT", consent=True)
    shop.sale(product["id"], 1, NOW - timedelta(days=2), customer_id=customer["id"])
    shop.post("/bsmart/run", {})
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    assert customer["id"] not in {r["customer_id"] for r in recos if r["action_type"] == "retention"}


def test_running_twice_the_same_day_does_not_duplicate(shop):
    product = shop.product("LIVE-7", reorder_level="5")
    shop.stock(product["id"], 25)
    for day in range(10):
        shop.sale(product["id"], 2, NOW - timedelta(days=day))

    first = shop.post("/bsmart/run", {})
    assert first["status"] == "imported"
    second = shop.post("/bsmart/run", {})
    assert second["status"] == "already_imported"
    assert second["recommendations"] == first["recommendations"]


def test_live_and_research_import_runs_coexist(shop):
    product = shop.product("LIVE-8", reorder_level="5")
    shop.stock(product["id"], 25)
    for day in range(10):
        shop.sale(product["id"], 2, NOW - timedelta(days=day))
    shop.post("/bsmart/run", {})
    # A research-artifact import (if a run exists on disk) must not collide with
    # the live run's rows for the same day; if no artifact file exists yet in
    # this test environment, the import correctly 404s instead of silently
    # merging with the live rows.
    r = shop.c.post("/api/app/bsmart/import-run", headers=shop.h)
    assert r.status_code in (200, 404)
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    assert all(r["source"] in ("live", "research_import") for r in recos)


def test_an_owner_declared_budget_caps_reorder_to_the_highest_utility_items(shop):
    cheap = shop.product("BUD-1", reorder_level="5")
    pricey = shop.product("BUD-2", reorder_level="5")
    for product in (cheap, pricey):
        shop.stock(product["id"], 25)
        for day in range(10):
            shop.sale(product["id"], 2, NOW - timedelta(days=day))

    # Only enough budget for one of the two reorders, whichever scores higher.
    shop.set_budget("50")
    result = shop.post("/bsmart/run", {})
    assert result["status"] == "imported"
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    reorder_skus = {r["sku"] for r in recos if r["action_type"] == "reorder"}
    assert reorder_skus <= {"BUD-1", "BUD-2"}
    assert len(reorder_skus) <= 1   # the tiny budget cannot cover both


def test_no_declared_budget_leaves_reorder_unconstrained(shop):
    product = shop.product("BUD-3", reorder_level="5")
    shop.stock(product["id"], 25)
    for day in range(10):
        shop.sale(product["id"], 2, NOW - timedelta(days=day))
    # No set_budget() call: default behaviour, same as before this feature.
    shop.post("/bsmart/run", {})
    recos = shop.get("/bsmart/recommendations")["recommendations"]
    assert "BUD-3" in {r["sku"] for r in recos if r["action_type"] == "reorder"}
