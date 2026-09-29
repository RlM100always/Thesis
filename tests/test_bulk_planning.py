"""Bulk import, shop profile, and the reorder plan."""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


def upload(client, headers, kind, text, mapping=None, mode="skip_existing", branch=None, path="commit", name="data.csv"):
    data = {"kind": kind}
    if path == "commit":
        data.update({"mapping": json.dumps(mapping or {}), "mode": mode})
        if branch:
            data["branch_id"] = branch
    body = text.encode("utf-8-sig") if isinstance(text, str) else text
    return client.post(f"/api/app/import/{path}", headers=headers, data=data, files={"file": (name, body, "text/csv")})


PRODUCT_MAP = {"sku": "sku", "name": "name", "selling_price": "price", "cost_price": "cost",
               "category": None, "unit": None, "barcode": None, "reorder_level": "min", "track_expiry": "expiry"}


# ── preview: recognising Bangla and English headers ──────────────────────────

def test_preview_guesses_columns_from_english_and_bangla_headers(client_for):
    client, headers = client_for("owner")
    csv = "পণ্যের কোড,পণ্যের নাম,বিক্রয়মূল্য,ক্রয়মূল্য,মজুত\nP1,নাপা,১৫,১০,৫০\n"
    body = upload(client, headers, "products", csv, path="preview").json()
    assert body["rows"] == 1 and body["mapping"]["sku"] == "পণ্যের কোড" and body["mapping"]["name"] == "পণ্যের নাম"
    assert body["mapping"]["selling_price"] == "বিক্রয়মূল্য" and body["mapping"]["cost_price"] == "ক্রয়মূল্য"
    assert body["sample"][0]["পণ্যের নাম"] == "নাপা"


def test_preview_rejects_unsupported_and_empty_files(client_for):
    client, headers = client_for("owner")
    assert upload(client, headers, "products", "x", path="preview", name="data.pdf").status_code == 400
    assert upload(client, headers, "products", "sku,name,price\n", path="preview").status_code == 400
    assert upload(client, headers, "nonsense", "a\n1\n", path="preview").status_code == 422


# ── products ─────────────────────────────────────────────────────────────────

def test_products_are_created_with_bangla_digits_and_yes_no_flags(client_for):
    client, headers = client_for("owner")
    csv = "sku,name,price,cost,min,expiry\nA-1,Napa,৳ ১৫.৫০,১০,5,হ্যাঁ\nA-2,Cable,\"1,200\",900,,no\n"
    result = upload(client, headers, "products", csv, PRODUCT_MAP).json()
    assert result["created"] == 2 and result["errors"] == []
    products = {p["sku"]: p for p in client.get("/api/app/products", headers=headers).json()}
    assert Decimal(products["A-1"]["selling_price"]) == Decimal("15.50") and products["A-1"]["track_expiry"] is True
    assert Decimal(products["A-2"]["selling_price"]) == 1200 and products["A-2"]["track_expiry"] is False


def test_bad_rows_are_reported_with_their_line_number_and_good_rows_still_land(client_for):
    client, headers = client_for("owner")
    csv = "sku,name,price,cost,min,expiry\nOK-1,Fine,10,5,,\n,No sku,10,5,,\nBAD-1,Bad price,abc,5,,\nOK-1,Twice,10,5,,\nBAD-2,Neg,-5,5,,\n"
    result = upload(client, headers, "products", csv, PRODUCT_MAP).json()
    assert result["created"] == 1
    lines = {e["row"] for e in result["errors"]}
    assert lines == {3, 4, 5, 6}        # header is line 1
    assert sorted(p["sku"] for p in client.get("/api/app/products", headers=headers).json()) == ["OK-1", "RICE-1"]


def test_existing_products_are_skipped_or_updated_as_chosen(client_for):
    client, headers = client_for("owner")
    upload(client, headers, "products", "sku,name,price,cost,min,expiry\nS-1,Old name,10,5,,\n", PRODUCT_MAP)
    csv = "sku,name,price,cost,min,expiry\nS-1,New name,99,50,,\n"
    skipped = upload(client, headers, "products", csv, PRODUCT_MAP).json()
    assert skipped["skipped"] == 1 and skipped["updated"] == 0
    updated = upload(client, headers, "products", csv, PRODUCT_MAP, mode="update_existing").json()
    assert updated["updated"] == 1
    product = client.get("/api/app/products", headers=headers).json()[0]
    assert product["name"] == "New name" and Decimal(product["selling_price"]) == 99


