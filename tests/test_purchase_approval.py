"""Purchase orders reuse the async Approval Inbox (`expense_amount`'s pattern),
not the synchronous till override — placing a PO is not time-critical the way
a checkout is."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w = client, headers, world

    def post(self, path, body, status=None):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        if status is not None:
            assert r.status_code == status, r.text
        return r

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, r.text
        return r.json()

    def product(self, sku, cost="10"):
        return self.post("/products", {"sku": sku, "name": sku, "selling_price": "20", "cost_price": cost}, status=200).json()

    def supplier(self, code):
        return self.post("/suppliers", {"code": code, "name": code}, status=200).json()

    def purchase(self, product, supplier, qty, unit_cost, status=None):
        return self.post("/purchases", {
            "branch_id": self.w["branch_a"], "supplier_id": supplier["id"], "order_number": f"PO-{product['sku']}-{qty}",
            "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": str(qty), "unit_cost": str(unit_cost)}],
        }, status=status)


@pytest.fixture()
def owner(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_a_small_purchase_posts_immediately(owner):
    product, supplier = owner.product("PU-1"), owner.supplier("S1")
    r = owner.purchase(product, supplier, 10, "10", status=200)
    assert r.json()["status"] == "ordered"
    assert owner.get("/approvals", status="all") == []


def test_a_large_purchase_by_a_manager_is_held_for_the_owner(client_for, world):
    manager, mheaders = client_for("manager")
    shop = Shop(manager, mheaders, world)
    product, supplier = shop.product("PU-2"), shop.supplier("S2")
    r = shop.purchase(product, supplier, 3000, "10", status=202)     # ৳30,000, over the ৳20,000/owner default
    body = r.json()
    assert body["status"] == "pending_approval" and body["needs_role"] == "owner"

    pending = shop.get("/approvals")
    assert len(pending) == 1 and pending[0]["kind"] == "purchase_amount" and Decimal(pending[0]["amount"]) == 30000
    assert not shop.get("/purchases")                                 # nothing created yet


def test_the_owner_can_purchase_the_same_amount_directly(owner):
    product, supplier = owner.product("PU-3"), owner.supplier("S3")
    r = owner.purchase(product, supplier, 3000, "10", status=200)
    assert Decimal(r.json()["total"]) == 30000


def test_approving_creates_exactly_the_purchase_order_that_was_requested(client_for, world):
    manager, mheaders = client_for("manager")
    owner_client, oheaders = client_for("owner")
    shop_m, shop_o = Shop(manager, mheaders, world), Shop(owner_client, oheaders, world)
    product, supplier = shop_o.product("PU-4"), shop_o.supplier("S4")
    shop_m.purchase(product, supplier, 3000, "10", status=202)
    request_id = shop_o.get("/approvals")[0]["id"]

    result = shop_o.post(f"/approvals/{request_id}/approve", {"reason": "বাজেটে আছে"}, status=200).json()
    assert result["status"] == "approved" and result["result_reference_id"]
    orders = shop_o.get("/purchases")
    assert len(orders) == 1 and Decimal(orders[0]["total"]) == 30000 and orders[0]["status"] == "ordered"


def test_rejecting_creates_nothing(client_for, world):
    manager, mheaders = client_for("manager")
    owner_client, oheaders = client_for("owner")
    shop_m, shop_o = Shop(manager, mheaders, world), Shop(owner_client, oheaders, world)
    product, supplier = shop_o.product("PU-5"), shop_o.supplier("S5")
    shop_m.purchase(product, supplier, 3000, "10", status=202)
    request_id = shop_o.get("/approvals")[0]["id"]
    result = shop_o.post(f"/approvals/{request_id}/reject", {"reason": "এখন দরকার নেই"}, status=200).json()
    assert result["status"] == "rejected"
    assert shop_o.get("/purchases") == []


def test_the_owner_can_relax_the_purchase_threshold(client_for, world):
    owner_client, oheaders = client_for("owner")
    shop_o = Shop(owner_client, oheaders, world)
    r = owner_client.patch("/api/app/approvals/rules/purchase_amount", headers=oheaders, json={"threshold": "50000"})
    assert r.status_code == 200

    manager, mheaders = client_for("manager")
    shop_m = Shop(manager, mheaders, world)
    product, supplier = shop_o.product("PU-6"), shop_o.supplier("S6")
    r = shop_m.purchase(product, supplier, 3000, "10", status=200)    # ৳30,000, now under the raised ৳50,000
    assert r.json()["status"] == "ordered"
