"""Morning brief, alerts, daily cash count, customer/supplier detail, branch transfer, honest profit."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.domain_models import Batch
from api.timeutil import dhaka_today

NOW = datetime.now(timezone.utc)
TODAY = dhaka_today()


def iso(delta_days=0):
    return (NOW + timedelta(days=delta_days)).isoformat()


class Shop:
    def __init__(self, client, headers, world, engine):
        self.c, self.h, self.w, self.engine = client, headers, world, engine
        self.n = 0

    def post(self, path, body):
        response = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert response.status_code == 200, (path, response.text)
        return response.json()

    def get(self, path, **params):
        return self.c.get(f"/api/app{path}", headers=self.h, params=params)

    def product(self, sku="P-1", price="15", cost="10", stock=20, track=False, reorder="0"):
        product = self.post("/products", {"sku": sku, "name": f"Item {sku}", "selling_price": price,
                                          "cost_price": cost, "track_expiry": track, "reorder_level": reorder})
        if stock and not track:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": product["id"],
                                            "quantity_delta": str(stock), "reason": "opening"})
        return product

    def customer(self, code="C1"):
        return self.post("/customers", {"code": code, "display_name": f"Customer {code}"})

    def sell(self, product, qty=1, customer=None, paid=None, when=None, method="cash"):
        self.n += 1
        price = Decimal(product["selling_price"])
        total = price * qty
        paid = total if paid is None else Decimal(paid)
        body = {"branch_id": self.w["branch_a"], "invoice_number": f"INV-{self.n}", "sold_at": when or iso(),
                "customer_id": customer["id"] if customer else None,
                "items": [{"product_id": product["id"], "quantity": str(qty)}],
                "payments": [{"method": method, "amount": str(paid)}] if paid > 0 else []}
        return self.post("/sales", body)

    def supplier(self, code="S1"):
        return self.post("/suppliers", {"code": code, "name": f"Supplier {code}", "typical_lead_days": 3})

    def order(self, supplier, product, qty=10, cost="10", ordered=None, expected=None, po="PO-1"):
        return self.post("/purchases", {
            "branch_id": self.w["branch_a"], "supplier_id": supplier["id"], "order_number": po,
            "ordered_at": ordered or iso(), "expected_at": expected,
            "items": [{"product_id": product["id"], "quantity": str(qty), "unit_cost": cost}]})


@pytest.fixture()
def shop(client_for, world, engine):
    client, headers = client_for("owner")
    return Shop(client, headers, world, engine)


# ── morning brief ────────────────────────────────────────────────────────────

def test_brief_reports_yesterday_low_stock_and_who_owes(shop):
    product = shop.product(stock=3, reorder="5")
    customer = shop.customer()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=12).isoformat()
    shop.sell(product, 1, customer=customer, paid=0, when=yesterday)
    brief = shop.get("/brief").json()
    assert Decimal(brief["yesterday"]["sales"]) == 15 and brief["yesterday"]["orders"] == 1
    assert brief["low_stock"]["count"] == 1 and brief["low_stock"]["items"][0]["name"] == "Item P-1"
    assert Decimal(brief["dues"]["total"]) == 15 and brief["dues"]["top"][0]["name"] == "Customer C1"


def test_brief_leaves_out_what_the_role_may_not_see(client_for, world):
    client, headers = client_for("evaluator")
    brief = client.get("/api/app/brief", headers=headers).json()
    assert "yesterday" in brief and "dues" not in brief and "low_stock" not in brief
    cashier, cashier_headers = client_for("cashier")
    assert cashier.get("/api/app/brief", headers=cashier_headers).status_code == 403


# ── alerts ───────────────────────────────────────────────────────────────────

def kinds(response):
    return {a["kind"] for a in response.json()["alerts"]}


def test_alerts_flag_stock_expiry_baki_and_late_orders(shop, engine):
    empty = shop.product("EMPTY", stock=0)
    shop.product("LOW", stock=2, reorder="5")
    tracked = shop.product("TRK", track=True)
    supplier = shop.supplier()
    po = shop.order(supplier, tracked, qty=5, po="PO-T")
    line = next(p for p in shop.get("/purchases").json() if p["id"] == po["id"])["items"][0]["id"]
    shop.post(f"/purchases/{po['id']}/receive", {"received_at": iso(), "items": [
        {"purchase_order_item_id": line, "quantity": "5", "batch_no": "B1", "expiry_date": (TODAY + timedelta(days=20)).isoformat()}]})
    shop.order(supplier, empty, po="PO-LATE", expected=iso(-3))
    shop.sell(shop.product("SELL"), 1, customer=shop.customer(), paid=0)
    seen = kinds(shop.get("/alerts"))
    assert {"out_of_stock", "low_stock", "near_expiry", "baki", "late_delivery"} <= seen
    with Session(engine) as db:
        db.scalar(select(Batch)).expiry_date = TODAY - timedelta(days=1)
        db.commit()
    assert "expired" in kinds(shop.get("/alerts"))


def test_alerts_are_ordered_most_urgent_first(shop):
    shop.product("EMPTY", stock=0)
    shop.sell(shop.product("SELL"), 1, customer=shop.customer(), paid=0)
    severities = [a["severity"] for a in shop.get("/alerts").json()["alerts"]]
    assert severities == sorted(severities, key={"danger": 0, "warn": 1, "info": 2}.get)


def test_a_cashier_sees_stock_alerts_but_not_money_alerts(shop, client_for):
    shop.product("EMPTY", stock=0)
    shop.sell(shop.product("SELL"), 1, customer=shop.customer(), paid=0)
    cashier, headers = client_for("cashier")
    seen = kinds(cashier.get("/api/app/alerts", headers=headers))
    assert "out_of_stock" in seen and "baki" not in seen


# ── daily cash count ─────────────────────────────────────────────────────────

def cash_scenario(shop):
    product = shop.product(stock=50)
    customer = shop.customer()
    shop.sell(product, 4)                                                   # ৳60 cash
    shop.sell(product, 2, method="bkash")                                   # mobile money: not in the drawer
    shop.sell(product, 2, customer=customer, paid=0)                        # ৳30 on credit
    shop.post(f"/customers/{customer['id']}/payments", {"amount": "10", "payment_method": "cash", "occurred_at": iso()})
    shop.post("/expenses", {"category": "Tea", "amount": "20", "payment_method": "cash", "incurred_at": iso()})
    supplier = shop.supplier()
    order = shop.order(supplier, product, qty=10, po="PO-C")
    line = next(p for p in shop.get("/purchases").json() if p["id"] == order["id"])["items"][0]["id"]
    shop.post(f"/purchases/{order['id']}/receive", {"received_at": iso(), "items": [{"purchase_order_item_id": line, "quantity": "10"}]})
    shop.post(f"/suppliers/{supplier['id']}/payments", {"amount": "25", "payment_method": "cash", "occurred_at": iso()})


def test_the_day_summary_adds_up_only_cash(shop):
    cash_scenario(shop)
    day = shop.get("/cash/day", branch_id=shop.w["branch_a"]).json()
    assert Decimal(day["cash_sales"]) == 60          # the bKash and credit sales are not cash
    assert Decimal(day["baki_collected"]) == 10
    assert Decimal(day["expenses"]) == 20
    assert Decimal(day["supplier_payments"]) == 25
    assert Decimal(day["expected_cash"]) == 60 + 10 - 20 - 25
    assert day["closed"] is None


def close(shop, counted, note=None, opening="0", day=None):
    return shop.c.post("/api/app/cash/close", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "business_date": (day or TODAY).isoformat(),
        "opening_cash": opening, "counted_cash": counted, **({"note": note} if note else {})})


def test_closing_the_day_records_the_variance_and_needs_a_reason_when_short(shop):
    cash_scenario(shop)
    assert close(shop, "20").status_code == 422              # 25 expected, 20 counted, no explanation
    ok = close(shop, "20", note="Gave change from own pocket")
    assert ok.status_code == 200 and Decimal(ok.json()["variance"]) == -5
    assert close(shop, "25").status_code == 409              # one close per day
    day = shop.get("/cash/day", branch_id=shop.w["branch_a"]).json()
    assert Decimal(day["closed"]["variance"]) == -5
    row = shop.get("/cash/closes").json()[0]
    assert Decimal(row["counted_cash"]) == 20 and row["note"] == "Gave change from own pocket"


def test_an_exact_count_needs_no_note_and_tomorrow_starts_from_it(shop):
    cash_scenario(shop)
    assert close(shop, "25").status_code == 200
    tomorrow = shop.c.get("/api/app/cash/day", headers=shop.h, params={
        "branch_id": shop.w["branch_a"], "day": (TODAY + timedelta(days=1)).isoformat()}).json()
    assert Decimal(tomorrow["suggested_opening"]) == 25


def test_a_future_day_cannot_be_closed(shop):
    assert close(shop, "0", day=TODAY + timedelta(days=2)).status_code == 422


def test_cash_close_is_audited(shop):
    cash_scenario(shop)
    close(shop, "25")
    actions = [i["action"] for i in shop.get("/audit", actions="cash.").json()["items"]]
    assert actions == ["cash.closed"]


@pytest.mark.parametrize("role,can_read,can_close", [
    ("owner", True, True), ("manager", True, True), ("accountant", True, True), ("cashier", True, True),
    ("viewer", True, False), ("stock_keeper", False, False), ("evaluator", False, False)])
def test_who_may_see_and_close_the_cash(shop, client_for, world, role, can_read, can_close):
    client, headers = client_for(role)
    read = client.get("/api/app/cash/day", headers=headers, params={"branch_id": world["branch_a"]})
    write = client.post("/api/app/cash/close", headers=headers, json={
        "branch_id": world["branch_a"], "business_date": TODAY.isoformat(), "opening_cash": "0", "counted_cash": "0"})
    assert (read.status_code == 200) == can_read
    assert (write.status_code == 200) == can_close


# ── customer and supplier detail ─────────────────────────────────────────────

def test_customer_summary(shop):
    product = shop.product(stock=30)
    customer = shop.customer()
    shop.sell(product, 2, customer=customer)
    shop.sell(product, 3, customer=customer, paid=0)
    summary = shop.get(f"/customers/{customer['id']}/summary").json()
    assert summary["orders"] == 2 and Decimal(summary["total_spent"]) == 75 and Decimal(summary["due"]) == 45
    assert summary["top_products"][0]["quantity"] == "5.000" or Decimal(summary["top_products"][0]["quantity"]) == 5
    assert summary["days_since_last_purchase"] == 0 and len(summary["recent"]) == 2


def test_a_customer_of_another_business_is_not_found(shop, client_for):
    customer = shop.customer()
    other, headers = client_for("owner", org="org_b")
    assert other.get(f"/api/app/customers/{customer['id']}/summary", headers=headers).status_code == 404


def test_supplier_stats_measure_real_lead_time_punctuality_and_price_change(shop):
    product = shop.product(stock=0)
    supplier = shop.supplier()
    ordered = iso(-5)
    first = shop.order(supplier, product, qty=10, cost="10", ordered=ordered, expected=iso(-2), po="PO-A")
    second = shop.order(supplier, product, qty=10, cost="12", ordered=iso(-1), expected=iso(5), po="PO-B")
    for order, received in ((first, iso(-3)), (second, iso())):
        line = next(p for p in shop.get("/purchases").json() if p["id"] == order["id"])["items"][0]["id"]
        shop.post(f"/purchases/{order['id']}/receive", {"received_at": received, "items": [{"purchase_order_item_id": line, "quantity": "10"}]})
    stats = shop.get(f"/suppliers/{supplier['id']}/stats").json()
    assert stats["orders"] == 2 and stats["delivered_orders"] == 2
    assert stats["average_lead_days"] == pytest.approx(1.5, abs=0.2)     # 2 days and 1 day
    assert stats["on_time_rate"] == 1.0
    move = stats["price_movement"][0]
    assert Decimal(move["last_cost"]) == 12 and move["change_pct"] == pytest.approx(20.0)


def test_a_supplier_with_no_deliveries_reports_nothing_measured(shop):
    stats = shop.get(f"/suppliers/{shop.supplier()['id']}/stats").json()
    assert stats["average_lead_days"] is None and stats["on_time_rate"] is None


# ── branch transfer ──────────────────────────────────────────────────────────

@pytest.fixture()
def two_branches(shop):
    second = shop.post("/branches", {"code": "B2", "name": "Second"})
    return shop.w["branch_a"], second["id"]


def stock_at(shop, branch, product):
    rows = shop.get("/inventory", branch_id=branch).json()
    return Decimal(next(r for r in rows if r["product_id"] == product["id"])["quantity"])


def test_transfer_moves_stock_and_keeps_both_ledgers_consistent(shop, two_branches):
    source, dest = two_branches
    product = shop.product(stock=20)
    shop.post("/inventory/transfer", {"from_branch_id": source, "to_branch_id": dest, "product_id": product["id"], "quantity": "8"})
    assert stock_at(shop, source, product) == 12 and stock_at(shop, dest, product) == 8
    for branch in (source, dest):
        issues = shop.get("/inventory/reconciliation", branch_id=branch).json()["items"]
        assert [i for i in issues if i["sku"] == product["sku"] and i["batch_residual"] not in (None, "0.000")] == []


def test_transfer_refuses_more_than_the_source_holds_and_the_same_branch(shop, two_branches):
    source, dest = two_branches
    product = shop.product(stock=5)
    args = {"product_id": product["id"], "quantity": "9"}
    assert shop.c.post("/api/app/inventory/transfer", headers=shop.h, json={"from_branch_id": source, "to_branch_id": dest, **args}).status_code == 409
    assert shop.c.post("/api/app/inventory/transfer", headers=shop.h, json={"from_branch_id": source, "to_branch_id": source, **args}).status_code == 422
    assert stock_at(shop, source, product) == 5


def test_transfer_carries_batches_with_their_expiry(shop, two_branches):
    source, dest = two_branches
    product = shop.product("TRK", track=True)
    supplier = shop.supplier()
    po = shop.order(supplier, product, qty=10, po="PO-X")
    line = next(p for p in shop.get("/purchases").json() if p["id"] == po["id"])["items"][0]["id"]
    shop.post(f"/purchases/{po['id']}/receive", {"received_at": iso(), "items": [
        {"purchase_order_item_id": line, "quantity": "4", "batch_no": "NEAR", "expiry_date": (TODAY + timedelta(days=20)).isoformat()},
        {"purchase_order_item_id": line, "quantity": "6", "batch_no": "FAR", "expiry_date": (TODAY + timedelta(days=300)).isoformat()}]})
    shop.post("/inventory/transfer", {"from_branch_id": source, "to_branch_id": dest, "product_id": product["id"], "quantity": "5"})
    at_dest = {b["batch_no"]: Decimal(b["quantity"]) for b in shop.get("/inventory/batches", branch_id=dest).json()}
    at_source = {b["batch_no"]: Decimal(b["quantity"]) for b in shop.get("/inventory/batches", branch_id=source).json()}
    assert at_dest == {"NEAR": 4, "FAR": 1} and at_source == {"FAR": 5}   # earliest expiry travelled first
    dest_expiry = {b["batch_no"]: b["expiry_date"] for b in shop.get("/inventory/batches", branch_id=dest).json()}
    assert dest_expiry["NEAR"] == (TODAY + timedelta(days=20)).isoformat()


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("stock_keeper", True),
                                          ("cashier", False), ("viewer", False), ("accountant", False)])
def test_who_may_transfer_stock(shop, client_for, two_branches, role, allowed):
    source, dest = two_branches
    product = shop.product(stock=5)
    client, headers = client_for(role)
    response = client.post("/api/app/inventory/transfer", headers=headers, json={
        "from_branch_id": source, "to_branch_id": dest, "product_id": product["id"], "quantity": "1"})
    assert (response.status_code == 200) == allowed


# ── sales search, honest profit ──────────────────────────────────────────────

def test_sales_can_be_searched_by_invoice_customer_and_date(shop):
    product = shop.product(stock=30)
    customer = shop.customer()
    shop.sell(product, 1, customer=customer)
    shop.sell(product, 1)
    assert len(shop.get("/sales").json()) == 2
    assert len(shop.get("/sales", customer_id=customer["id"]).json()) == 1
    assert [s["invoice_number"] for s in shop.get("/sales", q="INV-2").json()] == ["INV-2"]
    assert len(shop.get("/sales", date_from=TODAY.isoformat(), date_to=TODAY.isoformat()).json()) == 2
    old = (TODAY - timedelta(days=3)).isoformat()
    assert shop.get("/sales", date_to=old).json() == []


def test_profit_is_reported_on_known_costs_only(shop):
    costed = shop.product("COSTED", price="100", cost="60")
    uncosted = shop.product("NOCOST", price="100", cost="0")
    shop.sell(costed, 1)
    shop.sell(uncosted, 1)
    dashboard = shop.get("/dashboard").json()
    assert dashboard["gross_profit_known"] == 40.0          # only the line whose cost is known
    assert dashboard["cost_coverage"] == pytest.approx(0.5)
    assert dashboard["gross_profit_before_expenses"] == 140.0   # the old figure counts the uncosted sale as pure profit