def test_a_required_column_must_be_mapped(client_for):
    client, headers = client_for("owner")
    response = upload(client, headers, "products", "sku,name,price\nA,B,1\n", {"sku": "sku", "name": "name"})
    assert response.status_code == 422 and "selling_price" in response.json()["detail"]


# ── customers ────────────────────────────────────────────────────────────────

def test_customers_import_hashes_phone_numbers_and_validates_them(client_for, engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from api.domain_models import Customer
    client, headers = client_for("owner")
    csv = "code,name,phone,consent\nC1,রিনা,+8801712345678,হ্যাঁ\nC2,করিম,০১৮১২৩৪৫৬৭৮,না\nC3,Bad,12345,\nC1,Dup,,\n"
    mapping = {"code": "code", "display_name": "name", "phone": "phone", "marketing_consent": "consent"}
    result = upload(client, headers, "customers", csv, mapping).json()
    assert result["created"] == 2 and {e["row"] for e in result["errors"]} == {4, 5}
    with Session(engine) as db:
        rows = {c.code: c for c in db.scalars(select(Customer).where(Customer.code.in_(["C1", "C2"])))}
    assert rows["C1"].marketing_consent is True and rows["C2"].marketing_consent is False
    assert rows["C1"].phone_hash and "8801712345678" not in rows["C1"].phone_hash


# ── opening stock ────────────────────────────────────────────────────────────

def test_opening_stock_for_plain_and_expiry_tracked_products(client_for, world):
    client, headers = client_for("owner")
    upload(client, headers, "products", "sku,name,price,cost,min,expiry\nP-1,Plain,10,5,,no\nT-1,Tracked,10,5,,yes\n", PRODUCT_MAP)
    future = (date.today() + timedelta(days=200)).isoformat()
    csv = f"sku,qty,batch,exp\nP-1,40,,\nT-1,25,B-9,{future}\nT-1,5,,\nT-1,3,B-OLD,2020-01-01\nGHOST,4,,\nP-1,0,,\n"
    mapping = {"sku": "sku", "quantity": "qty", "batch_no": "batch", "expiry_date": "exp"}
    result = upload(client, headers, "opening_stock", csv, mapping, branch=world["branch_a"]).json()
    assert result["created"] == 2 and {e["row"] for e in result["errors"]} == {4, 5, 6, 7}
    stock = {r["sku"]: Decimal(r["quantity"]) for r in client.get(
        "/api/app/inventory", headers=headers, params={"branch_id": world["branch_a"]}).json()}
    assert stock["P-1"] == 40 and stock["T-1"] == 25
    batches = client.get("/api/app/inventory/batches", headers=headers, params={"branch_id": world["branch_a"]}).json()
    assert [b["batch_no"] for b in batches] == ["B-9"]
    audit = client.get("/api/app/inventory/reconciliation", headers=headers, params={"branch_id": world["branch_a"]}).json()
    assert audit["mismatched"] == 1 and audit["items"][0]["sku"] == "RICE-1"   # only the fixture's un-ledgered rice


def test_month_year_expiry_means_the_last_day_of_the_month(client_for, world):
    client, headers = client_for("owner")
    upload(client, headers, "products", "sku,name,price,cost,min,expiry\nT-1,Tracked,10,5,,yes\n", PRODUCT_MAP)
    year = date.today().year + 2
    upload(client, headers, "opening_stock", f"sku,qty,batch,exp\nT-1,5,B-1,02/{year}\n",
           {"sku": "sku", "quantity": "qty", "batch_no": "batch", "expiry_date": "exp"}, branch=world["branch_a"])
    batch = client.get("/api/app/inventory/batches", headers=headers, params={"branch_id": world["branch_a"]}).json()[0]
    assert batch["expiry_date"] in (f"{year}-02-28", f"{year}-02-29")


def test_opening_stock_needs_a_real_branch(client_for):
    client, headers = client_for("owner")
    assert upload(client, headers, "opening_stock", "sku,qty\nP,1\n", {"sku": "sku", "quantity": "qty"}).status_code == 422


@pytest.mark.parametrize("role,kind,allowed", [
    ("owner", "products", True), ("manager", "products", True), ("accountant", "products", False),
    ("accountant", "customers", True), ("cashier", "customers", False), ("viewer", "products", False),
    ("stock_keeper", "products", False)])
def test_who_may_import_what(client_for, role, kind, allowed):
    client, headers = client_for(role)
    csv = "sku,name,price\nX,Y,1\n" if kind == "products" else "code\nC\n"
    response = upload(client, headers, kind, csv, path="preview")
    assert (response.status_code == 200) == allowed


# ── shop profile ─────────────────────────────────────────────────────────────

def test_the_owner_can_set_the_details_printed_on_receipts(client_for, world):
    client, headers = client_for("owner")
    response = client.patch("/api/app/organization", headers=headers, json={
        "address": "মিরপুর-১০, ঢাকা", "phone": "01712345678", "vat_reg_no": "BIN-123", "receipt_footer": "আবার আসবেন"})
    assert response.status_code == 200 and response.json()["receipt_footer"] == "আবার আসবেন"
    listed = next(o for o in client.get("/api/app/organizations").json() if o["id"] == world["org_a"])
    assert listed["address"] == "মিরপুর-১০, ঢাকা" and listed["vat_reg_no"] == "BIN-123"
    cleared = client.patch("/api/app/organization", headers=headers, json={"receipt_footer": ""}).json()
    assert cleared["receipt_footer"] is None


@pytest.mark.parametrize("role", ["manager", "cashier", "accountant", "viewer"])
def test_only_the_owner_edits_the_shop_profile(client_for, role):
    client, headers = client_for(role)
    assert client.patch("/api/app/organization", headers=headers, json={"phone": "01"}).status_code == 403


# ── reorder plan ─────────────────────────────────────────────────────────────

class Store:
    def __init__(self, client, headers, world):
        self.c, self.h, self.w, self.n = client, headers, world, 0

    def post(self, path, body):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def product(self, sku, stock, reorder="0", price="10", cost="6"):
        p = self.post("/products", {"sku": sku, "name": sku, "selling_price": price, "cost_price": cost, "reorder_level": reorder})
        if stock:
            self.post("/inventory/adjust", {"branch_id": self.w["branch_a"], "product_id": p["id"], "quantity_delta": str(stock), "reason": "open"})
        return p

    def sell(self, product, qty):
        self.n += 1
        self.post("/sales", {"branch_id": self.w["branch_a"], "invoice_number": f"S-{self.n}", "sold_at": NOW.isoformat(),
                             "items": [{"product_id": product["id"], "quantity": str(qty)}],
                             "payments": [{"method": "cash", "amount": str(10 * qty)}]})

    def plan(self, **params):
        r = self.c.get("/api/app/reorder-plan", headers=self.h, params={"branch_id": self.w["branch_a"], **params})
        assert r.status_code == 200, r.text
        return {i["sku"]: i for i in r.json()["items"]}


@pytest.fixture()
def store(client_for, world):
    client, headers = client_for("owner")
    return Store(client, headers, world)


def test_a_well_stocked_product_is_left_out_of_the_plan(store):
    product = store.product("FAST", stock=100)
    store.sell(product, 56)                                     # 2 a day, 44 left
    assert "FAST" not in store.plan(cover_days=14)              # needs 2 * (7 + 14) = 42; has 44
    assert "FAST" in store.plan(cover_days=30)                  # needs 74 -> order 30


def test_low_cover_produces_an_order_and_marks_it_urgent(store):
    product = store.product("RUN", stock=30)
    store.sell(product, 28)                                     # 1/day; 2 left = 2 days of cover, lead is 7
    item = store.plan(cover_days=14)["RUN"]
    assert item["sellable"] == "2.000" or Decimal(item["sellable"]) == 2
    assert Decimal(item["suggested_qty"]) == 19                 # 1 * 21 - 2
    assert item["urgent"] is True and item["days_of_cover"] == 2.0


def test_stock_already_on_order_is_not_ordered_twice(store):
    product = store.product("PEND", stock=30)
    store.sell(product, 28)                                     # 1 a day, 2 left
    supplier = store.post("/suppliers", {"code": "S1", "name": "Sup", "typical_lead_days": 3})
    order = {"branch_id": store.w["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-1", "ordered_at": NOW.isoformat(),
             "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": "6"}]}
    assert Decimal(store.plan(cover_days=14)["PEND"]["suggested_qty"]) == 19          # 1 * (7 + 14) - 2, before ordering
    store.post("/purchases", order)
    item = store.plan(cover_days=14)["PEND"]
    assert Decimal(item["incoming"]) == 10 and item["lead_days"] == 3 and item["supplier_name"] == "Sup"
    assert Decimal(item["suggested_qty"]) == 5                                        # 1 * (3 + 14) - 2 - 10


