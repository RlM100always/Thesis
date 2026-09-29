"""A large cash refund needs a manager's own credentials, the same synchronous
override pattern the discount gate uses — a return counter cannot wait for an
async approval queue either."""

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

    def product(self, sku, price="100", cost="60"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost})
        self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": "100", "reason": "open"})
        return p

    def sale(self, product, qty):
        self.n += 1
        sale = self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "sold_at": NOW.isoformat(),
            "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(Decimal(product["selling_price"]) * qty)}]})
        line = self.get("/sales")[0]["items"][0]
        return sale, line


@pytest.fixture()
def setup(client_for, world, engine):
    """A manager with a real password, a fully-paid cash sale ready to be returned."""
    with Session(engine) as db:
        for role in ("manager",):
            user = db.scalar(select(User).where(User.email == f"{role}@a.example"))
            user.password_hash = hash_password(PASSWORD)
        db.commit()
    owner, oheaders = client_for("owner")
    return Shop(owner, oheaders, world)


def return_body(line, qty, override=None):
    body = {"return_number": f"R-{line['id'][:8]}", "reason": "damaged", "returned_at": NOW.isoformat(),
            "refund_method": "cash", "items": [{"sales_order_item_id": line["id"], "quantity": str(qty), "restock": False}]}
    if override:
        body.update(override)
    return body


def test_a_refund_under_the_threshold_needs_no_override(setup, client_for):
    shop = setup
    cashier, cheaders = client_for("cashier")
    product = shop.product("R-1")
    sale, line = shop.sale(product, 5)                                # ৳500 refundable, under ৳1000
    r = cashier.post(f"/api/app/sales/{sale['id']}/returns", headers=cheaders, json=return_body(line, 5))
    assert r.status_code == 200 and Decimal(r.json()["refund_amount"]) == 500


def test_a_refund_at_the_threshold_is_blocked_without_a_qualifying_override(setup, client_for):
    shop = setup
    cashier, cheaders = client_for("cashier")
    product = shop.product("R-2")
    sale, line = shop.sale(product, 15)                               # ৳1500 refundable
    r = cashier.post(f"/api/app/sales/{sale['id']}/returns", headers=cheaders, json=return_body(line, 15))
    assert r.status_code == 403
    body = r.json()["detail"]
    assert body["code"] == "refund_override_required" and body["threshold"] == 1000.0 and body["refund_amount"] == 1500.0


def test_a_valid_manager_override_lets_the_refund_through(setup, client_for):
    shop = setup
    cashier, cheaders = client_for("cashier")
    product = shop.product("R-3")
    sale, line = shop.sale(product, 15)
    r = cashier.post(f"/api/app/sales/{sale['id']}/returns", headers=cheaders,
                     json=return_body(line, 15, {"override_email": "manager@a.example", "override_password": PASSWORD}))
    assert r.status_code == 200 and Decimal(r.json()["refund_amount"]) == 1500


def test_a_wrong_password_is_refused(setup, client_for):
    shop = setup
    cashier, cheaders = client_for("cashier")
    product = shop.product("R-4")
    sale, line = shop.sale(product, 15)
    r = cashier.post(f"/api/app/sales/{sale['id']}/returns", headers=cheaders,
                     json=return_body(line, 15, {"override_email": "manager@a.example", "override_password": "wrong"}))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "refund_override_required"


def test_the_override_is_written_to_the_audit_trail(setup, client_for):
    shop = setup
    cashier, cheaders = client_for("cashier")
    product = shop.product("R-5")
    sale, line = shop.sale(product, 15)
    cashier.post(f"/api/app/sales/{sale['id']}/returns", headers=cheaders,
                json=return_body(line, 15, {"override_email": "manager@a.example", "override_password": PASSWORD}))
    event = next(e for e in shop.get("/audit")["items"] if e["action"] == "refund.override")
    assert event["details"]["approver_email"] == "manager@a.example" and Decimal(event["details"]["refund_amount"]) == 1500


def test_the_owner_needs_no_override_for_the_same_refund(setup):
    shop = setup
    product = shop.product("R-6")
    sale, line = shop.sale(product, 15)
    r = shop.c.post(f"/api/app/sales/{sale['id']}/returns", headers=shop.h, json=return_body(line, 15))
    assert r.status_code == 200


def test_the_owner_can_relax_the_refund_threshold(setup, client_for):
    shop = setup
    r = shop.c.patch("/api/app/approvals/rules/refund_amount", headers=shop.h, json={"threshold": "5000"})
    assert r.status_code == 200
    cashier, cheaders = client_for("cashier")
    product = shop.product("R-7")
    sale, line = shop.sale(product, 15)                              # ৳1500, now under the raised ৳5000 threshold
    r = cashier.post(f"/api/app/sales/{sale['id']}/returns", headers=cheaders, json=return_body(line, 15))
    assert r.status_code == 200


def test_voiding_a_large_paid_sale_by_a_manager_alone_never_needs_a_self_override(setup, client_for, world, engine):
    """A manager already meets the default refund rule's own role, so the
    synchronous override never even has to be asked for — only a role that
    ranks *below* the rule needs one."""
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "manager@a.example"))
        user.password_hash = hash_password(PASSWORD)
        db.commit()
    shop = setup
    manager, mheaders = client_for("manager")
    product = shop.product("R-8")
    sale, _ = shop.sale(product, 15)
    r = manager.post(f"/api/app/sales/{sale['id']}/void", headers=mheaders, json={"reason": "ভুল বিক্রি"})
    assert r.status_code == 200 and Decimal(r.json()["refund_amount"]) == 1500
