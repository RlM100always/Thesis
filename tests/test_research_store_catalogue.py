"""Checks that the 32-store UI preview is linked to one coherent synthetic source."""
from __future__ import annotations

from api.research_portal_routes import _all_shops, datasets, shop_detail, shops


def test_all_32_simulated_stores_are_available():
    rows = _all_shops()
    assert len(rows) == 32
    assert len({s["shop_id"] for s in rows}) == 32
    assert {s["division"] for s in rows} == {
        "Dhaka", "Chattogram", "Rajshahi", "Khulna",
        "Barishal", "Sylhet", "Rangpur", "Mymensingh",
    }
    assert all(s["evidence_tier"] == "synthetic_simulation" for s in rows)


def test_aggregate_orders_and_revenue_reconcile():
    rows = _all_shops()
    assert sum(s["orders"] for s in rows) == 365447
    assert sum(s["sales_lines"] for s in rows) == 736683
    assert sum(s["purchase_orders"] for s in rows) == 122422
    assert sum(s["stock_movements"] for s in rows) == 994808
    assert abs(sum(s["net_sales_bdt"] for s in rows) - 258266572.34) < .1
    for s in rows:
        assert sum(y["orders"] for y in s["years"]) == s["orders"]
        assert abs(sum(y["net_sales_bdt"] for y in s["years"]) - s["net_sales_bdt"]) <= 2.0


def test_preview_does_not_claim_full_operational_import_or_trained_models():
    dataset = datasets()["datasets"][0]
    assert dataset["preview_available"] is True
    assert dataset["installed"] is False
    assert dataset["evidence_tier"] == "synthetic_simulation"
    response = shops()
    assert response["preview_only"]
    assert not response["full_dataset_imported"]
    selected = shop_detail("SH001")
    assert selected["shop"]["orders"] == 10103
    assert selected["shop"]["recent_invoice_example"]["order_id"] == "SO0000365189"