def test_products_with_no_sales_fall_back_to_the_reorder_level(store):
    store.product("SLOW", stock=2, reorder="5")
    store.product("OK", stock=50, reorder="5")
    plan = store.plan()
    assert "SLOW" in plan and plan["SLOW"]["reason"] == "reorder_level" and Decimal(plan["SLOW"]["suggested_qty"]) == 8   # 2*5 - 2
    assert "OK" not in plan


def test_expired_and_blocked_units_do_not_count_as_cover(client_for, world, engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from api.domain_models import Batch
    client, headers = client_for("owner")
    s = Store(client, headers, world)
    product = s.post("/products", {"sku": "EXP", "name": "EXP", "selling_price": "10", "cost_price": "6", "track_expiry": True, "reorder_level": "5"})
    supplier = s.post("/suppliers", {"code": "S1", "name": "Sup"})
    order = s.post("/purchases", {"branch_id": world["branch_a"], "supplier_id": supplier["id"], "order_number": "PO-E", "ordered_at": NOW.isoformat(),
                                  "items": [{"product_id": product["id"], "quantity": "20", "unit_cost": "6"}]})
    line = next(p for p in client.get("/api/app/purchases", headers=headers).json() if p["id"] == order["id"])["items"][0]["id"]
    s.post(f"/purchases/{order['id']}/receive", {"received_at": NOW.isoformat(), "items": [
        {"purchase_order_item_id": line, "quantity": "20", "batch_no": "B1", "expiry_date": (date.today() + timedelta(days=30)).isoformat()}]})
    assert "EXP" not in s.plan()                                # 20 sellable, reorder level 5
    with Session(engine) as db:
        db.scalar(select(Batch)).expiry_date = date.today() - timedelta(days=1)
        db.commit()
    item = s.plan()["EXP"]                                      # now none of it may be sold
    assert Decimal(item["sellable"]) == 0 and Decimal(item["unsellable"]) == 20 and Decimal(item["suggested_qty"]) == 10


def test_ordering_from_the_plan_creates_one_purchase_order_per_supplier(store):
    a, b = store.product("PA", 0), store.product("PB", 0)
    s1 = store.post("/suppliers", {"code": "S1", "name": "One", "typical_lead_days": 4})
    s2 = store.post("/suppliers", {"code": "S2", "name": "Two"})
    body = {"branch_id": store.w["branch_a"], "orders": [
        {"supplier_id": s1["id"], "items": [{"product_id": a["id"], "quantity": "10", "unit_cost": "6"}, {"product_id": a["id"], "quantity": "5", "unit_cost": "6"}]},
        {"supplier_id": s2["id"], "items": [{"product_id": b["id"], "quantity": "3", "unit_cost": "8"}]}]}
    created = store.post("/reorder-plan/orders", body)["created"]
    assert [c["lines"] for c in created] == [1, 1] and Decimal(created[0]["total"]) == 90 and Decimal(created[1]["total"]) == 24
    orders = store.c.get("/api/app/purchases", headers=store.h).json()
    assert len(orders) == 2 and all(o["status"] == "ordered" for o in orders)
    first = next(o for o in orders if o["supplier_name"] == "One")
    assert Decimal(first["items"][0]["quantity"]) == 15                                    # merged
    assert (datetime.fromisoformat(first["expected_at"]) - datetime.fromisoformat(first["ordered_at"])).days == 4


def test_ordering_refuses_products_or_suppliers_of_another_business(store, client_for, world):
    other, other_headers = client_for("owner", org="org_b")
    foreign = other.post("/api/app/products", headers=other_headers, json={"sku": "F", "name": "F", "selling_price": "1"}).json()
    supplier = store.post("/suppliers", {"code": "S1", "name": "One"})
    bad = store.c.post("/api/app/reorder-plan/orders", headers=store.h, json={"branch_id": world["branch_a"], "orders": [
        {"supplier_id": supplier["id"], "items": [{"product_id": foreign["id"], "quantity": "1", "unit_cost": "1"}]}]})
    assert bad.status_code == 404


@pytest.mark.parametrize("role,can_plan,can_order", [
    ("owner", True, True), ("manager", True, True), ("accountant", True, True), ("stock_keeper", True, False),
    ("cashier", False, False), ("viewer", True, False), ("evaluator", False, False)])
def test_who_may_plan_and_order(client_for, world, role, can_plan, can_order):
    client, headers = client_for(role)
    planned = client.get("/api/app/reorder-plan", headers=headers, params={"branch_id": world["branch_a"]})
    ordered = client.post("/api/app/reorder-plan/orders", headers=headers, json={"branch_id": world["branch_a"], "orders": [
        {"supplier_id": "x", "items": [{"product_id": "y", "quantity": "1", "unit_cost": "1"}]}]})
    assert (planned.status_code == 200) == can_plan
    assert (ordered.status_code != 403) == can_order
