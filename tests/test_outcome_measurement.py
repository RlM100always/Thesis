"""Layer 10, measured from the ledger instead of typed in by hand.

`api/outcome_measurement.py` only works for a live-sourced recommendation
(model_version starting "live@"), since only those name a real product/
branch/customer in this tenant's own schema. These tests build Recommendation
rows directly (the engine's own persistence is already covered by
test_bsmart_live.py) so the measurement math itself can be tested against
precisely-dated ledger fixtures.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from api.domain_models import Recommendation

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers, world, engine):
        self.c, self.h, self.w, self.engine, self.n = client, headers, world, engine, 0

    def post(self, path, body, status=200):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, status=200):
        r = self.c.get(f"/api/app{path}", headers=self.h)
        assert r.status_code == status, r.text
        return r.json()

    def product(self, sku, reorder_level="0", track_expiry=False):
        return self.post("/products", {"sku": sku, "name": sku, "selling_price": "100", "cost_price": "60",
                                        "reorder_level": reorder_level, "track_expiry": track_expiry})

    def stock(self, product_id, qty):
        self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": product_id, "quantity_delta": str(qty), "reason": "opening"})

    def customer(self, code, consent=True):
        return self.post("/customers", {"code": code, "display_name": code, "marketing_consent": consent})

    def sale(self, product_id, qty, sold_at, customer_id=None):
        self.n += 1
        self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "sold_at": sold_at.isoformat(),
            "customer_id": customer_id, "items": [{"product_id": product_id, "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(Decimal(qty) * Decimal("100"))}],
        })

    def branch_name(self):
        return self.get("/branches")[0]["name"]

    def make_recommendation(self, action_type, sku=None, division=None, customer_id=None, quantity=None, live=True):
        with Session(self.engine) as db:
            reco = Recommendation(
                organization_id=self.w["org_a"], run_id="test-run", cutoff_date=NOW.date().isoformat(),
                action_type=action_type, target_sku=sku, target_customer_id=customer_id, division=division,
                quantity=quantity, benefit_bdt=100, action_cost_bdt=10, risk_bdt=5, utility_bdt=85,
                feasible=True, model_version=f"live@{NOW.date().isoformat()}" if live else f"13_bsmart_recommendation_engine@{NOW.date().isoformat()}",
            )
            db.add(reco)
            db.commit()
            return reco.id

    def decide(self, reco_id):
        self.post(f"/bsmart/recommendations/{reco_id}/decision", {"decision": "accept"})
        row = next(r for r in self.get("/bsmart/recommendations")["recommendations"] if r["id"] == reco_id)
        return datetime.fromisoformat(row["decided_at"])

    def measure(self, reco_id, window_days=30, status=200):
        r = self.c.post(f"/api/app/bsmart/recommendations/{reco_id}/measure", headers=self.h,
                         json={"observation_window_days": window_days})
        assert r.status_code == status, r.text
        return r.json()


@pytest.fixture()
def shop(client_for, world, engine):
    client, headers = client_for("owner")
    return Shop(client, headers, world, engine)


def test_measuring_a_research_imported_recommendation_is_refused(shop):
    reco_id = shop.make_recommendation("reorder", sku="P-1", division="Dhaka", quantity=10, live=False)
    shop.decide(reco_id)
    body = shop.measure(reco_id, status=422)
    assert "নিজের ডেটা" in body["detail"]


def test_measuring_before_any_decision_is_refused(shop):
    product = shop.product("OM-1")
    reco_id = shop.make_recommendation("reorder", sku=product["sku"], division=shop.branch_name(), quantity=10)
    body = shop.measure(reco_id, status=422)
    assert "সিদ্ধান্ত" in body["detail"]


def test_reorder_outcome_measures_stockout_days_and_sales_from_the_ledger(shop):
    product = shop.product("OM-2")
    shop.stock(product["id"], 1000)
    reco_id = shop.make_recommendation("reorder", sku=product["sku"], division=shop.branch_name(), quantity=50)
    decided_at = shop.decide(reco_id)

    # Before the decision: sell down to zero 10 days prior, so that day (and
    # every day after it, until the decision) reads as a stockout.
    shop.sale(product["id"], 1000, decided_at - timedelta(days=10))
    # Restock, then sell some more after the decision.
    shop.stock(product["id"], 500)
    shop.sale(product["id"], 30, decided_at + timedelta(days=2))

    result = shop.measure(reco_id, window_days=30)
    measured = result["measured"]
    assert measured["stockout_days_before"] >= 9   # ~10 days of the 30-day before-window at zero stock
    assert measured["stockout_days_after"] == 0     # restocked before running out again
    assert measured["realised_quantity"] == 30
    assert measured["predicted_quantity"] == 50

    recos = shop.get("/bsmart/recommendations")["recommendations"]
    row = next(r for r in recos if r["id"] == reco_id)
    assert row["outcome_logged"] is True
    assert row["outcome_measured_by"] == "ledger_auto"


def test_expiry_outcome_measures_real_wasted_stock_value(shop):
    product = shop.product("OM-3", track_expiry=True)
    reco_id = shop.make_recommendation("expiry", sku=product["sku"], division=shop.branch_name())
    decided_at = shop.decide(reco_id)

    supplier = shop.post("/suppliers", {"code": "SUP-OM", "name": "Test Supplier"})
    po = shop.post("/purchases", {
        "branch_id": shop.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-OM-3",
        "ordered_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "20", "unit_cost": "60"}],
    })
    detail = next(p for p in shop.get("/purchases") if p["id"] == po["id"])
    shop.post(f"/purchases/{po['id']}/receive", {
        "received_at": NOW.isoformat(),
        "items": [{"purchase_order_item_id": detail["items"][0]["id"], "quantity": "20",
                   "batch_no": "B-OM-3", "expiry_date": (decided_at + timedelta(days=15)).date().isoformat()}],
    })
    # The 20 units sit unsold, with an expiry date inside the 30-day window.
    result = shop.measure(reco_id, window_days=30)
    assert Decimal(str(result["measured"]["expired_value_bdt"])) == Decimal("1200.00")   # 20 units * 60 unit cost


def test_retention_outcome_measures_a_real_customer_purchase(shop):
    product = shop.product("OM-4")
    shop.stock(product["id"], 100)
    customer = shop.customer("OM-CUST")
    reco_id = shop.make_recommendation("retention", customer_id=customer["id"])
    decided_at = shop.decide(reco_id)
    shop.sale(product["id"], 1, decided_at + timedelta(days=5), customer_id=customer["id"])

    result = shop.measure(reco_id, window_days=30)
    assert result["measured"]["customer_responded"] is True


def test_retention_outcome_is_false_when_the_customer_never_returns(shop):
    customer = shop.customer("OM-CUST-2")
    reco_id = shop.make_recommendation("retention", customer_id=customer["id"])
    shop.decide(reco_id)
    result = shop.measure(reco_id, window_days=30)
    assert result["measured"]["customer_responded"] is False


def test_measuring_a_deleted_or_unknown_sku_is_refused_not_guessed(shop):
    reco_id = shop.make_recommendation("reorder", sku="NO-SUCH-SKU", division=shop.branch_name(), quantity=10)
    shop.decide(reco_id)
    body = shop.measure(reco_id, status=422)
    assert "খুঁজে পাওয়া যায়নি" in body["detail"]
