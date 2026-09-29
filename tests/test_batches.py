"""Batch and expiry stock: FEFO selling, expiry rules, recalls, returns and the books agreeing."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.domain_models import Batch, BatchStock, InventoryBalance, SaleItemBatch, StockMovement

NOW = datetime.now(timezone.utc)
TODAY = NOW.astimezone().date()


def day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


class Shop:
    """A tiny driver so each test reads as what the pharmacist does."""

    def __init__(self, client, headers, world, engine):
        self.c, self.h, self.w, self.engine = client, headers, world, engine
        self.product = None
        self._po = 0
        self._invoice = 0
        self.supplier = client.post("/api/app/suppliers", headers=headers,
                                    json={"code": "S1", "name": "Sup One"}).json()

    def product_with_stock(self, batches, *, track=True, cost="10", sku="MED-1"):
        self.product = self.c.post("/api/app/products", headers=self.h, json={
            "sku": sku, "name": "Napa 500", "selling_price": "15", "cost_price": cost,
            "track_expiry": track}).json()
        self.receive(batches)
        return self.product

    def receive(self, batches, expect=200, product=None):
        product = product or self.product
        self._po += 1
        total = sum(q for _, _, q in batches)
        po = self.c.post("/api/app/purchases", headers=self.h, json={
            "branch_id": self.w["branch_a"], "supplier_id": self.supplier["id"],
            "order_number": f"PO-{self._po}", "ordered_at": NOW.isoformat(),
            "items": [{"product_id": product["id"], "quantity": str(total), "unit_cost": "10"}]}).json()
        line = next(p for p in self.c.get("/api/app/purchases", headers=self.h).json()
                    if p["id"] == po["id"])["items"][0]["id"]
        response = self.c.post(f"/api/app/purchases/{po['id']}/receive", headers=self.h, json={
            "received_at": NOW.isoformat(),
            "items": [{"purchase_order_item_id": line, "quantity": str(q), "batch_no": no,
                       **({"expiry_date": day(d)} if d is not None else {})}
                      for no, d, q in batches]})
        assert response.status_code == expect, response.text
        return response

    def sell(self, quantity, product=None):
        product = product or self.product
        self._invoice += 1
        return self.c.post("/api/app/sales", headers=self.h, json={
            "branch_id": self.w["branch_a"], "invoice_number": f"INV-{self._invoice}",
            "sold_at": NOW.isoformat(),
            "items": [{"product_id": product["id"], "quantity": str(quantity)}],
            "payments": [{"method": "cash", "amount": str(15 * quantity)}]})

    def batches(self, **params):
        return self.c.get("/api/app/inventory/batches", headers=self.h,
                          params={"branch_id": self.w["branch_a"], **params}).json()

    def stock_by_batch(self):
        return {b["batch_no"]: Decimal(b["quantity"]) for b in self.batches()}

    def set_expiry(self, batch_no, days):
        with Session(self.engine) as db:
            batch = db.scalar(select(Batch).where(Batch.batch_no == batch_no))
            batch.expiry_date = TODAY + timedelta(days=days)
            db.commit()

    def issues(self):
        body = self.c.get("/api/app/inventory/reconciliation", headers=self.h,
                          params={"branch_id": self.w["branch_a"]}).json()
        return [i for i in body["items"] if i["sku"] == self.product["sku"]]


@pytest.fixture()
def shop(client_for, world, engine):
    client, headers = client_for("owner")
    return Shop(client, headers, world, engine)


# ── receiving ────────────────────────────────────────────────────────────────

def test_receiving_creates_batches_and_keeps_the_balance_in_step(shop):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-FAR", 300, 10)])
    assert shop.stock_by_batch() == {"B-NEAR": 5, "B-FAR": 10}
    inventory = shop.c.get("/api/app/inventory", headers=shop.h, params={"branch_id": shop.w["branch_a"]}).json()
    assert Decimal(next(i for i in inventory if i["sku"] == "MED-1")["quantity"]) == 15
    assert shop.issues() == []


def test_a_tracked_product_needs_batch_and_expiry_on_receipt(shop):
    shop.product_with_stock([("B-1", 100, 5)])
    assert shop.receive([("B-2", None, 5)], expect=422).status_code == 422  # no expiry given
    bad = shop.c.post("/api/app/purchases", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "supplier_id": shop.supplier["id"], "order_number": "PO-X",
        "ordered_at": NOW.isoformat(), "items": [{"product_id": shop.product["id"], "quantity": "5", "unit_cost": "10"}]}).json()
    line = next(p for p in shop.c.get("/api/app/purchases", headers=shop.h).json() if p["id"] == bad["id"])["items"][0]["id"]
    no_batch = shop.c.post(f"/api/app/purchases/{bad['id']}/receive", headers=shop.h, json={
        "received_at": NOW.isoformat(), "items": [{"purchase_order_item_id": line, "quantity": "5"}]})
    assert no_batch.status_code == 422


def test_an_already_expired_batch_is_refused_on_receipt(shop):
    shop.product_with_stock([("B-1", 100, 5)])
    assert shop.receive([("B-OLD", -3, 5)], expect=422).status_code == 422
    assert "B-OLD" not in shop.stock_by_batch()


def test_the_same_batch_arriving_again_adds_to_it_but_cannot_change_its_expiry(shop):
    shop.product_with_stock([("B-1", 100, 5)])
    shop.receive([("B-1", 100, 3)])
    assert shop.stock_by_batch() == {"B-1": 8}
    assert shop.receive([("B-1", 200, 1)], expect=409).status_code == 409
    assert shop.stock_by_batch() == {"B-1": 8}


def test_untracked_products_ignore_batch_fields_and_behave_as_before(shop):
    shop.product_with_stock([("B-1", 100, 5)], track=False, sku="PLAIN-1")
    assert shop.batches() == []
    assert shop.sell(2).status_code == 200


# ── FEFO selling ─────────────────────────────────────────────────────────────

def test_sales_take_the_earliest_expiry_first(shop):
    shop.product_with_stock([("B-FAR", 300, 10), ("B-NEAR", 20, 5)])
    assert shop.sell(3).status_code == 200
    assert shop.stock_by_batch() == {"B-NEAR": 2, "B-FAR": 10}


def test_a_sale_can_span_batches_and_records_each(shop, engine):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-FAR", 300, 10)])
    assert shop.sell(8).status_code == 200
    assert shop.stock_by_batch() == {"B-FAR": 7}
    with Session(engine) as db:
        taken = {db.get(Batch, r.batch_id).batch_no: r.quantity for r in db.scalars(select(SaleItemBatch))}
        moves = [m for m in db.scalars(select(StockMovement).where(StockMovement.movement_type == "sale"))]
    assert taken == {"B-NEAR": 5, "B-FAR": 3}
    assert sorted(m.quantity_delta for m in moves) == [-5, -3]
    assert all(m.batch_id for m in moves)
    assert shop.issues() == []


def test_unknown_expiry_stock_is_sold_last(client_for, world, engine):
    client, headers = client_for("owner")
    shop = Shop(client, headers, world, engine)
    shop.product = client.post("/api/app/products", headers=headers, json={
        "sku": "MED-1", "name": "Napa 500", "selling_price": "15", "cost_price": "10"}).json()
    client.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": shop.product["id"],
        "quantity_delta": "4", "reason": "opening stock"})
    client.post(f"/api/app/products/{shop.product['id']}/track-expiry", headers=headers)
    shop.receive([("B-DATED", 100, 4)])
    assert shop.sell(5).status_code == 200
    # The four dated units go first; only then is the undated opening stock touched.
    assert shop.stock_by_batch() == {"OPENING": 3}


def test_expired_batches_are_never_sold(shop):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-FAR", 300, 10)])
    shop.set_expiry("B-NEAR", -2)
    assert shop.sell(3).status_code == 200
    assert shop.stock_by_batch() == {"B-NEAR": 5, "B-FAR": 7}  # the expired one was skipped


def test_when_only_expired_stock_is_left_the_sale_is_refused_and_nothing_moves(shop):
    shop.product_with_stock([("B-NEAR", 20, 5)])
    shop.set_expiry("B-NEAR", -1)
    response = shop.sell(1)
    assert response.status_code == 409 and "expired or blocked" in response.json()["detail"]
    assert shop.stock_by_batch() == {"B-NEAR": 5}
    assert shop.issues() == []


def test_selling_more_than_the_batches_hold_is_atomic(shop):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-FAR", 300, 5)])
    assert shop.sell(11).status_code == 409
    assert shop.stock_by_batch() == {"B-NEAR": 5, "B-FAR": 5}
    assert shop.issues() == []


def test_cost_of_sale_comes_from_the_batches_sold(shop, engine):
    shop.product_with_stock([("B-NEAR", 20, 2)], cost="10")
    with Session(engine) as db:  # this batch cost 8, the next one 12
        db.scalar(select(Batch).where(Batch.batch_no == "B-NEAR")).unit_cost = Decimal("8")
        db.commit()
    shop.receive([("B-FAR", 300, 2)])
    with Session(engine) as db:
        db.scalar(select(Batch).where(Batch.batch_no == "B-FAR")).unit_cost = Decimal("12")
        db.commit()
    assert shop.sell(4).status_code == 200
    from api.domain_models import SalesOrderItem
    with Session(engine) as db:
        cost = db.scalar(select(SalesOrderItem.unit_cost_at_sale).where(SalesOrderItem.product_id == shop.product["id"]))
    assert cost == Decimal("10.00")  # (2*8 + 2*12) / 4


# ── recalls / quarantine ─────────────────────────────────────────────────────

def test_a_blocked_batch_is_not_sold_and_can_be_released(shop):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-FAR", 300, 10)])
    batch_id = next(b["batch_id"] for b in shop.batches() if b["batch_no"] == "B-NEAR")
    blocked = shop.c.post(f"/api/app/inventory/batches/{batch_id}/status", headers=shop.h,
                          json={"status": "blocked", "reason": "Recall notice DGDA/2026/14"})
    assert blocked.status_code == 200
    assert shop.sell(2).status_code == 200
    assert shop.stock_by_batch() == {"B-NEAR": 5, "B-FAR": 8}
    shop.c.post(f"/api/app/inventory/batches/{batch_id}/status", headers=shop.h, json={"status": "active"})
    assert shop.sell(2).status_code == 200
    assert shop.stock_by_batch() == {"B-NEAR": 3, "B-FAR": 8}


def test_blocking_needs_a_reason(shop):
    shop.product_with_stock([("B-1", 100, 5)])
    batch_id = shop.batches()[0]["batch_id"]
    assert shop.c.post(f"/api/app/inventory/batches/{batch_id}/status", headers=shop.h,
                       json={"status": "blocked"}).status_code == 422


def test_block_and_release_are_audited(shop):
    shop.product_with_stock([("B-1", 100, 5)])
    batch_id = shop.batches()[0]["batch_id"]
    shop.c.post(f"/api/app/inventory/batches/{batch_id}/status", headers=shop.h,
                json={"status": "blocked", "reason": "Damaged pack"})
    seen = [i["action"] for i in shop.c.get("/api/app/audit", headers=shop.h, params={"actions": "batch."}).json()["items"]]
    assert seen == ["batch.blocked"]


# ── returns ──────────────────────────────────────────────────────────────────

def test_a_return_goes_back_to_the_batch_it_came_from(shop):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-FAR", 300, 10)])
    sale = shop.sell(7)
    assert sale.status_code == 200
    line = shop.c.get("/api/app/sales", headers=shop.h).json()[0]["items"][0]["id"]
    ret = shop.c.post(f"/api/app/sales/{sale.json()['id']}/returns", headers=shop.h, json={
        "return_number": "R-1", "reason": "Customer changed mind", "returned_at": NOW.isoformat(),
        "refund_method": "cash", "items": [{"sales_order_item_id": line, "quantity": "6", "restock": True}]})
    assert ret.status_code == 200, ret.text
    # 5 from B-NEAR and 2 from B-FAR were sold; returning 6 refills the latest allocation first.
    assert sum(shop.stock_by_batch().values()) == 15 - 7 + 6
    assert shop.issues() == []


def test_a_return_without_restock_puts_nothing_back(shop):
    shop.product_with_stock([("B-1", 100, 10)])
    sale = shop.sell(4)
    line = shop.c.get("/api/app/sales", headers=shop.h).json()[0]["items"][0]["id"]
    shop.c.post(f"/api/app/sales/{sale.json()['id']}/returns", headers=shop.h, json={
        "return_number": "R-2", "reason": "Damaged on arrival", "returned_at": NOW.isoformat(),
        "refund_method": "cash", "items": [{"sales_order_item_id": line, "quantity": "2", "restock": False}]})
    assert shop.stock_by_batch() == {"B-1": 6}


# ── adjustments ──────────────────────────────────────────────────────────────

def adjust(shop, delta, **extra):
    return shop.c.post("/api/app/inventory/adjust", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "product_id": shop.product["id"],
        "quantity_delta": str(delta), "reason": "stock take", **extra})


def test_taking_stock_off_needs_a_named_batch(shop):
    shop.product_with_stock([("B-1", 100, 10)])
    assert adjust(shop, -2).status_code == 422
    batch_id = shop.batches()[0]["batch_id"]
    assert adjust(shop, -2, batch_id=batch_id).status_code == 200
    assert shop.stock_by_batch() == {"B-1": 8}
    assert shop.issues() == []


def test_writing_off_more_than_the_batch_holds_is_refused(shop):
    shop.product_with_stock([("B-1", 100, 3)])
    batch_id = shop.batches()[0]["batch_id"]
    assert adjust(shop, -4, batch_id=batch_id).status_code == 409
    assert shop.stock_by_batch() == {"B-1": 3}


def test_adding_stock_can_open_a_new_batch(shop):
    shop.product_with_stock([("B-1", 100, 3)])
    assert adjust(shop, 4).status_code == 422  # needs batch details
    assert adjust(shop, 4, batch_no="B-NEW", expiry_date=day(200)).status_code == 200
    assert shop.stock_by_batch() == {"B-1": 3, "B-NEW": 4}
    assert shop.issues() == []


# ── switching tracking on ────────────────────────────────────────────────────

def test_turning_tracking_on_moves_existing_stock_into_an_opening_batch(client_for, world, engine):
    client, headers = client_for("owner")
    shop = Shop(client, headers, world, engine)
    shop.product = client.post("/api/app/products", headers=headers, json={
        "sku": "OLD-1", "name": "Old stock", "selling_price": "15", "cost_price": "6"}).json()
    client.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": shop.product["id"],
        "quantity_delta": "12", "reason": "opening stock"})
    on = client.post(f"/api/app/products/{shop.product['id']}/track-expiry", headers=headers)
    assert on.status_code == 200 and Decimal(on.json()["opening_units"]) == 12
    rows = shop.batches()
    assert [(b["batch_no"], Decimal(b["quantity"]), b["state"]) for b in rows] == [("OPENING", 12, "no_expiry")]
    assert client.post(f"/api/app/products/{shop.product['id']}/track-expiry", headers=headers).status_code == 409
    assert shop.sell(2).status_code == 200  # opening stock is sellable
    assert shop.stock_by_batch() == {"OPENING": 10}


# ── shelf views and summary ──────────────────────────────────────────────────

def test_batches_are_listed_earliest_expiry_first_with_state_and_value(shop):
    shop.product_with_stock([("B-FAR", 300, 10), ("B-NEAR", 20, 5)])
    rows = shop.batches()
    assert [b["batch_no"] for b in rows] == ["B-NEAR", "B-FAR"]
    assert rows[0]["state"] == "near_expiry" and rows[1]["state"] == "ok"
    assert rows[0]["days_to_expiry"] == 20
    assert Decimal(rows[0]["value"]) == Decimal("50.00")


def test_state_filter_and_window(shop):
    shop.product_with_stock([("B-NEAR", 20, 5), ("B-MID", 60, 5), ("B-FAR", 300, 5)])
    assert [b["batch_no"] for b in shop.batches(state="near_expiry")] == ["B-NEAR", "B-MID"]
    assert [b["batch_no"] for b in shop.batches(state="near_expiry", days=30)] == ["B-NEAR"]
    shop.set_expiry("B-NEAR", -1)
    assert [b["batch_no"] for b in shop.batches(state="expired")] == ["B-NEAR"]


def test_expiry_summary_buckets_and_money_at_risk(shop):
    shop.product_with_stock([("B-A", 10, 2), ("B-B", 45, 3), ("B-C", 80, 4), ("B-D", 300, 5), ("B-E", 5, 1)])
    shop.set_expiry("B-E", -3)
    body = shop.c.get("/api/app/inventory/expiry-summary", headers=shop.h,
                      params={"branch_id": shop.w["branch_a"]}).json()
    units = {name: Decimal(b["units"]) for name, b in body["buckets"].items()}
    assert units == {"expired": 1, "d30": 2, "d60": 3, "d90": 4, "later": 5, "no_expiry": 0}
    assert Decimal(body["at_risk_value"]) == Decimal("100.00")  # (1+2+3+4) units at cost 10


def test_unknown_cost_is_reported_not_counted_as_zero(shop, engine):
    shop.product_with_stock([("B-A", 10, 2)])
    with Session(engine) as db:
        db.scalar(select(Batch)).unit_cost = None
        db.commit()
    body = shop.c.get("/api/app/inventory/expiry-summary", headers=shop.h,
                      params={"branch_id": shop.w["branch_a"]}).json()
    assert Decimal(body["at_risk_value"]) == 0
    assert Decimal(body["at_risk_unknown_cost_units"]) == 2
    assert shop.batches()[0]["value"] is None


# ── reconciliation ───────────────────────────────────────────────────────────

def test_reconciliation_flags_a_balance_that_the_ledger_does_not_explain(shop, engine):
    shop.product_with_stock([("B-1", 100, 10)])
    assert shop.issues() == []
    with Session(engine) as db:  # something edited the balance behind the ledger's back
        balance = db.scalar(select(InventoryBalance).where(InventoryBalance.product_id == shop.product["id"]))
        balance.quantity += 3
        db.commit()
    issue = shop.issues()[0]
    assert Decimal(issue["ledger_residual"]) == 3 and Decimal(issue["batch_residual"]) == 3


def test_reconciliation_flags_batches_that_disagree_with_the_balance(shop, engine):
    shop.product_with_stock([("B-1", 100, 10)])
    with Session(engine) as db:
        db.scalar(select(BatchStock)).quantity -= 2
        db.commit()
    issue = shop.issues()[0]
    assert Decimal(issue["batch_residual"]) == 2 and Decimal(issue["ledger_residual"]) == 0


# ── isolation and permissions ────────────────────────────────────────────────

def test_another_business_cannot_see_or_change_these_batches(shop, client_for, world):
    shop.product_with_stock([("B-1", 100, 5)])
    batch_id = shop.batches()[0]["batch_id"]
    other, other_headers = client_for("owner", org="org_b")
    assert other.post(f"/api/app/inventory/batches/{batch_id}/status", headers=other_headers,
                      json={"status": "blocked", "reason": "prank"}).status_code == 404
    assert other.get("/api/app/inventory/batches", headers=other_headers,
                     params={"branch_id": world["branch_a"]}).status_code == 404


@pytest.mark.parametrize("role,can_view,can_change", [
    ("owner", True, True), ("manager", True, True), ("stock_keeper", True, True),
    ("cashier", True, False), ("viewer", True, False), ("accountant", True, False),
    ("evaluator", False, False),
])
def test_who_may_view_and_change_batches(shop, client_for, world, role, can_view, can_change):
    shop.product_with_stock([("B-1", 100, 5)])
    batch_id = shop.batches()[0]["batch_id"]
    client, headers = client_for(role)
    view = client.get("/api/app/inventory/batches", headers=headers, params={"branch_id": world["branch_a"]})
    change = client.post(f"/api/app/inventory/batches/{batch_id}/status", headers=headers,
                         json={"status": "blocked", "reason": "test"})
    assert (view.status_code == 200) == can_view
    assert (change.status_code == 200) == can_change


# ── regression: found by the end-to-end run ──────────────────────────────────

def test_receiving_free_goods_at_zero_cost_works_and_owes_nothing(shop, engine):
    """A ৳0 line (sample, bonus stock) used to crash with a 500: the ledger rejects a zero entry."""
    from api.domain_models import LedgerEntry
    shop.product = shop.c.post("/api/app/products", headers=shop.h, json={
        "sku": "FREE-1", "name": "Free sample", "selling_price": "5", "track_expiry": True}).json()
    po = shop.c.post("/api/app/purchases", headers=shop.h, json={
        "branch_id": shop.w["branch_a"], "supplier_id": shop.supplier["id"], "order_number": "PO-FREE",
        "ordered_at": NOW.isoformat(),
        "items": [{"product_id": shop.product["id"], "quantity": "10", "unit_cost": "0"}]}).json()
    line = next(p for p in shop.c.get("/api/app/purchases", headers=shop.h).json() if p["id"] == po["id"])["items"][0]["id"]
    response = shop.c.post(f"/api/app/purchases/{po['id']}/receive", headers=shop.h, json={
        "received_at": NOW.isoformat(),
        "items": [{"purchase_order_item_id": line, "quantity": "10", "batch_no": "F-1", "expiry_date": day(90)}]})
    assert response.status_code == 200, response.text
    assert shop.stock_by_batch() == {"F-1": 10}
    with Session(engine) as db:
        assert db.scalars(select(LedgerEntry).where(LedgerEntry.ledger_type == "payable")).all() == []
