"""Attendance: self-service check-in/out, team visibility, and non-destructive corrections."""

from datetime import datetime, timedelta, timezone

import pytest


def test_check_in_and_check_out(client_for):
    cashier, headers = client_for("cashier")
    checked_in = cashier.post("/api/app/attendance/check-in", headers=headers, json={})
    assert checked_in.status_code == 200
    assert checked_in.json()["check_out_at"] is None

    checked_out = cashier.post("/api/app/attendance/check-out", headers=headers)
    assert checked_out.status_code == 200
    assert checked_out.json()["check_out_at"] is not None


def test_cannot_check_in_twice(client_for):
    cashier, headers = client_for("cashier")
    cashier.post("/api/app/attendance/check-in", headers=headers, json={})
    second = cashier.post("/api/app/attendance/check-in", headers=headers, json={})
    assert second.status_code == 409


def test_cannot_check_out_without_checking_in(client_for):
    cashier, headers = client_for("cashier")
    assert cashier.post("/api/app/attendance/check-out", headers=headers).status_code == 409


def test_my_attendance_shows_own_history(client_for):
    cashier, headers = client_for("cashier")
    cashier.post("/api/app/attendance/check-in", headers=headers, json={})
    cashier.post("/api/app/attendance/check-out", headers=headers)
    history = cashier.get("/api/app/attendance/me", headers=headers).json()
    assert len(history) == 1


@pytest.mark.parametrize("role,allowed", [
    ("owner", True), ("manager", True), ("accountant", False), ("cashier", False), ("stock_keeper", False),
])
def test_who_may_view_team_attendance(client_for, role, allowed):
    client, headers = client_for(role)
    assert (client.get("/api/app/attendance", headers=headers).status_code == 200) == allowed


def test_correction_adds_a_new_record_without_touching_any_original(client_for):
    cashier, cheaders = client_for("cashier")
    owner, oheaders = client_for("owner")
    cashier.post("/api/app/attendance/check-in", headers=cheaders, json={})
    cashier.post("/api/app/attendance/check-out", headers=cheaders)
    original = cashier.get("/api/app/attendance/me", headers=cheaders).json()[0]

    cashier_user_id = original["user_id"]
    now = datetime.now(timezone.utc)
    correction = owner.post("/api/app/attendance/correct", headers=oheaders, json={
        "user_id": cashier_user_id,
        "check_in_at": (now - timedelta(hours=2)).isoformat(),
        "check_out_at": now.isoformat(),
        "note": "Forgot to punch in on time",
    })
    assert correction.status_code == 200
    assert correction.json()["source"] == "manager_correction"

    all_records = owner.get("/api/app/attendance", headers=oheaders, params={"user_id": cashier_user_id}).json()
    assert len(all_records) == 2
    unchanged_original = next(r for r in all_records if r["id"] == original["id"])
    assert unchanged_original["check_in_at"] == original["check_in_at"]


def test_correction_rejects_checkout_before_checkin(client_for):
    owner, headers = client_for("owner")
    now = datetime.now(timezone.utc)
    response = owner.post("/api/app/attendance/correct", headers=headers, json={
        "user_id": "whoever", "check_in_at": now.isoformat(),
        "check_out_at": (now - timedelta(hours=1)).isoformat(), "note": "bad data",
    })
    assert response.status_code == 422


@pytest.mark.parametrize("role,allowed", [("owner", True), ("manager", True), ("accountant", False), ("cashier", False)])
def test_who_may_correct_attendance(client_for, role, allowed):
    client, headers = client_for(role)
    now = datetime.now(timezone.utc)
    response = client.post("/api/app/attendance/correct", headers=headers, json={
        "user_id": "someone", "check_in_at": now.isoformat(), "note": "fix",
    })
    assert (response.status_code == 200) == allowed
