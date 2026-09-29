"""Editing products/customers, wholesale prices, credit limits, voiding a sale, baki ageing."""

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

    def product(self, sku, stock=100, price="10", cost="6", **extra):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost, **extra})
        if stock:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def customer(self, code, **extra):
        return self.post("/customers", {"code": code, "display_name": code, **extra})

    def sale(self, product, qty, customer=None, paid=None, days_ago=0, status=200, price=None, method="cash"):
        self.n += 1
        item = {"product_id": product["id"], "quantity": str(qty)}
        if price is not None:
            item["unit_price"] = str(price)
        unit = Decimal(price if price is not None else product["selling_price"])
        paid = unit * qty if paid is None else paid
        r = self.c.post("/api/app/sales", headers=self.h, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "customer_id": customer["id"] if customer else None,
            "sold_at": (NOW - timedelta(days=days_ago)).isoformat(), "items": [item],
            "payments": [{"method": method, "amount": str(paid)}] if paid else []})
        assert r.status_code == status, r.text
        return r.json()

    def stock(self, product):
        rows = self.get("/inventory", branch_id=self.w["branch_a"])
        return next(Decimal(r["quantity"]) for r in rows if r["product_id"] == product["id"])

    def owed(self, customer):
        return Decimal(next(c for c in self.get("/customers") if c["id"] == customer["id"])["balance"])


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


# ── editing what was entered ─────────────────────────────────────────────────

def test_a_price_change_is_saved_and_written_to_the_audit_trail(shop):
    product = shop.product("EDIT-1", price="10")
    r = shop.c.patch(f"/api/app/products/{product['id']}", headers=shop.h, json={"selling_price": "12.50", "wholesale_price": "9", "name": "Renamed"})
    assert r.status_code == 200 and Decimal(r.json()["selling_price"]) == Decimal("12.50") and r.json()["name"] == "Renamed"
    events = [e for e in shop.get("/audit")["items"] if e["action"] == "product.updated"]
    assert events and events[0]["details"]["changes"]["selling_price"] == {"from": "10.00", "to": "12.50"}


def test_a_product_can_be_archived_and_then_is_not_sold_or_listed(shop):
    product = shop.product("OLD-1")
    assert shop.c.patch(f"/api/app/products/{product['id']}", headers=shop.h, json={"active": False}).status_code == 200
    assert "OLD-1" not in [p["sku"] for p in shop.get("/products")]
    shop.sale(product, 1, status=404)


def test_required_product_fields_cannot_be_blanked_and_the_sku_never_changes(shop):
    product = shop.product("KEEP-1", price="10")
    r = shop.c.patch(f"/api/app/products/{product['id']}", headers=shop.h, json={"name": None, "selling_price": None, "sku": "OTHER", "track_expiry": True})
    assert r.status_code == 200 and r.json()["name"] == "KEEP-1" and r.json()["sku"] == "KEEP-1" and r.json()["track_expiry"] is False


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("stock_keeper", False), ("cashier", False), ("accountant", False), ("viewer", False)])
def test_who_may_edit_a_product(client_for, world, role, allowed):
    client, headers = client_for(role)
    r = client.patch(f"/api/app/products/{world['product_a']}", headers=headers, json={"reorder_level": "3"})
    assert (r.status_code == 200) == allowed


def test_another_business_cannot_edit_our_product(client_for, world):
    client, headers = client_for("owner", org="org_b")
    assert client.patch(f"/api/app/products/{world['product_a']}", headers=headers, json={"name": "hack"}).status_code == 404


def test_a_customer_can_be_edited_and_the_phone_stays_out_of_the_audit_trail(shop):
    customer = shop.customer("C-1")
    r = shop.c.patch(f"/api/app/customers/{customer['id']}", headers=shop.h, json={
        "display_name": "রহিমা", "phone": "01712345678", "credit_limit": "500", "price_tier": "wholesale", "marketing_consent": True})
    assert r.status_code == 200 and r.json()["price_tier"] == "wholesale" and Decimal(r.json()["credit_limit"]) == 500
    event = next(e for e in shop.get("/audit")["items"] if e["action"] == "customer.updated")
    assert "01712345678" not in str(event) and "রহিমা" not in str(event)
    assert shop.c.patch(f"/api/app/customers/{customer['id']}", headers=shop.h, json={"credit_limit": None}).json()["credit_limit"] is None


def test_customer_edit_rejects_a_bad_tier_or_phone(shop):
    customer = shop.customer("C-2")
    assert shop.c.patch(f"/api/app/customers/{customer['id']}", headers=shop.h, json={"price_tier": "vip"}).status_code == 422
    assert shop.c.patch(f"/api/app/customers/{customer['id']}", headers=shop.h, json={"phone": "123"}).status_code == 422


# ── wholesale tier ───────────────────────────────────────────────────────────

