"""The audit trail: every sensitive action leaves a row, and only the right people can read it."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.domain_models import AuditLog

NOW = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc).isoformat()


def actions_seen(client, headers, **params):
    body = client.get("/api/app/audit", headers=headers, params={"limit": 200, **params}).json()
    return [item["action"] for item in body["items"]]


@pytest.fixture()
def owner(client_for):
    return client_for("owner")


def test_new_product_and_staff_invite_appear_with_who_did_it(owner):
    client, headers = owner
    client.post("/api/app/products", headers=headers, json={"sku": "PARA-500", "name": "Paracetamol", "selling_price": "2"})
    client.post("/api/app/staff", headers=headers, json={"email": "z@a.example", "display_name": "Zed Zed", "role": "viewer"})
    body = client.get("/api/app/audit", headers=headers).json()
    by_action = {item["action"]: item for item in body["items"]}
    assert {"product.created", "staff.invited"} <= set(by_action)
    assert by_action["staff.invited"]["actor"]["email"] == "owner@a.example"
    assert by_action["staff.invited"]["details"] == {"role": "viewer"}


def test_newest_first(owner):
    client, headers = owner
    for sku in ("A-1", "B-2", "C-3"):
        client.post("/api/app/products", headers=headers, json={"sku": sku, "name": sku, "selling_price": "1"})
    items = client.get("/api/app/audit", headers=headers).json()["items"]
    stamps = [item["created_at"] for item in items]
    assert stamps == sorted(stamps, reverse=True)


def test_money_and_data_actions_are_recorded(owner):
    client, headers = owner
    supplier = client.post("/api/app/suppliers", headers=headers,
                           json={"code": "SUP1", "name": "Square Distributor", "typical_lead_days": 3}).json()
    customer = client.post("/api/app/customers", headers=headers,
                           json={"code": "C1", "display_name": "Rina Begum", "phone": "01712345678", "marketing_consent": True}).json()
    client.post("/api/app/expenses", headers=headers, json={
        "category": "ভাড়া", "amount": "5000", "payment_method": "cash", "incurred_at": NOW})
    seen = actions_seen(client, headers)
    assert {"supplier.created", "customer.created", "expense.created"} <= set(seen)
    assert supplier["id"] and customer["id"]


def test_customer_personal_details_never_enter_the_trail(owner, engine):
    client, headers = owner
    client.post("/api/app/customers", headers=headers,
                json={"code": "C9", "display_name": "Secret Name", "phone": "01712345678"})
    with Session(engine) as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.action == "customer.created")).all()
    blob = " ".join(f"{r.metadata_json} {r.entity_id}" for r in rows)
    assert "Secret Name" not in blob and "01712345678" not in blob


def test_dataset_export_is_audited(owner):
    client, headers = owner
    assert client.get("/api/app/datasets/sales.csv", headers=headers).status_code == 200
    assert "dataset.exported" in actions_seen(client, headers)


def test_bsmart_decisions_are_audited(owner, engine, world):
    from api.domain_models import Recommendation
    client, headers = owner
    with Session(engine) as db:
        reco = Recommendation(
            organization_id=world["org_a"], run_id="run-1", cutoff_date="2026-09-01",
            action_type="reorder", target_sku="RICE-1", quantity=20, benefit_bdt=100,
            action_cost_bdt=10, risk_bdt=5, utility_bdt=85, feasible=True, model_version="test",
        )
        db.add(reco)
        db.commit()
        reco_id = reco.id
    response = client.post(f"/api/app/bsmart/recommendations/{reco_id}/decision", headers=headers, json={"decision": "accept"})
    assert response.status_code == 200, response.text
    items = client.get("/api/app/audit", headers=headers, params={"actions": "bsmart."}).json()["items"]
    assert [i["action"] for i in items] == ["bsmart.decided"]
    assert items[0]["details"]["decision"] == "accept"


# ── filters, paging, safety ──────────────────────────────────────────────────

def test_filter_by_action_prefix(owner):
    client, headers = owner
    client.post("/api/app/products", headers=headers, json={"sku": "F-1", "name": "F", "selling_price": "1"})
    client.post("/api/app/staff", headers=headers, json={"email": "f@a.example", "display_name": "Effe Effe", "role": "viewer"})
    assert set(actions_seen(client, headers, actions="staff.")) == {"staff.invited"}
    assert set(actions_seen(client, headers, actions="staff.,product.")) == {"staff.invited", "product.created"}


def test_action_filter_rejects_wildcards(owner):
    client, headers = owner
    for bad in ("%", "staff%", "a b", "x;y"):
        assert client.get("/api/app/audit", headers=headers, params={"actions": bad}).status_code == 422


def test_pages_are_disjoint_and_complete(owner):
    client, headers = owner
    for i in range(7):
        client.post("/api/app/products", headers=headers, json={"sku": f"P-{i}", "name": f"P{i}", "selling_price": "1"})
    everything = client.get("/api/app/audit", headers=headers, params={"limit": 200}).json()["items"]
    collected, cursor = [], None
    while True:
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/app/audit", headers=headers, params=params).json()
        collected += [item["id"] for item in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert collected == [item["id"] for item in everything]
    assert len(collected) == len(set(collected))


def test_bad_cursor_is_rejected(owner):
    client, headers = owner
    assert client.get("/api/app/audit", headers=headers, params={"cursor": "garbage"}).status_code == 422


def test_each_business_sees_only_its_own_trail(client_for):
    client_a, headers_a = client_for("owner", org="org_a")
    client_b, headers_b = client_for("owner", org="org_b")
    client_a.post("/api/app/products", headers=headers_a, json={"sku": "ONLY-A", "name": "A", "selling_price": "1"})
    assert client_b.get("/api/app/audit", headers=headers_b).json()["items"] == []
    assert "product.created" in actions_seen(client_a, headers_a)


def test_there_is_no_way_to_edit_or_delete_audit_rows(owner):
    client, headers = owner
    client.post("/api/app/products", headers=headers, json={"sku": "X-1", "name": "X", "selling_price": "1"})
    entry = client.get("/api/app/audit", headers=headers).json()["items"][0]["id"]
    for method in ("PATCH", "PUT", "DELETE"):
        assert client.request(method, f"/api/app/audit/{entry}", headers=headers).status_code in (404, 405)


def test_risk_summary_counts_control_bypass_actions_by_type_and_actor(owner, world):
    client, headers = owner
    client.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": world["product_a"],
        "quantity_delta": "5", "reason": "recount",
    })
    client.post("/api/app/inventory/adjust", headers=headers, json={
        "branch_id": world["branch_a"], "product_id": world["product_a"],
        "quantity_delta": "-2", "reason": "damage",
    })
    body = client.get("/api/app/risk/exceptions", headers=headers).json()
    assert body["by_action"]["inventory.adjusted"] == 2
    assert body["total"] == 2
    actor = body["by_actor"][0]
    assert actor["actor_name"] == "owner A"
    assert actor["by_action"]["inventory.adjusted"] == 2
    assert actor["total"] == 2


def test_risk_summary_window_excludes_old_events(owner, world, engine):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.orm import Session as OrmSession
    from api.domain_models import AuditLog as AL

    client, headers = owner
    with OrmSession(engine) as db:
        db.add(AL(
            organization_id=world["org_a"], action="sale.voided",
            entity_type="sales_order", created_at=datetime.now(timezone.utc) - timedelta(days=90),
        ))
        db.commit()
    body = client.get("/api/app/risk/exceptions", headers=headers, params={"days": 30}).json()
    assert body.get("by_action", {}).get("sale.voided", 0) == 0


def test_a_failed_action_leaves_no_audit_row(owner):
    """The audit entry commits with the change: a rejected duplicate writes nothing."""
    client, headers = owner
    payload = {"code": "DUP", "name": "Dup Supplier"}
    assert client.post("/api/app/suppliers", headers=headers, json=payload).status_code == 200
    assert client.post("/api/app/suppliers", headers=headers, json=payload).status_code == 409
    assert actions_seen(client, headers).count("supplier.created") == 1
