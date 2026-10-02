"""Support tickets: creation, status workflow, assignment, and the conversation thread."""

import pytest


@pytest.fixture()
def owner(client_for):
    return client_for("owner")


def test_create_and_read_a_ticket(owner):
    client, headers = owner
    created = client.post("/api/app/tickets", headers=headers, json={"subject": "Wrong item delivered"})
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "open" and body["priority"] == "normal"

    fetched = client.get(f"/api/app/tickets/{body['id']}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["subject"] == "Wrong item delivered"


def test_list_filters_by_status(owner):
    client, headers = owner
    a = client.post("/api/app/tickets", headers=headers, json={"subject": "AA"}).json()
    client.post("/api/app/tickets", headers=headers, json={"subject": "BB"})
    client.patch(f"/api/app/tickets/{a['id']}", headers=headers, json={"status": "resolved"})

    open_only = client.get("/api/app/tickets", headers=headers, params={"status": "open"}).json()
    assert {t["subject"] for t in open_only} == {"BB"}
    resolved_only = client.get("/api/app/tickets", headers=headers, params={"status": "resolved"}).json()
    assert {t["subject"] for t in resolved_only} == {"AA"}


def test_resolving_sets_resolved_at_and_reopening_clears_it(owner):
    client, headers = owner
    ticket = client.post("/api/app/tickets", headers=headers, json={"subject": "Late delivery"}).json()
    resolved = client.patch(f"/api/app/tickets/{ticket['id']}", headers=headers, json={"status": "resolved"}).json()
    assert resolved["resolved_at"] is not None

    reopened = client.patch(f"/api/app/tickets/{ticket['id']}", headers=headers, json={"status": "open"}).json()
    assert reopened["resolved_at"] is None


def test_conversation_thread_including_internal_notes(owner):
    client, headers = owner
    ticket = client.post("/api/app/tickets", headers=headers, json={"subject": "Refund question"}).json()
    client.post(f"/api/app/tickets/{ticket['id']}/messages", headers=headers, json={"body": "Customer called"})
    client.post(f"/api/app/tickets/{ticket['id']}/messages", headers=headers,
               json={"body": "Checking with warehouse", "internal": True})
    messages = client.get(f"/api/app/tickets/{ticket['id']}/messages", headers=headers).json()
    assert [m["body"] for m in messages] == ["Customer called", "Checking with warehouse"]
    assert [m["internal"] for m in messages] == [False, True]


def test_unknown_customer_or_branch_is_rejected(owner):
    client, headers = owner
    bad_customer = client.post("/api/app/tickets", headers=headers,
                               json={"subject": "XX", "customer_id": "not-real"})
    assert bad_customer.status_code == 404
    bad_branch = client.post("/api/app/tickets", headers=headers, json={"subject": "XX", "branch_id": "not-real"})
    assert bad_branch.status_code == 404


def test_ticket_cannot_be_seen_by_another_organization(client_for):
    owner_a, headers_a = client_for("owner", org="org_a")
    owner_b, headers_b = client_for("owner", org="org_b")
    ticket = owner_a.post("/api/app/tickets", headers=headers_a, json={"subject": "Org A issue"}).json()
    assert owner_b.get(f"/api/app/tickets/{ticket['id']}", headers=headers_b).status_code == 404


@pytest.mark.parametrize("role,allowed", [
    ("owner", True), ("manager", True), ("cashier", True), ("accountant", True),
    ("viewer", False), ("stock_keeper", False),
])
def test_who_may_create_tickets(client_for, role, allowed):
    client, headers = client_for(role)
    response = client.post("/api/app/tickets", headers=headers, json={"subject": "Check"})
    assert (response.status_code == 200) == allowed


def test_viewer_can_read_but_not_write(client_for):
    owner, owner_headers = client_for("owner")
    ticket = owner.post("/api/app/tickets", headers=owner_headers, json={"subject": "Viewer test"}).json()
    viewer, viewer_headers = client_for("viewer")
    assert viewer.get(f"/api/app/tickets/{ticket['id']}", headers=viewer_headers).status_code == 200
    assert viewer.patch(
        f"/api/app/tickets/{ticket['id']}", headers=viewer_headers, json={"status": "closed"}
    ).status_code == 403


def test_nothing_to_change_is_rejected(owner):
    client, headers = owner
    ticket = client.post("/api/app/tickets", headers=headers, json={"subject": "Empty patch"}).json()
    assert client.patch(f"/api/app/tickets/{ticket['id']}", headers=headers, json={}).status_code == 422
