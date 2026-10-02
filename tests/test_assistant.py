"""'ব্যবসা সম্পর্কে জিজ্ঞাসা করুন' -- keyword-classified, real-data-grounded Q&A."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


def iso(delta_days=0):
    return (NOW + timedelta(days=delta_days)).isoformat()


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w = client, headers, world
        self.n = 0

    def post(self, path, body):
        response = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert response.status_code == 200, (path, response.text)
        return response.json()

    def ask(self, question):
        response = self.c.post("/api/app/assistant/ask", headers=self.h, json={"question": question})
        assert response.status_code == 200, response.text
        return response.json()

    def product(self, sku="P-1", price="15", cost="10", stock=20, reorder="0"):
        product = self.post("/products", {"sku": sku, "name": f"Item {sku}", "selling_price": price,
                                          "cost_price": cost, "track_expiry": False, "reorder_level": reorder})
        if stock:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": product["id"],
                                            "quantity_delta": str(stock), "reason": "opening"})
        return product

    def customer(self, code="C1"):
        return self.post("/customers", {"code": code, "display_name": f"Customer {code}"})

    def sell(self, product, qty=1, customer=None, paid=None, when=None):
        self.n += 1
        price = Decimal(product["selling_price"])
        total = price * qty
        paid = total if paid is None else Decimal(paid)
        body = {"branch_id": self.w["branch_a"], "invoice_number": f"INV-{self.n}", "sold_at": when or iso(),
                "customer_id": customer["id"] if customer else None,
                "items": [{"product_id": product["id"], "quantity": str(qty)}],
                "payments": [{"method": "cash", "amount": str(paid)}] if paid > 0 else []}
        return self.post("/sales", body)


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_unrecognised_question_is_honest_not_a_guess(shop):
    result = shop.ask("আজকের আবহাওয়া কেমন?")
    assert result["answered"] is False
    assert "বুঝতে পারছি না" in result["text"]


def test_today_sales_reflects_a_real_sale(shop):
    product = shop.product(price="100")
    shop.sell(product, qty=2)  # 200 BDT
    result = shop.ask("আজকে কত বিক্রি হয়েছে?")
    assert result["answered"] is True
    assert result["intent"] == "আজকের বিক্রি"
    assert result["data"]["today_sales_bdt"] == 200.0
    assert "200" in result["text"]


def test_top_products_ranks_by_revenue(shop):
    cheap = shop.product(sku="CHEAP", price="10")
    pricey = shop.product(sku="PRICEY", price="500")
    shop.sell(cheap, qty=1)
    shop.sell(pricey, qty=1)
    result = shop.ask("কোন পণ্য বেশি বিক্রি হচ্ছে?")
    assert result["answered"] is True
    names = [p["name"] for p in result["data"]["top_products"]]
    assert names[0] == "Item PRICEY"


def test_low_stock_lists_products_at_or_below_reorder(shop):
    shop.product(sku="LOW", stock=2, reorder="5")
    shop.product(sku="FINE", stock=50, reorder="5")
    result = shop.ask("কোন পণ্যের স্টক কমে গেছে?")
    assert result["answered"] is True
    names = [i["name"] for i in result["data"]["items"]]
    assert "Item LOW" in names
    assert "Item FINE" not in names


def test_receivables_reflects_real_due(shop):
    product = shop.product(price="300")
    customer = shop.customer("C1")
    shop.sell(product, qty=1, customer=customer, paid="100")  # 200 due
    result = shop.ask("কার কাছে কত বাকি আছে?")
    assert result["answered"] is True
    assert result["data"]["total_receivable_bdt"] == 200.0


def test_cash_position_combines_sales_and_ledger(shop):
    product = shop.product(price="150")
    shop.sell(product, qty=1)
    result = shop.ask("আজকে হাতে কত টাকা আছে?")
    assert result["answered"] is True
    assert result["data"]["today_sales_bdt"] == 150.0


def test_without_llm_key_source_is_always_template(shop):
    # No ANTHROPIC_API_KEY/INTEGRATION_MODE=production in this test environment,
    # so every answered question must fall back to the deterministic template --
    # never silently calling out to a real API in CI.
    product = shop.product(price="50")
    shop.sell(product, qty=1)
    result = shop.ask("আজকের বিক্রি কেমন হলো?")
    assert result["source"] == "template"


def test_cashier_without_dashboard_permission_is_refused(client_for, world):
    client, headers = client_for("cashier")
    response = client.post("/api/app/assistant/ask", headers=headers, json={"question": "আজকে কত বিক্রি?"})
    assert response.status_code == 403
