"""Staff advances: issue, repay, over-repayment guard, and settlement."""

import pytest


def _cashier_user_id(client_for):
    owner, headers = client_for("owner")
    staff = owner.get("/api/app/staff", headers=headers).json()
    return next(s["user_id"] for s in staff if s["role"] == "cashier")


def test_issue_advance_and_see_it_outstanding(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    created = owner.post("/api/app/advances", headers=headers, json={
        "user_id": cashier_user_id, "amount": "5000", "reason": "medical emergency",
    })
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "outstanding" and body["outstanding_amount"] == 5000 or float(body["outstanding_amount"]) == 5000


def test_cashier_sees_own_advance(client_for):
    owner, oheaders = client_for("owner")
    cashier, cheaders = client_for("cashier")
    cashier_user_id = _cashier_user_id(client_for)
    owner.post("/api/app/advances", headers=oheaders, json={"user_id": cashier_user_id, "amount": "5000"})
    mine = cashier.get("/api/app/advances/me", headers=cheaders).json()
    assert len(mine) == 1


def test_partial_repayment_reduces_outstanding(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    advance = owner.post("/api/app/advances", headers=headers, json={
        "user_id": cashier_user_id, "amount": "1000",
    }).json()
    repaid = owner.post(f"/api/app/advances/{advance['id']}/repay", headers=headers, json={"amount": "400"})
    assert repaid.status_code == 200
    assert float(repaid.json()["outstanding_amount"]) == 600
    assert repaid.json()["status"] == "outstanding"


def test_full_repayment_settles_it(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    advance = owner.post("/api/app/advances", headers=headers, json={
        "user_id": cashier_user_id, "amount": "1000",
    }).json()
    owner.post(f"/api/app/advances/{advance['id']}/repay", headers=headers, json={"amount": "600"})
    final = owner.post(f"/api/app/advances/{advance['id']}/repay", headers=headers, json={"amount": "400"})
    assert final.json()["status"] == "settled" and float(final.json()["outstanding_amount"]) == 0


def test_cannot_repay_more_than_outstanding(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    advance = owner.post("/api/app/advances", headers=headers, json={
        "user_id": cashier_user_id, "amount": "1000",
    }).json()
    over = owner.post(f"/api/app/advances/{advance['id']}/repay", headers=headers, json={"amount": "1500"})
    assert over.status_code == 422


def test_cannot_repay_a_settled_advance(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    advance = owner.post("/api/app/advances", headers=headers, json={
        "user_id": cashier_user_id, "amount": "500",
    }).json()
    owner.post(f"/api/app/advances/{advance['id']}/repay", headers=headers, json={"amount": "500"})
    again = owner.post(f"/api/app/advances/{advance['id']}/repay", headers=headers, json={"amount": "100"})
    assert again.status_code == 409


def test_list_filters_by_status(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    a = owner.post("/api/app/advances", headers=headers, json={"user_id": cashier_user_id, "amount": "500"}).json()
    owner.post("/api/app/advances", headers=headers, json={"user_id": cashier_user_id, "amount": "700"})
    owner.post(f"/api/app/advances/{a['id']}/repay", headers=headers, json={"amount": "500"})
    outstanding = owner.get("/api/app/advances", headers=headers, params={"status": "outstanding"}).json()
    settled = owner.get("/api/app/advances", headers=headers, params={"status": "settled"}).json()
    assert len(outstanding) == 1 and len(settled) == 1


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_issue_advances(client_for, role, allowed):
    client, headers = client_for(role)
    cashier_user_id = _cashier_user_id(client_for)
    response = client.post("/api/app/advances", headers=headers, json={"user_id": cashier_user_id, "amount": "500"})
    assert (response.status_code == 200) == allowed


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("cashier", False)])
def test_who_may_view_team_advances(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/advances", headers=headers).status_code == 200) == allowed
