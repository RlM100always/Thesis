"""Staff lifecycle: invite → set password → sign in, role changes, and account safety."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import api.auth_routes
from api.domain_models import AuditLog, Membership, User

INVITE = {"email": "Newhire@Shop.example", "display_name": "New Hire", "role": "cashier"}
PASSWORD = "a fresh long password"


@pytest.fixture(autouse=True)
def _clear_lockouts():
    api.auth_routes._failed_logins.clear()
    yield
    api.auth_routes._failed_logins.clear()


@pytest.fixture()
def anonymous(make_app):
    """Real authentication path (nobody is pre-authenticated)."""
    return TestClient(make_app())


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def invite(client, headers, **overrides):
    return client.post("/api/app/staff", headers=headers, json={**INVITE, **overrides})


# ── invite → set password ────────────────────────────────────────────────────

def test_invite_new_person_returns_a_one_time_setup_token(client_for):
    client, headers = client_for("owner")
    response = invite(client, headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["setup_token"] and body["setup_expires_at"]
    assert body["pending_setup"] is True and body["email"] == "newhire@shop.example"


def test_setup_token_is_stored_only_as_a_digest(client_for, engine):
    client, headers = client_for("owner")
    raw = invite(client, headers).json()["setup_token"]
    with Session(engine) as db:
        stored = db.scalar(select(User.setup_token_hash).where(User.email == "newhire@shop.example"))
    assert stored and stored != raw and raw not in stored


def test_invited_person_can_set_password_and_work_within_their_role(client_for, anonymous, world):
    owner, headers = client_for("owner")
    raw = invite(owner, headers).json()["setup_token"]

    done = anonymous.post("/api/app/auth/set-password", json={"token": raw, "password": PASSWORD})
    assert done.status_code == 200, done.text
    access = done.json()["access_token"]

    # Signed in, and limited to what a cashier may do.
    org = {"X-Organization-ID": world["org_a"], **bearer(access)}
    assert anonymous.get("/api/app/products", headers=org).status_code == 200
    assert anonymous.get("/api/app/dashboard", headers=org).status_code == 403
    # The same credentials work through the normal login.
    login = anonymous.post("/api/app/auth/login", json={"email": "newhire@shop.example", "password": PASSWORD})
    assert login.status_code == 200


def test_setup_token_cannot_be_used_twice(client_for, anonymous):
    owner, headers = client_for("owner")
    raw = invite(owner, headers).json()["setup_token"]
    assert anonymous.post("/api/app/auth/set-password", json={"token": raw, "password": PASSWORD}).status_code == 200
    again = anonymous.post("/api/app/auth/set-password", json={"token": raw, "password": "someone else's pw"})
    assert again.status_code == 400


def test_expired_setup_token_is_rejected(client_for, anonymous, engine):
    owner, headers = client_for("owner")
    raw = invite(owner, headers).json()["setup_token"]
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "newhire@shop.example"))
        user.setup_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert anonymous.post("/api/app/auth/set-password", json={"token": raw, "password": PASSWORD}).status_code == 400


def test_unknown_token_and_short_password_are_rejected(client_for, anonymous):
    owner, headers = client_for("owner")
    raw = invite(owner, headers).json()["setup_token"]
    assert anonymous.post("/api/app/auth/set-password",
                          json={"token": "x" * 43, "password": PASSWORD}).status_code == 400
    assert anonymous.post("/api/app/auth/set-password",
                          json={"token": raw, "password": "short"}).status_code == 422


def test_inviting_someone_with_an_account_adds_them_without_a_token(client_for, anonymous):
    registered = anonymous.post("/api/app/auth/register", json={
        "email": "newhire@shop.example", "password": PASSWORD, "display_name": "Already Here"})
    assert registered.status_code == 200
    owner, headers = client_for("owner")
    body = invite(owner, headers).json()
    assert body["setup_token"] is None and body["pending_setup"] is False


def test_inviting_the_same_person_twice_is_a_conflict(client_for):
    owner, headers = client_for("owner")
    assert invite(owner, headers).status_code == 200
    assert invite(owner, headers).status_code == 409


@pytest.mark.parametrize("role", ["manager", "accountant", "cashier", "viewer"])
def test_only_owner_can_invite_or_change_staff(client_for, world, role):
    client, headers = client_for(role)
    assert invite(client, headers).status_code == 403
    membership_id = "any"
    assert client.patch(f"/api/app/staff/{membership_id}", headers=headers, json={"active": False}).status_code == 403
    assert client.post(f"/api/app/staff/{membership_id}/setup-link", headers=headers).status_code == 403


# ── role changes and the last owner ──────────────────────────────────────────

def membership_id_of(client, headers, email):
    return next(s["membership_id"] for s in client.get("/api/app/staff", headers=headers).json() if s["email"] == email)


def test_owner_can_change_a_role_and_it_is_audited(client_for, engine, world):
    client, headers = client_for("owner")
    target = membership_id_of(client, headers, "cashier@a.example")
    response = client.patch(f"/api/app/staff/{target}", headers=headers, json={"role": "stock_keeper"})
    assert response.status_code == 200 and response.json()["role"] == "stock_keeper"
    with Session(engine) as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "staff.role_changed"))
    assert entry.organization_id == world["org_a"] and "stock_keeper" in entry.metadata_json


def test_the_last_active_owner_cannot_be_demoted_or_deactivated(client_for):
    client, headers = client_for("owner")
    me = membership_id_of(client, headers, "owner@a.example")
    assert client.patch(f"/api/app/staff/{me}", headers=headers, json={"role": "manager"}).status_code == 409
    assert client.patch(f"/api/app/staff/{me}", headers=headers, json={"active": False}).status_code == 409


def test_an_owner_can_step_down_once_another_owner_exists(client_for):
    client, headers = client_for("owner")
    me = membership_id_of(client, headers, "owner@a.example")
    manager = membership_id_of(client, headers, "manager@a.example")
    assert client.patch(f"/api/app/staff/{manager}", headers=headers, json={"role": "owner"}).status_code == 200
    assert client.patch(f"/api/app/staff/{me}", headers=headers, json={"role": "manager"}).status_code == 200


def test_deactivated_person_loses_access_and_can_be_restored(client_for, engine, world):
    owner, headers = client_for("owner")
    target = membership_id_of(owner, headers, "cashier@a.example")
    assert owner.patch(f"/api/app/staff/{target}", headers=headers, json={"active": False}).status_code == 200
    cashier, cashier_headers = client_for("cashier")
    assert cashier.get("/api/app/products", headers=cashier_headers).status_code == 404
    assert owner.patch(f"/api/app/staff/{target}", headers=headers, json={"active": True}).status_code == 200
    assert cashier.get("/api/app/products", headers=cashier_headers).status_code == 200


def test_empty_update_is_rejected(client_for):
    client, headers = client_for("owner")
    target = membership_id_of(client, headers, "cashier@a.example")
    assert client.patch(f"/api/app/staff/{target}", headers=headers, json={}).status_code == 422


def test_staff_of_another_business_cannot_be_touched(client_for):
    owner_a, headers_a = client_for("owner", org="org_a")
    target = membership_id_of(owner_a, headers_a, "cashier@a.example")
    owner_b, headers_b = client_for("owner", org="org_b")
    assert owner_b.patch(f"/api/app/staff/{target}", headers=headers_b, json={"active": False}).status_code == 404
    assert owner_b.post(f"/api/app/staff/{target}/setup-link", headers=headers_b).status_code == 404


# ── owner-issued setup links (and the account-hijack rule) ───────────────────

def test_setup_link_for_a_pending_invite(client_for):
    client, headers = client_for("owner")
    invite(client, headers)
    target = membership_id_of(client, headers, "newhire@shop.example")
    body = client.post(f"/api/app/staff/{target}/setup-link", headers=headers).json()
    assert body["setup_token"]


def test_setup_link_is_refused_for_your_own_account(client_for):
    client, headers = client_for("owner")
    me = membership_id_of(client, headers, "owner@a.example")
    assert client.post(f"/api/app/staff/{me}/setup-link", headers=headers).status_code == 409


def test_owner_cannot_reset_a_password_for_someone_who_belongs_to_another_business(client_for, engine, world, anonymous):
    """Otherwise the owner of shop A could take over a person's account in shop B."""
    with Session(engine) as db:
        colleague = db.scalar(select(User).where(User.email == "manager@a.example"))
        colleague.password_hash = "set"  # has an established password
        db.add(Membership(organization_id=world["org_b"], user_id=colleague.id, role="cashier"))
        db.commit()
    owner_a, headers_a = client_for("owner")
    target = membership_id_of(owner_a, headers_a, "manager@a.example")
    refused = owner_a.post(f"/api/app/staff/{target}/setup-link", headers=headers_a)
    assert refused.status_code == 409


