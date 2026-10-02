"""Leave: request, approve/reject, cancel, and visibility rules."""

from datetime import date, timedelta

import pytest

TODAY = date(2026, 10, 1)


def _dates(offset=5, span=2):
    start = TODAY + timedelta(days=offset)
    return start.isoformat(), (start + timedelta(days=span)).isoformat()


def test_request_leave_and_see_it_in_my_leave(client_for):
    cashier, headers = client_for("cashier")
    start, end = _dates()
    created = cashier.post("/api/app/leave", headers=headers,
                           json={"start_date": start, "end_date": end, "reason": "family event"})
    assert created.status_code == 200 and created.json()["status"] == "pending"
    mine = cashier.get("/api/app/leave/me", headers=headers).json()
    assert len(mine) == 1


def test_end_before_start_is_rejected(client_for):
    cashier, headers = client_for("cashier")
    start, _ = _dates()
    response = cashier.post("/api/app/leave", headers=headers, json={
        "start_date": start, "end_date": (TODAY).isoformat(),
    })
    assert response.status_code == 422


def test_owner_approves_a_leave_request(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    start, end = _dates()
    leave = cashier.post("/api/app/leave", headers=cheaders, json={"start_date": start, "end_date": end}).json()
    decided = owner.post(f"/api/app/leave/{leave['id']}/decide", headers=oheaders, json={"status": "approved"})
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved" and decided.json()["decided_by_user_id"]


def test_cannot_decide_the_same_request_twice(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    start, end = _dates()
    leave = cashier.post("/api/app/leave", headers=cheaders, json={"start_date": start, "end_date": end}).json()
    owner.post(f"/api/app/leave/{leave['id']}/decide", headers=oheaders, json={"status": "approved"})
    second = owner.post(f"/api/app/leave/{leave['id']}/decide", headers=oheaders, json={"status": "rejected"})
    assert second.status_code == 409


def test_cancel_only_works_while_pending(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    start, end = _dates()
    leave = cashier.post("/api/app/leave", headers=cheaders, json={"start_date": start, "end_date": end}).json()
    owner.post(f"/api/app/leave/{leave['id']}/decide", headers=oheaders, json={"status": "approved"})
    cancelled = cashier.post(f"/api/app/leave/{leave['id']}/cancel", headers=cheaders)
    assert cancelled.status_code == 409


def test_pending_leave_can_be_cancelled_by_its_owner(client_for):
    cashier, headers = client_for("cashier")
    start, end = _dates()
    leave = cashier.post("/api/app/leave", headers=headers, json={"start_date": start, "end_date": end}).json()
    cancelled = cashier.post(f"/api/app/leave/{leave['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


def test_leave_request_notifies_owner_and_manager(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    start, end = _dates()
    cashier.post("/api/app/leave", headers=cheaders, json={"start_date": start, "end_date": end})
    notes = owner.get("/api/app/notifications", headers=oheaders).json()
    assert any(n["category"] == "staff" for n in notes)


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_view_team_leave(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/leave", headers=headers).status_code == 200) == allowed


def test_cannot_act_on_someone_elses_pending_leave(client_for):
    cashier, cheaders = client_for("cashier")
    manager, mheaders = client_for("manager")
    start, end = _dates()
    leave = cashier.post("/api/app/leave", headers=cheaders, json={"start_date": start, "end_date": end}).json()
    assert manager.post(f"/api/app/leave/{leave['id']}/cancel", headers=mheaders).status_code == 404
