"""A big discount at the till needs a manager's own credentials, typed inline —
a sale cannot sit in an async approval queue the way an expense can."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.domain_models import User
from api.security import hash_password

NOW = datetime.now(timezone.utc)
PASSWORD = "correct horse battery"


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body, status=200):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, r.text
        return r.json()

    def sell(self, client, headers, product, qty, discount, status=200, paid=None, **extra):
        self.n += 1
        total = Decimal("100") * qty - Decimal(discount)
        paid = total if paid is None else paid
        r = client.post("/api/app/sales", headers=headers, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "sold_at": NOW.isoformat(),
            "items": [{"product_id": product["id"], "quantity": str(qty), "discount_amount": str(discount)}],
            "payments": [{"method": "cash", "amount": str(paid)}], **extra})
        assert r.status_code == status, r.text
        return r


@pytest.fixture()
def setup(client_for, world, engine):
    """Owner creates and stocks a ৳100-priced product every test can discount.

    The `world` fixture's users have no password (client_for bypasses login
    entirely) — an override needs a real one, so this gives the manager and
    cashier one to type inline.
    """
    with Session(engine) as db:
        for role in ("manager", "cashier"):
            user = db.scalar(select(User).where(User.email == f"{role}@a.example"))
            user.password_hash = hash_password(PASSWORD)
        db.commit()
    owner, oheaders = client_for("owner")
    shop = Shop(owner, oheaders, world)

    def make(sku):
        product = shop.post("/products", {"sku": sku, "name": sku, "selling_price": "100", "cost_price": "60"})
        shop.post("/inventory/adjust", {"branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "100", "reason": "open"})
        return product
    return shop, make


def test_a_discount_under_the_threshold_needs_no_override(setup, client_for, world):
    shop, make = setup
    cashier, cheaders = client_for("cashier")
    product = make("D-1")
    # 5% off a ৳1000 subtotal, well under the default 10% rule: proceeds past the discount
    # gate (the eventual 422 is only because an underpayment leaves a due with no customer).
    shop.sell(cashier, cheaders, product, 10, "50", status=422, paid="0.01")


def test_a_discount_at_the_threshold_is_blocked_without_a_qualifying_override(setup, client_for, world):
    shop, make = setup
    cashier, cheaders = client_for("cashier")
    product = make("D-2")
    r = shop.sell(cashier, cheaders, product, 10, "150", status=403)   # 15% discount
    body = r.json()["detail"]
    assert body["code"] == "discount_override_required" and body["threshold"] == 10.0
    assert abs(body["discount_pct"] - 15.0) < 0.01 and body["needs_role"] == "manager"


def test_a_valid_manager_override_lets_the_discount_through(setup, client_for, world):
    shop, make = setup
    cashier, cheaders = client_for("cashier")
    product = make("D-3")
    r = shop.sell(cashier, cheaders, product, 10, "150", status=200,
                  override_email="manager@a.example", override_password=PASSWORD)
    assert Decimal(r.json()["total"]) == 850   # 1000 - 150 discount


def test_a_wrong_password_is_refused(setup, client_for, world):
    shop, make = setup
    cashier, cheaders = client_for("cashier")
    product = make("D-4")
    r = shop.sell(cashier, cheaders, product, 10, "150", status=403,
                  override_email="manager@a.example", override_password="wrong password entirely")
    assert r.json()["detail"]["code"] == "discount_override_required"


def test_correct_credentials_for_a_role_that_does_not_outrank_the_rule_still_fail(setup, client_for, world):
    shop, make = setup
    cashier, cheaders = client_for("cashier")
    product = make("D-5")
    # Another cashier's own real password — correct credentials, wrong rank.
    r = shop.sell(cashier, cheaders, product, 10, "150", status=403,
                  override_email="cashier@a.example", override_password=PASSWORD)
    assert r.json()["detail"]["code"] == "discount_override_required"


def test_the_override_is_written_to_the_audit_trail(setup, client_for, world):
    shop, make = setup
    cashier, cheaders = client_for("cashier")
    product = make("D-6")
    shop.sell(cashier, cheaders, product, 10, "150", status=200,
              override_email="manager@a.example", override_password=PASSWORD)
    event = next(e for e in shop.get("/audit")["items"] if e["action"] == "sale.discount_override")
    assert event["details"]["approver_email"] == "manager@a.example"


def test_the_owner_may_apply_the_same_discount_without_any_override(setup, world):
    shop, make = setup
    product = make("D-7")
    r = shop.sell(shop.c, shop.h, product, 10, "150", status=200)   # owner outranks the rule itself
    assert Decimal(r.json()["total"]) == 850


def test_the_owner_can_relax_the_threshold_or_turn_the_rule_off(setup, client_for, world):
    shop, make = setup
    shop.c.patch("/api/app/approvals/rules/discount_percent", headers=shop.h, json={"threshold": "50"})
    cashier, cheaders = client_for("cashier")
    product = make("D-8")
    shop.sell(cashier, cheaders, product, 10, "150", status=200)   # 15% now under the raised 50% threshold

    shop.c.patch("/api/app/approvals/rules/discount_percent", headers=shop.h, json={"active": False})
    product2 = make("D-9")
    shop.sell(cashier, cheaders, product2, 10, "900", status=200)  # 90% off, but the rule is off entirely
