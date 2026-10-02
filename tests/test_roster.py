"""Roster: shift planning, overlap guard, and visibility rules."""

from datetime import date

import pytest


def _cashier_user_id(client_for):
    """The seeded cashier's user id, via a round-trip through /staff."""
    owner, headers = client_for("owner")
    staff = owner.get("/api/app/staff", headers=headers).json()
    return next(s["user_id"] for s in staff if s["role"] == "cashier")


def test_create_shift_and_see_it_in_my_roster(client_for, world):
    owner, oheaders = client_for("owner")
    cashier, cheaders = client_for("cashier")
    cashier_user_id = _cashier_user_id(client_for)
    created = owner.post("/api/app/roster", headers=oheaders, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "09:00", "end_time": "17:00",
    })
    assert created.status_code == 200
    mine = cashier.get("/api/app/roster/me", headers=cheaders).json()
    assert len(mine) == 1 and mine[0]["start_time"] == "09:00"


def test_end_before_start_is_rejected(client_for, world):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    response = owner.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "17:00", "end_time": "09:00",
    })
    assert response.status_code == 422


def test_overlapping_shift_for_the_same_person_is_rejected(client_for, world):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    owner.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "09:00", "end_time": "17:00",
    })
    overlap = owner.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "16:00", "end_time": "20:00",
    })
    assert overlap.status_code == 409

    non_overlap = owner.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "17:00", "end_time": "20:00",
    })
    assert non_overlap.status_code == 200


def test_shift_creation_notifies_the_assigned_person(client_for, world):
    owner, oheaders = client_for("owner")
    cashier, cheaders = client_for("cashier")
    cashier_user_id = _cashier_user_id(client_for)
    owner.post("/api/app/roster", headers=oheaders, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "09:00", "end_time": "17:00",
    })
    notes = cashier.get("/api/app/notifications", headers=cheaders).json()
    assert any(n["category"] == "staff" for n in notes)


def test_delete_shift(client_for, world):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    shift = owner.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "09:00", "end_time": "17:00",
    }).json()
    deleted = owner.delete(f"/api/app/roster/{shift['id']}", headers=headers)
    assert deleted.status_code == 200
    assert owner.get("/api/app/roster", headers=headers).json() == []


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_create_shifts(client_for, world, role, allowed):
    client, headers = client_for(role)
    cashier_user_id = _cashier_user_id(client_for)
    response = client.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": world["branch_a"],
        "shift_date": "2026-10-05", "start_time": "09:00", "end_time": "17:00",
    })
    assert (response.status_code == 200) == allowed


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_view_team_roster(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/roster", headers=headers).status_code == 200) == allowed


def test_unknown_branch_is_rejected(client_for):
    owner, headers = client_for("owner")
    cashier_user_id = _cashier_user_id(client_for)
    response = owner.post("/api/app/roster", headers=headers, json={
        "user_id": cashier_user_id, "branch_id": "not-real",
        "shift_date": "2026-10-05", "start_time": "09:00", "end_time": "17:00",
    })
    assert response.status_code == 404
