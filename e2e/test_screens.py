"""Screenshots of the main screens with realistic data, for visual review.

Skipped unless SHOTS_DIR is set:  SHOTS_DIR=<folder> python -m pytest e2e/test_screens.py
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .conftest import WEB, call, in_days, sign_in

SHOTS = os.environ.get("SHOTS_DIR")
pytestmark = pytest.mark.skipif(not SHOTS, reason="set SHOTS_DIR to take screenshots")


def seed(shop):
    t, o = shop["token"], shop["org"]
    branch = call("GET", "/api/app/branches", token=t, org=o)[0]["id"]
    now = datetime.now(timezone.utc).isoformat()
    items = [
        ("NAPA-500", "নাপা ৫০০ মি.গ্রা.", "15", "10", True, 50, [("N-2611", in_days(12), 30), ("N-2705", in_days(320), 90)]),
        ("SEC-20", "সেকলো ২০ মি.গ্রা.", "8", "5.5", True, 30, [("S-1902", in_days(-0 + 45), 80)]),
        ("ORS-1", "ওরস্যালাইন", "10", "6", False, 30, []),
        ("INS-R", "ইনসুলিন রিজুলার", "520", "430", True, 5, [("I-77", in_days(70), 8)]),
        ("AZI-250", "অ্যাজিথ্রোমাইসিন ২৫০", "45", "0", True, 30, [("A-9", in_days(200), 40)]),
    ]
    supplier = call("POST", "/api/app/suppliers", {"code": "ACI", "name": "একমি ডিস্ট্রিবিউটর", "typical_lead_days": 3}, t, o)
    ids = {}
    for sku, name, price, cost, track, reorder, batches in items:
        p = call("POST", "/api/app/products", {"sku": sku, "name": name, "selling_price": price, "cost_price": cost,
                                              "track_expiry": track, "reorder_level": str(reorder // 5)}, t, o)
        ids[sku] = p["id"]
        total = sum(q for _, _, q in batches) or 40
        po = call("POST", "/api/app/purchases", {
            "branch_id": branch, "supplier_id": supplier["id"], "order_number": f"PO-{sku}", "ordered_at": now,
            "items": [{"product_id": p["id"], "quantity": str(total), "unit_cost": cost}]}, t, o)
        line = next(x for x in call("GET", "/api/app/purchases", token=t, org=o) if x["id"] == po["id"])["items"][0]["id"]
        receive = [{"purchase_order_item_id": line, "quantity": str(q), "batch_no": b, "expiry_date": d} for b, d, q in batches] \
            or [{"purchase_order_item_id": line, "quantity": str(total)}]
        call("POST", f"/api/app/purchases/{po['id']}/receive", {"received_at": now, "items": receive}, t, o)
    # a few sales, a recall, a pending order
    customer = call("POST", "/api/app/customers", {"code": "C-1", "display_name": "হালিমা খাতুন", "marketing_consent": True}, t, o)
    for n, (sku, qty) in enumerate([("NAPA-500", 6), ("ORS-1", 4), ("SEC-20", 10), ("NAPA-500", 20)]):
        price = {"NAPA-500": 15, "ORS-1": 10, "SEC-20": 8}[sku]
        call("POST", "/api/app/sales", {
            "branch_id": branch, "invoice_number": f"INV-S{n}", "sold_at": now, "customer_id": customer["id"],
            "items": [{"product_id": ids[sku], "quantity": str(qty)}],
            "payments": [{"method": "cash", "amount": str(price * qty - (20 if n == 2 else 0))}]}, t, o)
    batches = call("GET", f"/api/app/inventory/batches?branch_id={branch}", token=t, org=o)
    call("POST", f"/api/app/inventory/batches/{next(b for b in batches if b['batch_no'] == 'I-77')['batch_id']}/status",
         {"status": "blocked", "reason": "রিকল নোটিশ এসেছে"}, t, o)
    call("POST", "/api/app/purchases", {"branch_id": branch, "supplier_id": supplier["id"], "order_number": "PO-NEW", "ordered_at": now,
                                        "items": [{"product_id": ids["ORS-1"], "quantity": "60", "unit_cost": "6"}]}, t, o)


def test_take_screenshots(shop, new_session):
    seed(shop)
    out = Path(SHOTS)
    out.mkdir(parents=True, exist_ok=True)

    desktop = new_session(1360, 900)
    sign_in(desktop, shop["email"])
    page = desktop.page
    page.goto(f"{WEB}/#/sales")
    page.get_by_placeholder(re.compile("পণ্যের নাম")).fill("নাপা")
    page.get_by_role("button", name=re.compile("নাপা")).first.click()
    page.get_by_placeholder(re.compile("পণ্যের নাম")).fill("ওরস")
    page.get_by_role("button", name=re.compile("ওরস্যালাইন")).first.click()
    page.get_by_placeholder(re.compile("পণ্যের নাম")).fill("")
    page.wait_for_timeout(700)
    page.screenshot(path=str(out / "d-sales.png"), full_page=True)
    for name, path in [("dashboard", "/"), ("cash", "/cash"), ("history", "/sales-history"), ("reports", "/reports"), ("directory", "/directory"), ("accounts", "/accounts"), ("returns", "/returns"), ("strategy", "/strategy"), ("settings", "/setup"), ("staff", "/staff"), ("products", "/products"), ("inventory", "/inventory"), ("expiry", "/expiry"), ("purchases", "/purchases"), ("audit", "/audit")]:
        page.goto(f"{WEB}/#{path}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        page.screenshot(path=str(out / f"d-{name}.png"), full_page=True)
    page.goto(f"{WEB}/#/purchases")
    page.get_by_role("button", name="মাল রিসিভ").first.click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(out / "d-receive-modal.png"))

    phone = new_session(390, 844)
    sign_in(phone, shop["email"])
    for name, path in [("sales", "/sales"), ("expiry", "/expiry"), ("inventory", "/inventory")]:
        phone.page.goto(f"{WEB}/#{path}")
        phone.page.wait_for_load_state("networkidle")
        phone.page.wait_for_timeout(600)
        phone.page.screenshot(path=str(out / f"m-{name}.png"), full_page=True)
