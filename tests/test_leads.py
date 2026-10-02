"""Leads / pipeline: stage progression, conversion into a real customer, and activity log."""

import pytest


@pytest.fixture()
def owner(client_for):
    return client_for("owner")


def test_create_and_read_a_lead(owner):
    client, headers = owner
    created = client.post("/api/app/leads", headers=headers, json={"name": "Karim Store", "source": "walk-in"})
    assert created.status_code == 200
    body = created.json()
    assert body["stage"] == "new" and body["source"] == "walk-in"
    fetched = client.get(f"/api/app/leads/{body['id']}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["name"] == "Karim Store"


def test_stage_progression(owner):
    client, headers = owner
    lead = client.post("/api/app/leads", headers=headers, json={"name": "Rahim Traders"}).json()
    qualified = client.patch(f"/api/app/leads/{lead['id']}", headers=headers, json={"stage": "qualified"})
    assert qualified.status_code == 200 and qualified.json()["stage"] == "qualified"
    quoted = client.patch(f"/api/app/leads/{lead['id']}", headers=headers, json={"stage": "quoted"})
    assert quoted.status_code == 200 and quoted.json()["stage"] == "quoted"


def test_winning_a_lead_requires_the_convert_endpoint(owner):
    client, headers = owner
    lead = client.post("/api/app/leads", headers=headers, json={"name": "Won Co"}).json()
    rejected = client.patch(f"/api/app/leads/{lead['id']}", headers=headers, json={"stage": "won"})
    assert rejected.status_code == 422


def test_convert_creates_a_real_customer_exactly_once(owner):
    client, headers = owner
    lead = client.post("/api/app/leads", headers=headers, json={"name": "New Shop", "estimated_value": "5000"}).json()
    converted = client.post(f"/api/app/leads/{lead['id']}/convert", headers=headers)
    assert converted.status_code == 200
    customer = converted.json()
    assert customer["display_name"] == "New Shop"

    closed_lead = client.get(f"/api/app/leads/{lead['id']}", headers=headers).json()
    assert closed_lead["stage"] == "won" and closed_lead["converted_customer_id"] == customer["id"]

    # Already closed -- cannot convert or update again.
    assert client.post(f"/api/app/leads/{lead['id']}/convert", headers=headers).status_code == 409
    assert client.patch(f"/api/app/leads/{lead['id']}", headers=headers, json={"stage": "qualified"}).status_code == 409


def test_losing_a_lead_requires_a_reason(owner):
    client, headers = owner
    lead = client.post("/api/app/leads", headers=headers, json={"name": "Lost Co"}).json()
    no_reason = client.patch(f"/api/app/leads/{lead['id']}", headers=headers, json={"stage": "lost"})
    assert no_reason.status_code == 422
    with_reason = client.patch(
        f"/api/app/leads/{lead['id']}", headers=headers, json={"stage": "lost", "lost_reason": "Too expensive"},
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["stage"] == "lost" and with_reason.json()["closed_at"] is not None


def test_activity_log(owner):
    client, headers = owner
    lead = client.post("/api/app/leads", headers=headers, json={"name": "Chatty Co"}).json()
    client.post(f"/api/app/leads/{lead['id']}/activities", headers=headers, json={"note": "Called, interested"})
    client.post(f"/api/app/leads/{lead['id']}/activities", headers=headers, json={"note": "Sent quote"})
    activities = client.get(f"/api/app/leads/{lead['id']}/activities", headers=headers).json()
    assert [a["note"] for a in activities] == ["Called, interested", "Sent quote"]


def test_filter_by_stage(owner):
    client, headers = owner
    a = client.post("/api/app/leads", headers=headers, json={"name": "A Co"}).json()
    client.post("/api/app/leads", headers=headers, json={"name": "B Co"})
    client.patch(f"/api/app/leads/{a['id']}", headers=headers, json={"stage": "qualified"})
    new_only = client.get("/api/app/leads", headers=headers, params={"stage": "new"}).json()
    assert {l["name"] for l in new_only} == {"B Co"}


def test_lead_cannot_be_seen_by_another_organization(client_for):
    owner_a, headers_a = client_for("owner", org="org_a")
    owner_b, headers_b = client_for("owner", org="org_b")
    lead = owner_a.post("/api/app/leads", headers=headers_a, json={"name": "Org A Lead"}).json()
    assert owner_b.get(f"/api/app/leads/{lead['id']}", headers=headers_b).status_code == 404


@pytest.mark.parametrize("role,allowed", [
    ("owner", True), ("manager", True), ("cashier", True), ("accountant", True),
    ("viewer", False), ("stock_keeper", False),
])
def test_who_may_create_leads(client_for, role, allowed):
    client, headers = client_for(role)
    response = client.post("/api/app/leads", headers=headers, json={"name": "Perm Check"})
    assert (response.status_code == 200) == allowed
