"""Loyalty points: earn on sale, redeem as a discount, an append-only ledger."""

from datetime import datetime, timezone
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

    def get(self, path, status=200, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == status, r.text
        return r.json()

    def product(self, sku, price="100", cost="60"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost})
        self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": "1000", "reason": "open"})
        return p

    def customer(self, code):
        return self.post("/customers", {"code": code, "display_name": code})

    def sale(self, product, qty, customer=None, redeem_points="0", paid=None, status=200):
        self.n += 1
        total = Decimal("100") * qty
        paid = str(total if paid is None else paid)
        r = self.c.post("/api/app/sales", headers=self.h, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "sold_at": NOW.isoformat(),
            "customer_id": customer["id"] if customer else None,
            "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": paid}] if paid != "0" else [],
            "redeem_points": redeem_points,
        })
        assert r.status_code == status, r.text
        return r


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def turn_on(shop, points_per_taka="100", redemption_value="0.5"):
    return shop.patch("/loyalty/rule", {"points_per_taka": points_per_taka, "redemption_value": redemption_value, "active": True})


def test_loyalty_is_off_by_default_and_no_points_are_earned(shop):
    rule = shop.get("/loyalty/rule")
    assert rule["active"] is False
    product = shop.product("L-1")
    customer = shop.customer("C-1")
    shop.sale(product, 5, customer=customer)   # ৳500
    balance = shop.get(f"/customers/{customer['id']}/loyalty")
    assert balance["active"] is False and Decimal(balance["balance"]) == 0


def test_turning_it_on_awards_whole_points_on_the_net_sale(shop):
    turn_on(shop)   # 1 point per ৳100
    product = shop.product("L-2")
    customer = shop.customer("C-2")
    shop.sale(product, 5, customer=customer)          # ৳500 -> 5 points
    balance = shop.get(f"/customers/{customer['id']}/loyalty")
    assert balance["active"] is True and Decimal(balance["balance"]) == 5
    assert balance["history"][0]["reason"] == "earned"


def test_points_round_down_never_up(shop):
    turn_on(shop)
    product = shop.product("L-3", price="99")
    customer = shop.customer("C-3")
    r = shop.post("/products", {"sku": "L-3B", "name": "L-3B", "selling_price": "99", "cost_price": "50"})
    shop.post("/inventory/adjust", {"branch_id": shop.w["branch_a"], "product_id": r["id"], "quantity_delta": "10", "reason": "open"})
    shop.n += 1
    resp = shop.c.post("/api/app/sales", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "invoice_number": f"S-{shop.n}", "sold_at": NOW.isoformat(),
        "customer_id": customer["id"], "items": [{"product_id": r["id"], "quantity": "2"}],
        "payments": [{"method": "cash", "amount": "198"}]})
    assert resp.status_code == 200
    balance = shop.get(f"/customers/{customer['id']}/loyalty")
    assert Decimal(balance["balance"]) == 1   # 198 / 100 = 1.98 -> 1, not 2


def test_a_customer_can_redeem_points_for_a_discount(shop):
    turn_on(shop)
    product = shop.product("L-4")
    customer = shop.customer("C-4")
    shop.sale(product, 20, customer=customer)          # ৳2000 -> 20 points earned
    r = shop.sale(product, 5, customer=customer, redeem_points="10", paid="0")  # 10 points = ৳5 off ৳500
    body = r.json()
    assert Decimal(body["total"]) == 495
    balance = shop.get(f"/customers/{customer['id']}/loyalty")
    earned_on_second_sale = Decimal(495) // 100   # 1 point per ৳100, floor
    assert Decimal(balance["balance"]) == 20 - 10 + earned_on_second_sale


def test_redeeming_more_points_than_the_bill_needs_only_spends_what_it_needs(shop):
    turn_on(shop, points_per_taka="10", redemption_value="1")   # 1 point per ৳10, each point worth ৳1
    product = shop.product("L-5")
    customer = shop.customer("C-5")
    shop.sale(product, 100, customer=customer)          # ৳10,000 -> 1000 points
    r = shop.sale(product, 1, customer=customer, redeem_points="500", paid="0")   # bill is only ৳100
    assert Decimal(r.json()["total"]) == 0               # fully covered, not negative
    balance = shop.get(f"/customers/{customer['id']}/loyalty")
    redeemed = next(h for h in balance["history"] if h["reason"] == "redeemed")
    assert Decimal(redeemed["points_delta"]) == -100      # only 100 points spent (৳100 worth), not 500


def test_redeeming_more_points_than_the_customer_has_is_refused(shop):
    turn_on(shop)
    product = shop.product("L-6")
    customer = shop.customer("C-6")
    r = shop.sale(product, 1, customer=customer, redeem_points="50", status=409)
    assert "loyalty points" in r.json()["detail"]


def test_redeeming_needs_a_customer(shop):
    turn_on(shop)
    product = shop.product("L-7")
    r = shop.c.post("/api/app/sales", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "invoice_number": "S-anon", "sold_at": NOW.isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1"}],
        "payments": [{"method": "cash", "amount": "100"}], "redeem_points": "5"})
    assert r.status_code == 422


def test_redemption_posts_to_the_books_as_reduced_revenue(shop):
    turn_on(shop)
    product = shop.product("L-8", cost="60")
    customer = shop.customer("C-8")
    shop.sale(product, 20, customer=customer)                                  # ৳2000, earns 20 points
    shop.sale(product, 5, customer=customer, redeem_points="10", paid="0")     # ৳500 - ৳5 = ৳495
    tb = {r["code"]: r for r in shop.get("/accounting/trial-balance")["accounts"]}
    assert Decimal(tb["4000"]["balance"]) == 2000 + 495   # full revenue recognised net of the loyalty discount


def test_the_owner_can_change_the_rate_or_turn_it_off(shop):
    turn_on(shop, points_per_taka="50", redemption_value="0.25")
    rule = shop.get("/loyalty/rule")
    assert Decimal(rule["points_per_taka"]) == 50 and Decimal(rule["redemption_value"]) == Decimal("0.25")
    product = shop.product("L-9")
    customer = shop.customer("C-9")
    shop.sale(product, 5, customer=customer)   # ৳500 / 50 = 10 points
    assert Decimal(shop.get(f"/customers/{customer['id']}/loyalty")["balance"]) == 10

    shop.patch("/loyalty/rule", {"active": False})
    shop.sale(product, 5, customer=customer)   # loyalty off now: no more points
    assert Decimal(shop.get(f"/customers/{customer['id']}/loyalty")["balance"]) == 10


@pytest.mark.parametrize("role,can_read,can_edit", [
    ("owner", True, True), ("manager", True, False), ("cashier", True, False), ("viewer", True, False)])
def test_who_may_read_and_edit_the_rule(client_for, role, can_read, can_edit):
    client, headers = client_for(role)
    assert (client.get("/api/app/loyalty/rule", headers=headers).status_code == 200) == can_read
    r = client.patch("/api/app/loyalty/rule", headers=headers, json={"active": True})
    assert (r.status_code == 200) == can_edit


def test_another_business_cannot_see_our_customers_points(shop, client_for):
    product = shop.product("L-10")
    customer = shop.customer("C-10")
    turn_on(shop)
    shop.sale(product, 5, customer=customer)
    other, oheaders = client_for("owner", org="org_b")
    assert other.get(f"/api/app/customers/{customer['id']}/loyalty", headers=oheaders).status_code == 404