def test_a_wholesale_customer_gets_the_wholesale_price_by_default(shop):
    product = shop.product("W-1", price="10", wholesale_price="8")
    plain = shop.product("W-2", price="10")
    wholesale = shop.customer("WS", price_tier="wholesale")
    retail = shop.customer("RT")
    shop.sale(product, 5, customer=wholesale, paid=40)
    shop.sale(product, 5, customer=retail)
    shop.sale(plain, 5, customer=wholesale)                           # no wholesale price set -> retail
    shop.sale(product, 5, customer=wholesale, price=9)                # an explicit price always wins
    totals = sorted(Decimal(s["total"]) for s in shop.get("/sales"))
    assert totals == [40, 45, 50, 50]


# ── credit limit ─────────────────────────────────────────────────────────────

def test_credit_is_refused_beyond_the_limit_but_cash_still_sells(shop):
    product = shop.product("CL-1", price="10")
    customer = shop.customer("LIMITED", credit_limit="100")
    shop.sale(product, 6, customer=customer, paid=0)                   # owes 60
    assert shop.owed(customer) == 60
    refused = shop.c.post("/api/app/sales", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "invoice_number": "S-X", "customer_id": customer["id"], "sold_at": NOW.isoformat(),
        "items": [{"product_id": product["id"], "quantity": "5"}], "payments": []})
    assert refused.status_code == 409 and "Credit limit" in refused.json()["detail"]
    assert shop.stock(product) == 94                                   # nothing was taken by the refused sale
    shop.sale(product, 5, customer=customer, paid=20)                  # adds 30 -> 90, within the limit
    shop.sale(product, 5, customer=customer)                           # fully paid: never limited
    assert shop.owed(customer) == 90


def test_paying_a_baki_makes_room_under_the_limit(shop):
    product = shop.product("CL-2", price="10")
    customer = shop.customer("PAYER", credit_limit="100")
    shop.sale(product, 10, customer=customer, paid=0)
    shop.sale(product, 1, customer=customer, paid=0, status=409)
    shop.post(f"/customers/{customer['id']}/payments", {"amount": "40", "payment_method": "cash", "occurred_at": NOW.isoformat()})
    shop.sale(product, 1, customer=customer, paid=0)
    assert shop.owed(customer) == 70


def test_no_limit_means_unlimited_credit(shop):
    product = shop.product("CL-3", price="10")
    customer = shop.customer("FREE")
    shop.sale(product, 50, customer=customer, paid=0)
    assert shop.owed(customer) == 500


# ── voiding a sale ───────────────────────────────────────────────────────────

def test_voiding_returns_the_stock_and_refunds_what_was_paid(shop):
    product = shop.product("V-1", price="10")
    sale = shop.sale(product, 4)
    assert shop.stock(product) == 96
    r = shop.post(f"/sales/{sale['id']}/void", {"reason": "ভুল পণ্য স্ক্যান"})
    assert Decimal(r["refund_amount"]) == 40
    assert shop.stock(product) == 100
    invoice = next(s for s in shop.get("/sales") if s["id"] == sale["id"])
    assert invoice["status"] == "voided" and all(Decimal(i["returned_quantity"]) == Decimal(i["quantity"]) for i in invoice["items"])
    event = next(e for e in shop.get("/audit")["items"] if e["action"] == "sale.voided")
    assert event["details"]["reason"] == "ভুল পণ্য স্ক্যান" and Decimal(event["details"]["refunded"]) == 40


def test_voiding_a_credit_sale_clears_the_customers_baki(shop):
    product = shop.product("V-2", price="10")
    customer = shop.customer("VOIDER")
    sale = shop.sale(product, 5, customer=customer, paid=20)           # owes 30
    assert shop.owed(customer) == 30
    r = shop.post(f"/sales/{sale['id']}/void", {"reason": "গ্রাহক নেননি"})
    assert Decimal(r["refund_amount"]) == 20                            # the 30 due is cancelled, the 20 paid goes back
    assert shop.owed(customer) == 0


def test_a_sale_can_only_be_voided_once_and_not_after_a_return(shop):
    product = shop.product("V-3", price="10")
    sale = shop.sale(product, 4)
    shop.post(f"/sales/{sale['id']}/void", {"reason": "ভুল হয়েছে"})
    again = shop.c.post(f"/api/app/sales/{sale['id']}/void", headers=shop.h, json={"reason": "আবার"})
    assert again.status_code == 409

    other = shop.sale(product, 4)
    line = next(s for s in shop.get("/sales") if s["id"] == other["id"])["items"][0]
    shop.post(f"/sales/{other['id']}/returns", {"return_number": "R-1", "reason": "একটি ফেরত", "returned_at": NOW.isoformat(),
                                                 "refund_method": "cash", "items": [{"sales_order_item_id": line["id"], "quantity": "1"}]})
    assert shop.c.post(f"/api/app/sales/{other['id']}/void", headers=shop.h, json={"reason": "সব বাতিল"}).status_code == 409


