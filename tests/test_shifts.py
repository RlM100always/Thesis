"""A cashier's own drawer accountability window -- open with a float, every
cash sale/refund while it is open belongs to it, close with a count and a
variance. Distinct from the branch's once-a-day ``cash/close``."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.domain_models import Payment, User
from api.security import hash_password

NOW = datetime.now(timezone.utc)
PASSWORD = "correct horse battery"


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body, status=200):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json() if status < 300 else r

    def get(self, path, status=200, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == status, r.text
        return r.json()

    def sell(self, product, qty=1, paid=None, method="cash"):
        self.n += 1
        total = Decimal(product["selling_price"]) * qty
        paid = total if paid is None else paid
        return self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}",
            "sold_at": datetime.now(timezone.utc).isoformat(),
            "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": method, "amount": str(paid)}],
        })


@pytest.fixture()
def setup(client_for, world, engine):
    """The manager gets a real password (client_for bypasses login entirely),
    so a shortage-override test can type it inline."""
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "manager@a.example"))
        user.password_hash = hash_password(PASSWORD)
        db.commit()
    owner, oheaders = client_for("owner")
    owner_shop = Shop(owner, oheaders, world)
    product = owner_shop.post("/products", {"sku": "SHF-1", "name": "Shift Item", "selling_price": "100", "cost_price": "60"})
    owner_shop.post("/inventory/adjust", {"branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "100", "reason": "open"})
    cashier, cheaders = client_for("cashier")
    shop = Shop(cashier, cheaders, world)
    return shop, product


def test_opening_a_shift_and_reading_it_back_as_current(setup, world):
    shop, _ = setup
    opened = shop.post("/shifts/open", {"branch_id": world["branch_a"], "drawer_label": "Counter-1", "opening_cash": "5000"})
    assert opened["status"] == "open" and Decimal(opened["opening_cash"]) == 5000
    current = shop.get("/shifts/current", branch_id=world["branch_a"])
    assert current["id"] == opened["id"] and Decimal(current["expected_cash"]) == 5000


def test_opening_a_second_shift_on_the_same_branch_is_refused(setup, world):
    shop, _ = setup
    shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "5000"})
    shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "1000"}, status=409)


def test_a_sale_made_during_an_open_shift_is_attributed_to_it(setup, world, engine):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "0"})
    sale = shop.sell(product, 2)  # ৳200 cash
    with Session(engine) as db:
        payment = db.scalar(select(Payment).where(Payment.order_id == sale["id"]))
        assert payment.shift_id == shift["id"]
    current = shop.get("/shifts/current", branch_id=world["branch_a"])
    assert Decimal(current["expected_cash"]) == 200


def test_cash_drop_reduces_expected_cash_and_add_restores_it(setup, world):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "1000"})
    shop.sell(product, 1)  # +100
    shop.post(f"/shifts/{shift['id']}/movements", {"direction": "drop", "amount": "500", "reason": "To safe"})
    current = shop.get("/shifts/current", branch_id=world["branch_a"])
    assert Decimal(current["expected_cash"]) == 1000 + 100 - 500  # = 600
    shop.post(f"/shifts/{shift['id']}/movements", {"direction": "add", "amount": "200", "reason": "Change top-up"})
    current = shop.get("/shifts/current", branch_id=world["branch_a"])
    assert Decimal(current["expected_cash"]) == 600 + 200  # = 800


def test_closing_with_an_exact_count_needs_no_note(setup, world):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "1000"})
    shop.sell(product, 1)  # +100
    closed = shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "1100"})
    assert closed["status"] == "closed" and Decimal(closed["variance"]) == 0


def test_closing_with_a_mismatch_requires_a_note(setup, world):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "1000"})
    shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "900"}, status=422)
    closed = shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "900", "note": "Gave change short"})
    assert Decimal(closed["variance"]) == -100


def test_a_small_shortage_closes_without_a_manager_override(setup, world):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "1000"})
    # ৳100 short, well under the ৳500 default cash_shortage threshold.
    closed = shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "900", "note": "Small shortage"})
    assert Decimal(closed["variance"]) == -100


def test_a_large_shortage_needs_a_manager_override(setup, world):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "1000"})
    r = shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "400", "note": "Big shortage"}, status=403)
    body = r.json()["detail"]
    assert body["code"] == "cash_shortage_override_required" and body["needs_role"] == "manager"
    ok = shop.post(f"/shifts/{shift['id']}/close", {
        "counted_cash": "400", "note": "Big shortage",
        "override_email": "manager@a.example", "override_password": PASSWORD,
    })
    assert ok["status"] == "closed" and Decimal(ok["variance"]) == -600


def test_a_closed_shift_cannot_be_closed_again_or_take_movements(setup, world):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "0"})
    shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "0"})
    shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "0"}, status=409)
    shop.post(f"/shifts/{shift['id']}/movements", {"direction": "add", "amount": "10", "reason": "late"}, status=409)


def test_shift_history_lists_closed_shifts_for_a_manager(setup, world, client_for):
    shop, product = setup
    shift = shop.post("/shifts/open", {"branch_id": world["branch_a"], "opening_cash": "0"})
    shop.post(f"/shifts/{shift['id']}/close", {"counted_cash": "0"})
    manager, mheaders = client_for("manager")
    rows = manager.get("/api/app/shifts/history", headers=mheaders, params={"branch_id": world["branch_a"]}).json()
    assert len(rows) == 1 and rows[0]["cashier_name"] == "cashier A" and rows[0]["status"] == "closed"
