"""Capture real B-SMART operational UI screens using isolated seeded demo data.

All records are synthetic test fixtures created in a throwaway SQLite database.
No research customer records or production credentials are used.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from .conftest import WEB, call, sign_in

SHOTS = os.environ.get("SHOTS_DIR")
pytestmark = pytest.mark.skipif(not SHOTS, reason="SHOTS_DIR must be set by the screenshot workflow")


def _seed_generic_retail(shop):
    token, org = shop["token"], shop["org"]
    tag = shop["tag"]
    # Re-label the fixture tenant as a general retail SME; no pharmacy data is used.
    call("PATCH", "/api/app/organization",
         {"name": f"Green Basket Retail {tag}", "sector": "retail"}, token, org)
    branch = call("GET", "/api/app/branches", token=token, org=org)[0]["id"]
    supplier = shop["supplier"]
    now = datetime.now(timezone.utc)
    now_s = now.isoformat()

    products = [
        ("RICE-5KG", "Miniket Rice 5 kg", "450", "400", 40, 10),
        ("LENTIL-1KG", "Masoor Dal 1 kg", "145", "122", 100, 15),
        ("OIL-1L", "Soybean Oil 1 litre", "175", "158", 80, 12),
        ("DETERGENT-500", "Laundry Detergent 500 g", "95", "78", 100, 20),
    ]
    product_ids = {}
    for sku, name, selling, cost, stock, reorder in products:
        p = call("POST", "/api/app/products", {
            "sku": sku, "name": name, "category": "Grocery & Household",
            "unit": "pcs", "selling_price": selling, "cost_price": cost,
            "reorder_level": str(reorder), "track_expiry": False,
        }, token, org)
        product_ids[sku] = p["id"]
        po = call("POST", "/api/app/purchases", {
            "branch_id": branch, "supplier_id": supplier["id"],
            "order_number": f"DEMO-PO-{sku}", "ordered_at": now_s,
            "items": [{"product_id": p["id"], "quantity": str(stock), "unit_cost": cost}],
        }, token, org)
        orders = call("GET", "/api/app/purchases", token=token, org=org)
        line = next(x for x in next(x for x in orders if x["id"] == po["id"])["items"])
        call("POST", f"/api/app/purchases/{po['id']}/receive", {
            "received_at": now_s,
            "items": [{"purchase_order_item_id": line["id"], "quantity": str(stock)}],
        }, token, org)

    dormant = call("POST", "/api/app/customers", {
        "code": "DEMO-C-OLD", "display_name": "Amina Rahman",
        "marketing_consent": True,
    }, token, org)
    active = call("POST", "/api/app/customers", {
        "code": "DEMO-C-ACTIVE", "display_name": "Rahim Uddin",
        "marketing_consent": True,
    }, token, org)

    def sale(invoice, sku, quantity, price, when, customer=None):
        call("POST", "/api/app/sales", {
            "branch_id": branch, "invoice_number": invoice,
            "sold_at": when.isoformat(),
            "customer_id": customer["id"] if customer else None,
            "items": [{"product_id": product_ids[sku], "quantity": str(quantity)}],
            "payments": [{"method": "cash", "amount": str(int(price) * int(quantity))}],
        }, token, org)

    # Old, consented customer: creates an eligible retention case.
    sale("DEMO-OLD-001", "LENTIL-1KG", 8, 145, now - timedelta(days=68), dormant)
    # Recent rice demand leaves the stock low enough for a live reorder candidate.
    sale("DEMO-RICE-001", "RICE-5KG", 35, 450, now - timedelta(days=1), active)
    sale("DEMO-RICE-002", "RICE-5KG", 2, 450, now, active)
    sale("DEMO-OIL-001", "OIL-1L", 12, 175, now - timedelta(days=2), None)

    # Generate tenant-specific operational recommendations; these use the
    # live baseline/heuristic path unless a model artefact is explicitly loaded.
    call("POST", "/api/app/bsmart/run", {}, token, org)
    return {"token": token, "org": org, "email": shop["email"]}


def test_capture_real_operational_ui(shop, new_session):
    data = _seed_generic_retail(shop)
    out = Path(SHOTS)
    out.mkdir(parents=True, exist_ok=True)
    session = new_session(1440, 1000)
    sign_in(session, data["email"])
    page = session.page

    pages = [
        ("01-dashboard.png", "/"),
        ("02-sales-pos.png", "/sales"),
        ("03-inventory.png", "/inventory"),
        ("04-insights.png", "/insights"),
        ("05-recommendations.png", "/strategy"),
        ("06-reports.png", "/reports"),
        ("07-purchases.png", "/purchases"),
        ("08-customers.png", "/directory"),
    ]
    for filename, route in pages:
        page.goto(f"{WEB}/#{route}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out / filename), full_page=True)