def test_voiding_needs_a_reason(shop):
    sale = shop.sale(shop.product("V-4"), 1)
    assert shop.c.post(f"/api/app/sales/{sale['id']}/void", headers=shop.h, json={"reason": "x"}).status_code == 422


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("cashier", False), ("accountant", False), ("stock_keeper", False), ("viewer", False)])
def test_who_may_void(client_for, world, shop, role, allowed):
    sale = shop.sale(shop.product("V-5"), 1)
    client, headers = client_for(role)
    r = client.post(f"/api/app/sales/{sale['id']}/void", headers=headers, json={"reason": "পরীক্ষা"})
    assert (r.status_code == 200) == allowed


def test_voiding_puts_units_back_into_the_batch_they_came_from(shop):
    from datetime import timedelta as td
    product = shop.post("/products", {"sku": "VB-1", "name": "Tracked", "selling_price": "10", "cost_price": "6", "track_expiry": True})
    shop.post("/inventory/adjust", {"branch_id": shop.w["branch_a"], "product_id": product["id"], "quantity_delta": "20", "reason": "open",
                                    "batch_no": "B-SOON", "expiry_date": (date.today() + td(days=40)).isoformat()})
    shop.post("/inventory/adjust", {"branch_id": shop.w["branch_a"], "product_id": product["id"], "quantity_delta": "20", "reason": "open",
                                    "batch_no": "B-LATE", "expiry_date": (date.today() + td(days=400)).isoformat()})
    sale = shop.sale(product, 8)
    shop.post(f"/sales/{sale['id']}/void", {"reason": "ভুল বিক্রি"})
    batches = {b["batch_no"]: Decimal(b["quantity"]) for b in shop.get("/inventory/batches", branch_id=shop.w["branch_a"])}
    assert batches == {"B-SOON": 20, "B-LATE": 20}
    audit = shop.get("/inventory/reconciliation", branch_id=shop.w["branch_a"])
    assert "VB-1" not in [i["sku"] for i in audit["items"]]


# ── ageing ───────────────────────────────────────────────────────────────────

def test_payments_clear_the_oldest_baki_first_and_the_rest_is_aged(shop):
    product = shop.product("AG-1", price="10")
    customer = shop.customer("AGED")
    shop.sale(product, 10, customer=customer, paid=0, days_ago=100)     # 100 owed, 100 days old
    shop.sale(product, 5, customer=customer, paid=0, days_ago=40)       # 50 owed, 40 days old
    shop.sale(product, 2, customer=customer, paid=0, days_ago=3)        # 20 owed, 3 days old
    shop.post(f"/customers/{customer['id']}/payments", {"amount": "120", "payment_method": "cash", "occurred_at": NOW.isoformat()})
    report = shop.get("/receivables/ageing")
    row = next(r for r in report["customers"] if r["code"] == "AGED")
    # 120 clears the 100 (oldest) and 20 of the 50; left: 30 aged 40 days + 20 aged 3 days
    assert Decimal(row["balance"]) == 50
    assert Decimal(row["d90_plus"]) == 0 and Decimal(row["d61_90"]) == 0
    assert Decimal(row["d31_60"]) == 30 and Decimal(row["d0_30"]) == 20
    assert row["oldest_days"] in (40, 39, 41)
    assert Decimal(report["total"]) == 50


def test_ageing_ranks_the_oldest_debtor_first_and_flags_over_limit(shop):
    product = shop.product("AG-2", price="10")
    old = shop.customer("OLD")
    new = shop.customer("NEW")
    shop.sale(product, 5, customer=new, paid=0, days_ago=2)
    shop.sale(product, 3, customer=old, paid=0, days_ago=95)
    shop.c.patch(f"/api/app/customers/{old['id']}", headers=shop.h, json={"credit_limit": "20"})
    report = shop.get("/receivables/ageing")
    assert [r["code"] for r in report["customers"]] == ["OLD", "NEW"]
    assert report["customers"][0]["over_limit"] is True and report["customers"][1]["over_limit"] is False
    assert Decimal(report["buckets"]["d90_plus"]) == 30


def test_settled_customers_and_other_businesses_do_not_appear(shop, client_for):
    product = shop.product("AG-3", price="10")
    customer = shop.customer("SETTLED")
    shop.sale(product, 2, customer=customer, paid=0)
    shop.post(f"/customers/{customer['id']}/payments", {"amount": "20", "payment_method": "cash", "occurred_at": NOW.isoformat()})
    assert "SETTLED" not in [r["code"] for r in shop.get("/receivables/ageing")["customers"]]
    other, other_headers = client_for("owner", org="org_b")
    assert other.get("/api/app/receivables/ageing", headers=other_headers).json()["customers"] == []


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("viewer", True), ("cashier", False), ("stock_keeper", False)])
def test_who_may_read_the_ageing(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/receivables/ageing", headers=headers).status_code == 200) == allowed
