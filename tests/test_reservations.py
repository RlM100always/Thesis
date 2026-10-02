"""Reservations: hold stock for one order, block it from everyone else, release/fulfill correctly."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body):
        return self.c.post(f"/api/app{path}", headers=self.h, json=body)

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def product(self, sku, stock=10, price="100"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price}).json()
        self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def order(self, product, qty):
        self.n += 1
        return self.post("/sales-documents", {
            "document_type": "order", "document_number": f"RES-ORD-{self.n}",
            "branch_id": self.w["branch_a"], "issued_at": NOW.isoformat(),
            "items": [{"product_id": product["id"], "quantity": str(qty)}],
        }).json()

    def sale(self, product, qty, status=200):
        self.n += 1
        unit = Decimal(product["selling_price"])
        r = self.post("/sales", {
            "branch_id": self.w["branch_a"], "invoice_number": f"RES-SALE-{self.n}",
            "sold_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(unit * qty)}],
        })
        assert r.status_code == status, r.text
        return r.json()


@pytest.fixture()
def shop(client_for, world):
    client, headers = client_for("owner")
    return Shop(client, headers, world)


def test_reserving_an_order_holds_stock(shop):
    product = shop.product("RES-1", stock=10)
    order = shop.order(product, 6)
    reserved = shop.post("/reservations", {"sales_document_id": order["id"]})
    assert reserved.status_code == 200
    assert len(reserved.json()) == 1 and Decimal(reserved.json()[0]["quantity"]) == 6


def test_reserved_stock_is_unavailable_to_a_walk_in_sale(shop):
    product = shop.product("RES-2", stock=10)
    order = shop.order(product, 7)
    shop.post("/reservations", {"sales_document_id": order["id"]})
    # Only 3 of the 10 units are actually available now.
    blocked = shop.sale(product, 4, status=409)
    assert "reserved" in blocked["detail"].lower()
    allowed = shop.sale(product, 3, status=200)
    assert allowed


def test_fulfilling_the_reserved_order_consumes_its_own_hold_cleanly(shop):
    product = shop.product("RES-3", stock=10)
    order = shop.order(product, 6)
    shop.post("/reservations", {"sales_document_id": order["id"]})
    invoiced = shop.post(f"/sales-documents/{order['id']}/invoice", {
        "invoice_number": "RES-INV-1", "sold_at": NOW.isoformat(),
        "payments": [{"method": "cash", "amount": "600"}],
    })
    assert invoiced.status_code == 200
    # Stock actually dropped by 6 (10 - 6 = 4), nothing double-reserved or phantom-blocked.
    remaining = shop.get("/reservations/availability/" + product["id"], branch_id=shop.w["branch_a"])
    assert Decimal(str(remaining["on_hand"])) == 4
    assert Decimal(str(remaining["reserved"])) == 0
    assert Decimal(str(remaining["available"])) == 4


def test_cancelling_the_order_releases_its_reservation(shop):
    product = shop.product("RES-4", stock=10)
    order = shop.order(product, 8)
    shop.post("/reservations", {"sales_document_id": order["id"]})
    cancelled = shop.post(f"/sales-documents/{order['id']}/status", {"status": "cancelled"})
    assert cancelled.status_code == 200
    # Stock is free again for someone else.
    allowed = shop.sale(product, 8, status=200)
    assert allowed


def test_manual_release_frees_stock(shop):
    product = shop.product("RES-5", stock=10)
    order = shop.order(product, 9)
    shop.post("/reservations", {"sales_document_id": order["id"]})
    blocked = shop.sale(product, 2, status=409)
    assert blocked
    released = shop.post(f"/reservations/{order['id']}/release", {})
    assert released.status_code == 200
    allowed = shop.sale(product, 9, status=200)
    assert allowed


def test_expired_reservation_no_longer_blocks_availability(shop, engine):
    from sqlalchemy.orm import Session
    from api.domain_models import Reservation

    product = shop.product("RES-6", stock=10)
    order = shop.order(product, 9)
    created = shop.post("/reservations", {"sales_document_id": order["id"]}).json()
    with Session(engine) as db:
        row = db.get(Reservation, created[0]["id"])
        row.expires_at = NOW - timedelta(hours=1)
        db.commit()
    allowed = shop.sale(product, 9, status=200)
    assert allowed


def test_cannot_reserve_a_quotation(shop):
    product = shop.product("RES-7")
    shop.n += 1
    quote = shop.post("/sales-documents", {
        "document_type": "quotation", "document_number": f"RES-QUOTE-{shop.n}",
        "branch_id": shop.w["branch_a"], "issued_at": NOW.isoformat(),
        "items": [{"product_id": product["id"], "quantity": "1"}],
    }).json()
    response = shop.post("/reservations", {"sales_document_id": quote["id"]})
    assert response.status_code == 422


def test_cannot_double_reserve_the_same_order(shop):
    product = shop.product("RES-8")
    order = shop.order(product, 1)
    shop.post("/reservations", {"sales_document_id": order["id"]})
    again = shop.post("/reservations", {"sales_document_id": order["id"]})
    assert again.status_code == 409


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("stock_keeper", False), ("viewer", False)])
def test_who_may_reserve(client_for, world, role, allowed):
    owner, oheaders = client_for("owner")
    product = owner.post("/api/app/products", headers=oheaders, json={"sku": f"RES-PERM-{role}", "name": "P", "selling_price": "10"}).json()
    owner.post("/api/app/inventory/adjust", headers=oheaders, json={"branch_id": world["branch_a"], "product_id": product["id"], "quantity_delta": "10", "reason": "open"})
    order = owner.post("/api/app/sales-documents", headers=oheaders, json={
        "document_type": "order", "document_number": f"RES-PERM-ORD-{role}", "branch_id": world["branch_a"],
        "issued_at": NOW.isoformat(), "items": [{"product_id": product["id"], "quantity": "1"}],
    }).json()
    client, headers = client_for(role)
    response = client.post("/api/app/reservations", headers=headers, json={"sales_document_id": order["id"]})
    assert (response.status_code == 200) == allowed
