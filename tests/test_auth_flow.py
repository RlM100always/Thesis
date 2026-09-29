"""Register → login → refresh → logout, and the password primitives beneath them."""

import pytest
from fastapi.testclient import TestClient

import api.auth
import api.auth_routes
from api.config import Settings
from api.security import DUMMY_HASH, hash_password, verify_password

CREDENTIALS = {"email": "Owner@Shop.example", "password": "correct horse battery", "display_name": "Shop Owner"}


@pytest.fixture(autouse=True)
def _clear_lockouts():
    api.auth_routes._failed_logins.clear()
    yield
    api.auth_routes._failed_logins.clear()


@pytest.fixture()
def client(make_app):
    """Real authentication path: only the database is overridden."""
    return TestClient(make_app())


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── password primitives ──────────────────────────────────────────────────────

def test_password_hash_verifies_and_is_salted():
    first, second = hash_password("s3cret-pass"), hash_password("s3cret-pass")
    assert first != second
    assert verify_password("s3cret-pass", first)
    assert not verify_password("wrong", first)


def test_missing_or_malformed_hash_never_verifies():
    assert not verify_password("anything", None)
    assert not verify_password("anything", "")
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "md5$1$2$3$4$5")
    assert verify_password("timing-equaliser-not-a-real-password", DUMMY_HASH)


# ── register / login ─────────────────────────────────────────────────────────

def test_register_returns_tokens_that_authenticate(client):
    response = client.post("/api/app/auth/register", json=CREDENTIALS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    assert body["user"]["email"] == "owner@shop.example"  # normalised to lower case
    me = client.get("/api/app/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == "owner@shop.example"


def test_register_never_returns_the_password_hash(client):
    body = client.post("/api/app/auth/register", json=CREDENTIALS).json()
    assert "password" not in str(body).lower().replace("password_reset", "")


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert client.post("/api/app/auth/register", json=CREDENTIALS).status_code == 200
    again = client.post("/api/app/auth/register", json={**CREDENTIALS, "email": "OWNER@shop.example"})
    assert again.status_code == 409


def test_short_password_is_rejected(client):
    assert client.post("/api/app/auth/register", json={**CREDENTIALS, "password": "short"}).status_code == 422


def test_registration_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(api.auth_routes, "get_settings", lambda: Settings(allow_registration=False))
    assert client.post("/api/app/auth/register", json=CREDENTIALS).status_code == 403


def test_login_with_correct_password(client):
    client.post("/api/app/auth/register", json=CREDENTIALS)
    ok = client.post("/api/app/auth/login", json={"email": "owner@shop.example", "password": CREDENTIALS["password"]})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_wrong_password_and_unknown_email_look_identical(client):
    client.post("/api/app/auth/register", json=CREDENTIALS)
    wrong = client.post("/api/app/auth/login", json={"email": "owner@shop.example", "password": "nope-nope"})
    unknown = client.post("/api/app/auth/login", json={"email": "ghost@shop.example", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_repeated_failures_lock_the_account_out(client):
    client.post("/api/app/auth/register", json=CREDENTIALS)
    bad = {"email": "owner@shop.example", "password": "nope-nope"}
    for _ in range(5):
        assert client.post("/api/app/auth/login", json=bad).status_code == 401
    locked = client.post("/api/app/auth/login", json=bad)
    assert locked.status_code == 429 and "Retry-After" in locked.headers
    # Even the correct password is refused while locked out.
    good = {"email": "owner@shop.example", "password": CREDENTIALS["password"]}
    assert client.post("/api/app/auth/login", json=good).status_code == 429


def test_successful_login_clears_the_failure_count(client):
    client.post("/api/app/auth/register", json=CREDENTIALS)
    for _ in range(4):
        client.post("/api/app/auth/login", json={"email": "owner@shop.example", "password": "nope-nope"})
    good = {"email": "owner@shop.example", "password": CREDENTIALS["password"]}
    assert client.post("/api/app/auth/login", json=good).status_code == 200
    for _ in range(4):  # a fresh budget of failures, not 4 + 4
        assert client.post("/api/app/auth/login", json={**good, "password": "nope-nope"}).status_code == 401


# ── token types, refresh, logout ─────────────────────────────────────────────

def test_refresh_token_cannot_authenticate_an_api_call(client):
    tokens = client.post("/api/app/auth/register", json=CREDENTIALS).json()
    assert client.get("/api/app/auth/me", headers=bearer(tokens["refresh_token"])).status_code == 401


def test_access_token_cannot_be_used_to_refresh(client):
    tokens = client.post("/api/app/auth/register", json=CREDENTIALS).json()
    response = client.post("/api/app/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401


def test_refresh_issues_a_working_pair(client):
    tokens = client.post("/api/app/auth/register", json=CREDENTIALS).json()
    fresh = client.post("/api/app/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert fresh.status_code == 200
    assert client.get("/api/app/auth/me", headers=bearer(fresh.json()["access_token"])).status_code == 200


def test_logout_revokes_access_and_refresh_tokens(client):
    tokens = client.post("/api/app/auth/register", json=CREDENTIALS).json()
    assert client.post("/api/app/auth/logout", headers=bearer(tokens["access_token"])).status_code == 200
    assert client.get("/api/app/auth/me", headers=bearer(tokens["access_token"])).status_code == 401
    assert client.post("/api/app/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    # Signing in again works and yields tokens under the new version.
    again = client.post("/api/app/auth/login", json={"email": "owner@shop.example", "password": CREDENTIALS["password"]})
    assert client.get("/api/app/auth/me", headers=bearer(again.json()["access_token"])).status_code == 200


def test_garbage_token_is_rejected(client):
    assert client.get("/api/app/auth/me", headers=bearer("not.a.jwt")).status_code == 401


# ── modes ────────────────────────────────────────────────────────────────────

def test_jwt_mode_refuses_anonymous_requests(client, monkeypatch):
    monkeypatch.setattr(api.auth, "get_settings", lambda: Settings(auth_mode="jwt"))
    assert client.get("/api/app/auth/me").status_code == 401


def test_development_mode_still_allows_the_local_prototype_owner(client):
    response = client.get("/api/app/auth/me")
    assert response.status_code == 200 and response.json()["email"] == "developer@bsmart.local"
