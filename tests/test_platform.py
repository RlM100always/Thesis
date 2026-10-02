"""Platform super-admin: read-only visibility across every tenant.

The `world` fixture's users are all ordinary, org-scoped members; a platform
admin is deliberately not one of them (the flag is never settable through
any API), so each test here creates its own via a direct DB write, the same
way `test_audit.py` creates rows a normal API call can't produce.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import platform_routes
from api.domain_models import AuditLog, Membership, Notification, Organization, OutboundMessage, User, UserSession


def platform_admin_client(engine, make_app):
    with Session(engine) as db:
        admin = User(email="platform-admin@bsmart.local", display_name="Platform Admin", is_platform_admin=True)
        db.add(admin)
        db.commit()
        admin_id = admin.id
    return TestClient(make_app(admin_id))


def test_an_ordinary_user_is_refused_platform_routes(client_for):
    client, headers = client_for("owner")
    assert client.get("/api/platform/organizations").status_code == 403
    assert client.get("/api/platform/summary").status_code == 403
    assert client.get("/api/platform/security").status_code == 403
    assert client.get("/api/platform/system-health").status_code == 403
    assert client.get("/api/platform/features").status_code == 403


def test_a_platform_admin_sees_every_organization_with_real_counts(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    body = client.get("/api/platform/organizations").json()
    ids = {o["id"] for o in body["organizations"]}
    assert world["org_a"] in ids and world["org_b"] in ids
    org_a = next(o for o in body["organizations"] if o["id"] == world["org_a"])
    assert org_a["branch_count"] >= 1
    assert org_a["member_count"] >= 1
    assert org_a["last_sale_at"] is None   # world fixture seeds no sales


def test_platform_summary_counts_are_real_not_estimated(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    body = client.get("/api/platform/summary").json()
    assert body["organizations_total"] >= 2
    assert body["users_total"] >= len(world["users"]) + 1   # + owner_b


def test_platform_user_directory_filters_and_paginates_on_the_server(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    result = client.get("/api/platform/users?filter=mfa&page=1&page_size=10")
    assert result.status_code == 200
    body = result.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["count"] >= len(world["users"])
    assert all(user["active"] and not user["mfa_enabled"] for user in body["users"])


def test_the_platform_admin_flag_is_not_settable_through_any_api(client_for):
    client, headers = client_for("owner")
    # Nothing in the staff/account update surfaces exposes this field; confirm
    # the org-scoped "update my account" style routes simply don't accept it.
    response = client.patch("/api/app/auth/me", headers=headers, json={"is_platform_admin": True})
    assert response.status_code in (404, 405)   # no such route exists at all


def test_system_health_never_returns_credentials(engine, make_app):
    client = platform_admin_client(engine, make_app)
    response = client.get("/api/platform/system-health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"]["connected"] is True
    assert {p["key"] for p in body["providers"]} == {"bkash", "whatsapp", "sms", "ai"}
    serialized = response.text.lower()
    assert "access_token" not in serialized
    assert "app_secret" not in serialized
    assert "api_key" not in serialized
    assert "password" not in serialized


def test_security_posture_uses_real_user_rows(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    body = client.get("/api/platform/security").json()
    assert body["users_total"] >= len(world["users"]) + 2
    assert body["users_active"] == body["users_total"]
    assert body["platform_admins"] == 1
    assert body["mfa_coverage_percent"] == 0


def test_feature_rollout_changes_every_active_tenant_and_is_audited(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    before = client.get("/api/platform/features").json()
    workforce = next(f for f in before["features"] if f["key"] == "workforce")
    assert workforce["enabled_count"] == 2

    response = client.patch("/api/platform/features/workforce", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["updated_count"] == 2

    after = client.get("/api/platform/features").json()
    workforce = next(f for f in after["features"] if f["key"] == "workforce")
    assert workforce["disabled_count"] == 2
    with Session(engine) as db:
        assert all('"workforce": false' in (org.feature_flags_json or "") for org in db.query(Organization).all())
        assert db.query(AuditLog).filter(AuditLog.action == "platform.feature_rollout_updated").count() == 1


def test_unknown_feature_rollout_is_rejected(engine, make_app):
    client = platform_admin_client(engine, make_app)
    response = client.patch("/api/platform/features/not-a-real-module", json={"enabled": True})
    assert response.status_code == 404


def test_admin_can_inspect_and_revoke_only_the_requested_user_session(engine, world, make_app):
    target_id = world["users"]["cashier"]
    with Session(engine) as db:
        session = UserSession(
            user_id=target_id,
            current_jti_hash="a" * 64,
            device_label="Cash counter Chrome",
            ip_address="10.0.0.8",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(session)
        db.commit()
        session_id = session.id

    client = platform_admin_client(engine, make_app)
    detail = client.get(f"/api/platform/users/{target_id}")
    assert detail.status_code == 200
    assert any(s["id"] == session_id and s["active"] for s in detail.json()["sessions"])
    response = client.post(f"/api/platform/users/{target_id}/sessions/{session_id}/revoke")
    assert response.status_code == 200
    with Session(engine) as db:
        stored = db.get(UserSession, session_id)
        assert stored.revoked_at is not None
        assert stored.revoked_reason == "platform_admin_revoked"


def test_platform_admin_governance_requires_mfa_and_is_audited(engine, world, make_app):
    target_id = world["users"]["manager"]
    client = platform_admin_client(engine, make_app)
    blocked = client.patch(f"/api/platform/administrators/{target_id}", json={"is_platform_admin": True})
    assert blocked.status_code == 409
    with Session(engine) as db:
        target = db.get(User, target_id)
        target.mfa_enabled = True
        db.commit()
    granted = client.patch(f"/api/platform/administrators/{target_id}", json={"is_platform_admin": True})
    assert granted.status_code == 200
    listing = client.get("/api/platform/administrators").json()
    assert any(row["id"] == target_id for row in listing["administrators"])
    with Session(engine) as db:
        assert db.query(AuditLog).filter(AuditLog.action == "platform.administrator_granted").count() == 1


def test_tenant_profile_and_member_access_are_managed_with_owner_guard(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    updated = client.patch(f"/api/platform/organizations/{world['org_a']}", json={
        "name": "Shop A Limited", "sector": "retail", "size_class": "small",
        "address": "Dhaka", "phone": "01700000000", "vat_reg_no": "BIN123",
    })
    assert updated.status_code == 200
    detail = client.get(f"/api/platform/organizations/{world['org_a']}").json()
    assert detail["name"] == "Shop A Limited"
    owner = next(row for row in detail["members"] if row["role"] == "owner")
    blocked = client.patch(
        f"/api/platform/organizations/{world['org_a']}/members/{owner['membership_id']}",
        json={"role": "manager", "active": True},
    )
    assert blocked.status_code == 409
    cashier = next(row for row in detail["members"] if row["role"] == "cashier")
    changed = client.patch(
        f"/api/platform/organizations/{world['org_a']}/members/{cashier['membership_id']}",
        json={"role": "manager", "active": True},
    )
    assert changed.status_code == 200
    with Session(engine) as db:
        assert db.get(Membership, cashier["membership_id"]).role == "manager"


def test_onboarding_pipeline_is_calculated_from_real_tenant_rows(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    body = client.get("/api/platform/organizations/onboarding").json()
    org_a = next(row for row in body["organizations"] if row["id"] == world["org_a"])
    assert org_a["checklist"]["team"] is True
    assert org_a["checklist"]["branch"] is True
    assert org_a["checklist"]["catalog"] is True
    assert org_a["checklist"]["first_sale"] is False
    assert org_a["progress_percent"] == 60


def test_integration_monitor_masks_recipient_and_omits_message_body(engine, world, make_app):
    with Session(engine) as db:
        db.add(OutboundMessage(
            organization_id=world["org_a"], requested_by_user_id=world["users"]["owner"],
            channel="sms", recipient="01700123456", template="payment_due",
            body="Private customer message", idempotency_key="platform-test-message",
            status="failed", last_error="Provider timeout",
        ))
        db.commit()
    client = platform_admin_client(engine, make_app)
    response = client.get("/api/platform/integration-operations")
    assert response.status_code == 200
    body = response.json()
    assert body["status_counts"]["failed"] == 1
    assert body["messages"][0]["recipient_masked"] == "••••3456"
    assert "Private customer message" not in response.text
    assert "01700123456" not in response.text


def test_backup_download_and_guarded_delete(engine, make_app, tmp_path, monkeypatch):
    monkeypatch.setattr(platform_routes, "BACKUP_DIR", tmp_path)
    first = tmp_path / "backup_20260101T000000000000Z.sqlite3"
    second = tmp_path / "backup_20260102T000000000000Z.sqlite3"
    first.write_bytes(b"sqlite-backup-one")
    second.write_bytes(b"sqlite-backup-two")
    client = platform_admin_client(engine, make_app)

    download = client.get(f"/api/platform/backups/{first.name}/download")
    assert download.status_code == 200
    assert download.content == b"sqlite-backup-one"
    removed = client.delete(f"/api/platform/backups/{first.name}")
    assert removed.status_code == 200
    assert not first.exists()
    refused = client.delete(f"/api/platform/backups/{second.name}")
    assert refused.status_code == 409
    assert second.exists()


def test_platform_announcement_targets_selected_tenant_and_audience(engine, world, make_app):
    client = platform_admin_client(engine, make_app)
    response = client.post("/api/platform/announcements", json={
        "title": "Planned maintenance",
        "body": "The service will be unavailable for ten minutes.",
        "severity": "warning",
        "audience": "owners",
        "organization_ids": [world["org_a"]],
    })
    assert response.status_code == 200
    assert response.json()["organization_count"] == 1
    assert response.json()["recipient_count"] == 1
    with Session(engine) as db:
        notifications = db.query(Notification).all()
        assert len(notifications) == 1
        assert notifications[0].organization_id == world["org_a"]
        assert notifications[0].recipient_user_id == world["users"]["owner"]
    history = client.get("/api/platform/announcements").json()["announcements"]
    assert history[0]["title"] == "Planned maintenance"
    assert history[0]["recipient_count"] == 1
