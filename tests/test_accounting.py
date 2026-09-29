"""The accounting engine: journal posting from real events, trial balance, P&L.

The one invariant every test here leans on: **the trial balance always balances**
(total debits == total credits across every account), because `post_journal`
refuses anything that does not. If that ever stops being true, the books are
wrong somewhere in the wiring, not just in a report.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from api.accounting import Line, post_journal

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

    def sale(self, product, qty, customer=None, paid=None, method="cash", tax="0", price=None):
        self.n += 1
        item = {"product_id": product["id"], "quantity": str(qty)}
        if price is not None:
            item["unit_price"] = str(price)
        unit = Decimal(price if price is not None else product["selling_price"])
        paid = unit * qty if paid is None else paid
        return self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "customer_id": customer["id"] if customer else None,
            "sold_at": NOW.isoformat(), "tax_amount": tax, "items": [item],
            "payments": [{"method": method, "amount": str(paid)}] if paid else []})

    def trial_balance(self):
        return self.get("/accounting/trial-balance")

    def accounts(self):
        return {a["code"]: a for a in self.get("/accounting/accounts")}

    def pnl(self, days_ago=1):
        return self.get("/accounting/profit-and-loss",
                         date_from=(date.today() - timedelta(days=days_ago)).isoformat(), date_to=(date.today() + timedelta(days=1)).isoformat())

    def balance_sheet(self):
        return self.get("/accounting/balance-sheet")


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


# ── the chart of accounts exists from day one ────────────────────────────────

def test_every_organization_has_a_seeded_chart_of_accounts(shop):
    accounts = shop.accounts()
    for code in ("1000", "1100", "1200", "2000", "4000", "5000"):
        assert code in accounts and accounts[code]["is_system"] is True


# ── post_journal itself ──────────────────────────────────────────────────────

def test_post_journal_refuses_an_unbalanced_entry(client_for, world, engine):
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        with pytest.raises(ValueError, match="does not balance"):
            post_journal(db, world["org_a"], world["branch_a"], NOW, "test", "x",
                         [Line("1000", Decimal("10"), Decimal("0")), Line("4000", Decimal("0"), Decimal("9"))])


def test_post_journal_refuses_an_unknown_account_code(client_for, world, engine):
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        with pytest.raises(ValueError, match="Unknown account"):
            post_journal(db, world["org_a"], world["branch_a"], NOW, "test", "x",
                         [Line("9999", Decimal("10"), Decimal("0")), Line("1000", Decimal("0"), Decimal("10"))])


# ── a sale posts revenue, cash/receivable, and cost of goods ─────────────────

def test_a_fully_paid_cash_sale_posts_revenue_and_cogs(shop):
    product = shop.product("A-1", price="10", cost="6")
    shop.sale(product, 5)                                     # ৳50 cash, cost ৳30
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1000"]["balance"]) == 50                # Cash up
    assert Decimal(tb["4000"]["balance"]) == 50                # Sales Revenue up
    assert Decimal(tb["5000"]["balance"]) == 30                # COGS up
    assert Decimal(tb["1200"]["balance"]) == -30               # Inventory down by the same cost


def test_a_credit_sale_posts_to_accounts_receivable_instead_of_cash(shop):
    product = shop.product("A-2", price="10", cost="6")
    customer = shop.customer("C-1")
    shop.sale(product, 4, customer=customer, paid=0)          # ৳40 owed
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1100"]["balance"]) == 40
    assert Decimal(tb["1000"]["balance"]) == 0


def test_a_part_paid_sale_splits_between_cash_and_receivable(shop):
    product = shop.product("A-3", price="10", cost="6")
    customer = shop.customer("C-2")
    shop.sale(product, 10, customer=customer, paid=Decimal("60"))   # 100 total, 60 cash, 40 due
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1000"]["balance"]) == 60
    assert Decimal(tb["1100"]["balance"]) == 40
    assert Decimal(tb["4000"]["balance"]) == 100


def test_a_mobile_banking_sale_posts_to_the_mobile_banking_account_not_cash(shop):
    product = shop.product("A-4", price="10", cost="6")
    shop.sale(product, 3, method="bkash")
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1010"]["balance"]) == 30 and Decimal(tb["1000"]["balance"]) == 0


def test_tax_is_posted_to_vat_payable_separately_from_revenue(shop):
    product = shop.product("A-5", price="100", cost="60")
    shop.sale(product, 1, tax="15", paid=Decimal("115"))
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["4000"]["balance"]) == 100
    assert Decimal(tb["2100"]["balance"]) == 15
    assert Decimal(tb["1000"]["balance"]) == 115


def test_a_product_with_no_cost_price_posts_no_cogs_the_way_the_dashboard_already_treats_it(shop):
    product = shop.product("A-6", price="10", cost="0")
    shop.sale(product, 5)
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["5000"]["balance"]) == 0 and Decimal(tb["1200"]["balance"]) == 0


# ── returns and voids reverse the same accounts ──────────────────────────────

def test_a_restocked_return_reverses_revenue_and_cogs(shop):
    product = shop.product("B-1", price="10", cost="6")
    sale = shop.sale(product, 10)                              # 100 revenue, 60 cogs
    line = shop.get("/sales")[0]["items"][0]
    shop.post(f"/sales/{sale['id']}/returns", {
        "return_number": "R-1", "reason": "damaged", "returned_at": NOW.isoformat(), "refund_method": "cash",
        "items": [{"sales_order_item_id": line["id"], "quantity": "4", "restock": True}]})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    # 4100 is contra-revenue: its normal side is a debit, so on a credit-normal
    # revenue-type report it shows as the negative that nets against 4000.
    assert Decimal(tb["4100"]["balance"]) == -40
    assert Decimal(tb["4000"]["balance"]) + Decimal(tb["4100"]["balance"]) == 60   # net revenue after the return
    assert Decimal(tb["1200"]["balance"]) == -60 + 24          # cogs for 6 units minus the 4 restocked
    assert Decimal(tb["1000"]["balance"]) == 100 - 40           # cash refunded


def test_voiding_a_sale_reverses_everything_it_posted(shop):
    product = shop.product("B-2", price="10", cost="6")
    sale = shop.sale(product, 5)
    before = shop.trial_balance()["total_debit"]
    shop.post(f"/sales/{sale['id']}/void", {"reason": "test"})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    # Fully reversed: cash, cost of goods and inventory are back to zero. Revenue is
    # untouched (4000 keeps its original credit); the reversal lands in the contra
    # account 4100 instead, so the *net* of the two is what actually zeroes out.
    for code in ("1000", "5000", "1200"):
        assert Decimal(tb[code]["balance"]) == 0
    assert Decimal(tb["4000"]["balance"]) + Decimal(tb["4100"]["balance"]) == 0
    assert shop.trial_balance()["balanced"] is True
    assert shop.trial_balance()["total_debit"] > before          # the reversal itself still posted (debits/credits both grew)


# ── purchasing, expenses, settlements ────────────────────────────────────────

def test_receiving_a_purchase_posts_inventory_and_payable(shop):
    product = shop.product("C-1", stock=0, cost="6")
    supplier = shop.post("/suppliers", {"code": "S1", "name": "Sup"})
    order = shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-1",
                                     "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": "6"}]})
    line = order["items"][0]["id"] if "items" in order else shop.get("/purchases")[0]["items"][0]["id"]
    shop.post(f"/purchases/{order['id']}/receive", {"received_at": NOW.isoformat(),
                                                     "items": [{"purchase_order_item_id": line, "quantity": "10"}]})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1200"]["balance"]) == 60
    assert Decimal(tb["2000"]["balance"]) == 60


def test_free_goods_receiving_posts_nothing_since_nothing_is_owed(shop):
    product = shop.product("C-2", stock=0, cost="0")
    supplier = shop.post("/suppliers", {"code": "S2", "name": "Sup2"})
    order = shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-2",
                                     "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": "0"}]})
    line = shop.get("/purchases")[0]["items"][0]["id"]
    shop.post(f"/purchases/{order['id']}/receive", {"received_at": NOW.isoformat(),
                                                     "items": [{"purchase_order_item_id": line, "quantity": "10"}]})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1200"]["balance"]) == 0 and Decimal(tb["2000"]["balance"]) == 0


def test_an_expense_debits_operating_expenses_and_credits_the_payment_account(shop):
    shop.post("/expenses", {"category": "ভাড়া", "amount": "500", "payment_method": "cash", "incurred_at": NOW.isoformat()})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["5900"]["balance"]) == 500 and Decimal(tb["1000"]["balance"]) == -500


def test_paying_a_supplier_clears_payable_and_reduces_the_payment_account(shop):
    product = shop.product("C-3", stock=0, cost="10")
    supplier = shop.post("/suppliers", {"code": "S3", "name": "Sup3"})
    order = shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-3",
                                     "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": "10"}]})
    line = shop.get("/purchases")[0]["items"][0]["id"]
    shop.post(f"/purchases/{order['id']}/receive", {"received_at": NOW.isoformat(),
                                                     "items": [{"purchase_order_item_id": line, "quantity": "10"}]})
    shop.post(f"/suppliers/{supplier['id']}/payments", {"amount": "60", "payment_method": "bank", "occurred_at": NOW.isoformat()})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["2000"]["balance"]) == 40 and Decimal(tb["1020"]["balance"]) == -60


def test_collecting_a_baki_clears_receivable_and_increases_the_payment_account(shop):
    product = shop.product("C-4", price="10", cost="6")
    customer = shop.customer("C-3")
    shop.sale(product, 10, customer=customer, paid=0)
    shop.post(f"/customers/{customer['id']}/payments", {"amount": "70", "payment_method": "nagad", "occurred_at": NOW.isoformat()})
    tb = {r["code"]: r for r in shop.trial_balance()["accounts"]}
    assert Decimal(tb["1100"]["balance"]) == 30 and Decimal(tb["1010"]["balance"]) == 70


# ── the trial balance always balances, whatever happened ────────────────────

def test_the_trial_balance_always_balances_after_a_full_day(shop):
    product = shop.product("D-1", price="20", cost="12")
    customer = shop.customer("D-C1")
    supplier = shop.post("/suppliers", {"code": "SD", "name": "SupD"})
    shop.sale(product, 3)
    shop.sale(product, 2, customer=customer, paid=Decimal("10"))
    shop.post("/expenses", {"category": "বিদ্যুৎ", "amount": "200", "payment_method": "cash", "incurred_at": NOW.isoformat()})
    order = shop.post("/purchases", {"branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-D",
                                     "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "5", "unit_cost": "12"}]})
    line = shop.get("/purchases")[0]["items"][0]["id"]
    shop.post(f"/purchases/{order['id']}/receive", {"received_at": NOW.isoformat(), "items": [{"purchase_order_item_id": line, "quantity": "5"}]})
    shop.post(f"/customers/{customer['id']}/payments", {"amount": "10", "payment_method": "cash", "occurred_at": NOW.isoformat()})
    result = shop.trial_balance()
    assert result["balanced"] is True
    assert result["total_debit"] == result["total_credit"]


def test_the_balance_sheet_balances_too(shop):
    product = shop.product("D-2", price="20", cost="12")
    shop.sale(product, 3)
    shop.post("/expenses", {"category": "ভাড়া", "amount": "50", "payment_method": "cash", "incurred_at": NOW.isoformat()})
    sheet = shop.balance_sheet()
    assert sheet["balances"] is True


# ── profit & loss reads straight off the journal ─────────────────────────────

def test_profit_and_loss_matches_hand_arithmetic(shop):
    product = shop.product("E-1", price="20", cost="12")
    shop.sale(product, 10)                                    # revenue 200, cogs 120
    shop.post("/expenses", {"category": "ভাড়া", "amount": "30", "payment_method": "cash", "incurred_at": NOW.isoformat()})
    report = shop.pnl()
    assert Decimal(report["revenue"]) == 200 and Decimal(report["cogs"]) == 120
    assert Decimal(report["gross_profit"]) == 80
    assert Decimal(report["operating_expenses"]) == 30
    assert Decimal(report["net_profit"]) == 50


def test_profit_and_loss_only_counts_its_own_date_range(shop):
    product = shop.product("E-2", price="20", cost="12")
    shop.sale(product, 1)
    old_report = shop.get("/accounting/profit-and-loss",
                          date_from=(date.today() - timedelta(days=400)).isoformat(),
                          date_to=(date.today() - timedelta(days=390)).isoformat())
    assert Decimal(old_report["revenue"]) == 0


# ── permissions and tenant isolation ─────────────────────────────────────────

@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("viewer", True), ("cashier", False), ("stock_keeper", False)])
def test_who_may_read_the_books(client_for, role, allowed):
    client, headers = client_for(role)
    for path in ("/accounting/accounts", "/accounting/trial-balance", "/accounting/journal"):
        assert (client.get(f"/api/app{path}", headers=headers).status_code == 200) == allowed, path


def test_another_business_never_sees_our_accounts_or_journal(shop, client_for):
    product = shop.product("F-1", price="10", cost="6")
    shop.sale(product, 5)
    other, other_headers = client_for("owner", org="org_b")
    other_tb = other.get("/api/app/accounting/trial-balance", headers=other_headers).json()
    assert all(Decimal(r["balance"]) == 0 for r in other_tb["accounts"])
    assert other.get("/api/app/accounting/journal", headers=other_headers).json() == []
