"""Customer feedback / NPS: scoring, auto-ticket on low score, and summary stats."""

import pytest


@pytest.fixture()
def owner(client_for):
    return client_for("owner")


def test_submit_feedback(owner):
    client, headers = owner
    response = client.post("/api/app/feedback", headers=headers, json={"score": 9, "comment": "Great service"})
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 9 and body["follow_up_ticket_id"] is None


def test_low_score_opens_a_follow_up_ticket_automatically(owner):
    client, headers = owner
    response = client.post("/api/app/feedback", headers=headers, json={"score": 3, "comment": "Late delivery"})
    body = response.json()
    assert body["follow_up_ticket_id"] is not None
    ticket = client.get(f"/api/app/tickets/{body['follow_up_ticket_id']}", headers=headers).json()
    assert ticket["priority"] == "high" and ticket["category"] == "feedback"


def test_passive_and_promoter_scores_do_not_open_tickets(owner):
    client, headers = owner
    for score in (7, 8, 10):
        body = client.post("/api/app/feedback", headers=headers, json={"score": score}).json()
        assert body["follow_up_ticket_id"] is None


def test_summary_computes_nps_buckets(owner):
    client, headers = owner
    for score in (9, 10, 7, 3, 2):
        client.post("/api/app/feedback", headers=headers, json={"score": score})
    summary = client.get("/api/app/feedback/summary", headers=headers).json()
    assert summary["count"] == 5
    assert summary["promoters"] == 2 and summary["passives"] == 1 and summary["detractors"] == 2
    assert summary["nps"] == 0.0  # (2 - 2) / 5 * 100


def test_summary_with_no_feedback_is_null_not_zero(owner):
    client, headers = owner
    summary = client.get("/api/app/feedback/summary", headers=headers).json()
    assert summary == {"count": 0, "average_score": None, "nps": None, "promoters": 0, "passives": 0, "detractors": 0}


def test_filter_by_max_score(owner):
    client, headers = owner
    client.post("/api/app/feedback", headers=headers, json={"score": 9})
    client.post("/api/app/feedback", headers=headers, json={"score": 2})
    low = client.get("/api/app/feedback", headers=headers, params={"max_score": 5}).json()
    assert [f["score"] for f in low] == [2]


def test_unknown_customer_is_rejected(owner):
    client, headers = owner
    response = client.post("/api/app/feedback", headers=headers, json={"score": 8, "customer_id": "not-real"})
    assert response.status_code == 404


@pytest.mark.parametrize("role,allowed", [
    ("owner", True), ("manager", True), ("cashier", True), ("accountant", True),
    ("viewer", False), ("stock_keeper", False),
])
def test_who_may_submit_feedback(client_for, role, allowed):
    client, headers = client_for(role)
    response = client.post("/api/app/feedback", headers=headers, json={"score": 8})
    assert (response.status_code == 200) == allowed