def test_owner_can_reset_a_password_for_someone_who_belongs_only_to_this_business(client_for, engine, anonymous):
    with Session(engine) as db:
        db.scalar(select(User).where(User.email == "cashier@a.example")).password_hash = "set"
        db.commit()
    owner, headers = client_for("owner")
    target = membership_id_of(owner, headers, "cashier@a.example")
    body = owner.post(f"/api/app/staff/{target}/setup-link", headers=headers).json()
    done = anonymous.post("/api/app/auth/set-password", json={"token": body["setup_token"], "password": PASSWORD})
    assert done.status_code == 200


# ── change your own password ─────────────────────────────────────────────────

@pytest.fixture()
def signed_in(anonymous):
    tokens = anonymous.post("/api/app/auth/register", json={
        "email": "me@shop.example", "password": PASSWORD, "display_name": "Me Myself"}).json()
    return tokens


def test_wrong_current_password_is_rejected_without_ending_the_session(anonymous, signed_in):
    response = anonymous.post("/api/app/auth/change-password", headers=bearer(signed_in["access_token"]),
                              json={"current_password": "not it at all", "new_password": "brand new password"})
    assert response.status_code == 400  # a 401 would make the client sign the user out
    assert anonymous.get("/api/app/auth/me", headers=bearer(signed_in["access_token"])).status_code == 200


