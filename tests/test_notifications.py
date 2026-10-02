"""Notification Center: own-notifications listing, read/snooze, and the ticket trigger."""

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def owner(client_for):
    return client_for("owner")


def test_a_high_priority_ticket_notifies_owner_and_manager(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    manager, mheaders = client_for("manager")
    cashier.post("/api/app/tickets", headers=cheaders,
                json={"subject": "Customer very upset", "priority": "urgent"})

    owner_notes = owner.get("/api/app/notifications", headers=oheaders).json()
    assert any(n["category"] == "action_required" and n["severity"] == "critical" for n in owner_notes)
    manager_notes = manager.get("/api/app/notifications", headers=mheaders).json()
    assert len(manager_notes) == 1


def test_normal_priority_ticket_does_not_notify(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Routine question"})
    assert owner.get("/api/app/notifications", headers=oheaders).json() == []


def test_cashier_does_not_see_owners_notifications(client_for):
    cashier, cheaders = client_for("cashier")
    cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Urgent thing", "priority": "urgent"})
    assert cashier.get("/api/app/notifications", headers=cheaders).json() == []


def test_mark_read_and_unread_count(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Urgent thing", "priority": "urgent"})

    before = owner.get("/api/app/notifications/unread-count", headers=oheaders).json()
    assert before["unread_count"] == 1
    notification = owner.get("/api/app/notifications", headers=oheaders).json()[0]
    owner.post(f"/api/app/notifications/{notification['id']}/read", headers=oheaders)
    after = owner.get("/api/app/notifications/unread-count", headers=oheaders).json()
    assert after["unread_count"] == 0


def test_mark_all_read(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    for _ in range(3):
        cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Urgent thing", "priority": "urgent"})
    result = owner.post("/api/app/notifications/read-all", headers=oheaders).json()
    assert result["marked_read"] == 3
    assert owner.get("/api/app/notifications/unread-count", headers=oheaders).json()["unread_count"] == 0


def test_snooze_hides_from_default_list_until_it_expires(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Urgent thing", "priority": "urgent"})
    notification = owner.get("/api/app/notifications", headers=oheaders).json()[0]

    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    snoozed = owner.post(f"/api/app/notifications/{notification['id']}/snooze", headers=oheaders, json={"until": future})
    assert snoozed.status_code == 200

    assert owner.get("/api/app/notifications", headers=oheaders).json() == []
    assert owner.get("/api/app/notifications", headers=oheaders, params={"include_snoozed": True}).json()


def test_snooze_in_the_past_is_rejected(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Urgent thing", "priority": "urgent"})
    notification = owner.get("/api/app/notifications", headers=oheaders).json()[0]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = owner.post(f"/api/app/notifications/{notification['id']}/snooze", headers=oheaders, json={"until": past})
    assert response.status_code == 422


def test_cannot_act_on_someone_elses_notification(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    manager, mheaders = client_for("manager")
    cashier.post("/api/app/tickets", headers=cheaders, json={"subject": "Urgent thing", "priority": "urgent"})
    owner_notification = owner.get("/api/app/notifications", headers=oheaders).json()[0]
    assert manager.post(f"/api/app/notifications/{owner_notification['id']}/read", headers=mheaders).status_code == 404
