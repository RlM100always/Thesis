"""The Approval Inbox: an expense over the threshold waits for the owner instead
of posting immediately, and approving it posts exactly what would have posted
without the rule."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

NOW = datetime.now(timezone.utc)


class Shop:
    def __init__(self, client, headers):
        self.c, self.h = client, headers

    def post(self, path, body, status=200):
        r = self.c.post(f"/api/app{path}", headers=self.h, json=body)
        assert r.status_code == status, (path, r.status_code, r.text)
        return r.json()

    def get(self, path, **params):
        r = self.c.get(f"/api/app{path}", headers=self.h, params=params)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    def expense(self, amount, status=None):
        r = self.c.post("/api/app/expenses", headers=self.h, json={
            "category": "ভাড়া", "amount": str(amount), "payment_method": "cash", "incurred_at": NOW.isoformat()})
        if status is not None:
            assert r.status_code == status, r.text
        return r

    def trial_balance(self):
        return self.get("/accounting/trial-balance")


@pytest.fixture()
def owner(client_for):
    client, headers = client_for("owner")
    return Shop(client, headers)


def test_a_small_expense_posts_immediately_with_no_approval_needed(owner):
    r = owner.expense("100", status=200)
    body = r.json()
    assert body["id"] and Decimal(body["amount"]) == 100
    assert owner.get("/approvals", status="all") == []


def test_a_large_expense_by_a_manager_is_held_for_the_owner(client_for):
    manager, headers = client_for("manager")
    shop = Shop(manager, headers)
    r = shop.expense("6000", status=202)
    body = r.json()
    assert body["status"] == "pending_approval" and body["needs_role"] == "owner"
    tb = {row["code"]: row for row in shop.trial_balance()["accounts"]}
    assert Decimal(tb["5900"]["balance"]) == 0                    # nothing posted yet

    pending = shop.get("/approvals")
    assert len(pending) == 1 and pending[0]["kind"] == "expense_amount" and Decimal(pending[0]["amount"]) == 6000
    assert pending[0]["requested_by"] == "manager A"


def test_the_owner_can_still_post_the_same_large_expense_directly(owner):
    r = owner.expense("6000", status=200)                          # owner meets the rule's own role
    assert Decimal(r.json()["amount"]) == 6000
    assert owner.get("/approvals") == []


def test_approving_posts_the_expense_exactly_as_the_direct_route_would(client_for):
    manager, mheaders = client_for("manager")
    owner_client, oheaders = client_for("owner")
    shop_m, shop_o = Shop(manager, mheaders), Shop(owner_client, oheaders)
    shop_m.expense("7000", status=202)
    request_id = shop_o.get("/approvals")[0]["id"]

    result = shop_o.post(f"/approvals/{request_id}/approve", {"reason": "ঠিক আছে"})
    assert result["status"] == "approved" and result["result_reference_id"]
    tb = {row["code"]: row for row in shop_o.trial_balance()["accounts"]}
    assert Decimal(tb["5900"]["balance"]) == 7000 and Decimal(tb["1000"]["balance"]) == -7000

    decided = shop_o.get("/approvals", status="approved")[0]
    assert decided["status"] == "approved" and decided["decided_by"] == "owner A" and decided["decision_reason"] == "ঠিক আছে"
    assert shop_o.get("/approvals") == []                          # no longer pending


def test_rejecting_needs_a_reason_and_posts_nothing(client_for):
    manager, mheaders = client_for("manager")
    owner_client, oheaders = client_for("owner")
    shop_m, shop_o = Shop(manager, mheaders), Shop(owner_client, oheaders)
    shop_m.expense("8000", status=202)
    request_id = shop_o.get("/approvals")[0]["id"]

    bad = owner_client.post(f"/api/app/approvals/{request_id}/reject", headers=oheaders, json={})
    assert bad.status_code == 422

    result = shop_o.post(f"/approvals/{request_id}/reject", {"reason": "বাজেটের বাইরে"})
    assert result["status"] == "rejected"
    tb = {row["code"]: row for row in shop_o.trial_balance()["accounts"]}
    assert Decimal(tb["5900"]["balance"]) == 0
    assert shop_o.get("/approvals", status="rejected")[0]["decision_reason"] == "বাজেটের বাইরে"


def test_a_decided_request_cannot_be_decided_again(client_for):
    manager, mheaders = client_for("manager")
    owner_client, oheaders = client_for("owner")
    shop_m, shop_o = Shop(manager, mheaders), Shop(owner_client, oheaders)
    shop_m.expense("9000", status=202)
    request_id = shop_o.get("/approvals")[0]["id"]
    shop_o.post(f"/approvals/{request_id}/approve", {})
    again = owner_client.post(f"/api/app/approvals/{request_id}/approve", headers=oheaders, json={})
    assert again.status_code == 409


def test_the_owner_can_change_the_threshold_and_who_must_approve(client_for):
    owner_client, oheaders = client_for("owner")
    manager, mheaders = client_for("manager")
    shop_o, shop_m = Shop(owner_client, oheaders), Shop(manager, mheaders)

    updated = owner_client.patch("/api/app/approvals/rules/expense_amount", headers=oheaders,
                                  json={"threshold": "1000", "approver_role": "manager"}).json()
    assert Decimal(updated["threshold"]) == 1000 and updated["approver_role"] == "manager"

    # Below the new, lower threshold: still posts immediately even for a role with no special standing.
    cashier, cheaders = client_for("cashier")
    # cashier cannot create expenses at all (no expenses:write) -- use accountant instead
    accountant, aheaders = client_for("accountant")
    shop_a = Shop(accountant, aheaders)
    r = shop_a.expense("1200", status=202)                          # accountant ranks below manager
    assert r.json()["needs_role"] == "manager"

    # A manager may now approve it themselves without the owner.
    request_id = shop_m.get("/approvals")[0]["id"]
    result = shop_m.post(f"/approvals/{request_id}/approve", {})
    assert result["status"] == "approved"


def test_simulate_reports_whether_a_rule_would_fire(client_for):
    owner, oheaders = client_for("owner")
    below = owner.post("/api/app/approvals/rules/simulate", headers=oheaders,
                       json={"kind": "expense_amount", "amount": "100", "requester_role": "cashier"}).json()
    assert below["requires_approval"] is False

    above = owner.post("/api/app/approvals/rules/simulate", headers=oheaders,
                       json={"kind": "expense_amount", "amount": "6000", "requester_role": "cashier"}).json()
    assert above["requires_approval"] is True and above["approver_role"] == "owner"


def test_simulate_defaults_to_the_callers_own_role(client_for):
    accountant, aheaders = client_for("accountant")
    result = accountant.post("/api/app/approvals/rules/simulate", headers=aheaders,
                             json={"kind": "expense_amount", "amount": "6000"}).json()
    assert result["requires_approval"] is True  # accountant ranks below owner


def test_simulate_rejects_an_unknown_role(client_for):
    owner, oheaders = client_for("owner")
    response = owner.post("/api/app/approvals/rules/simulate", headers=oheaders,
                          json={"kind": "expense_amount", "amount": "100", "requester_role": "ghost"})
    assert response.status_code == 422


def test_turning_a_rule_off_lets_everything_through(client_for):
    owner_client, oheaders = client_for("owner")
    manager, mheaders = client_for("manager")
    owner_client.patch("/api/app/approvals/rules/expense_amount", headers=oheaders, json={"active": False})
    Shop(manager, mheaders).expense("50000", status=200)


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", True), ("viewer", True), ("cashier", False), ("stock_keeper", False)])
def test_who_may_read_the_inbox(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/approvals", headers=headers).status_code == 200) == allowed


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("viewer", False), ("cashier", False)])
def test_who_may_decide(client_for, role, allowed):
    owner_client, oheaders = client_for("owner")
    Shop(owner_client, oheaders).expense("100")  # ensure the org exists / warm up, harmless
    manager, mheaders = client_for("manager")
    Shop(manager, mheaders).expense("9500", status=202)
    request_id = Shop(owner_client, oheaders).get("/approvals")[0]["id"]
    client, headers = client_for(role)
    r = client.post(f"/api/app/approvals/{request_id}/approve", headers=headers, json={})
    assert (r.status_code == 200) == allowed


def test_another_business_cannot_see_or_decide_our_request(client_for):
    manager, mheaders = client_for("manager")
    Shop(manager, mheaders).expense("9999", status=202)
    other, oheaders = client_for("owner", org="org_b")
    assert other.get("/api/app/approvals", headers=oheaders).json() == []
    owner_client, oh = client_for("owner")
    request_id = Shop(owner_client, oh).get("/approvals")[0]["id"]
    cross = other.post(f"/api/app/approvals/{request_id}/approve", headers=oheaders, json={})
    assert cross.status_code == 404