def test_changing_password_signs_out_other_sessions_but_keeps_this_one(anonymous, signed_in):
    response = anonymous.post("/api/app/auth/change-password", headers=bearer(signed_in["access_token"]),
                              json={"current_password": PASSWORD, "new_password": "brand new password"})
    assert response.status_code == 200
    fresh = response.json()
    assert anonymous.get("/api/app/auth/me", headers=bearer(signed_in["access_token"])).status_code == 401
    assert anonymous.post("/api/app/auth/refresh", json={"refresh_token": signed_in["refresh_token"]}).status_code == 401
    assert anonymous.get("/api/app/auth/me", headers=bearer(fresh["access_token"])).status_code == 200
    old = anonymous.post("/api/app/auth/login", json={"email": "me@shop.example", "password": PASSWORD})
    new = anonymous.post("/api/app/auth/login", json={"email": "me@shop.example", "password": "brand new password"})
    assert old.status_code == 401 and new.status_code == 200


def test_repeated_wrong_current_password_locks_the_change_form(anonymous, signed_in):
    for _ in range(5):
        anonymous.post("/api/app/auth/change-password", headers=bearer(signed_in["access_token"]),
                       json={"current_password": "wrong wrong", "new_password": "brand new password"})
    locked = anonymous.post("/api/app/auth/change-password", headers=bearer(signed_in["access_token"]),
                            json={"current_password": PASSWORD, "new_password": "brand new password"})
    assert locked.status_code == 429
