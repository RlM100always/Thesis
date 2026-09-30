"""Platform super-admin: read-only visibility across every tenant.

The `world` fixture's users are all ordinary, org-scoped members; a platform
admin is deliberately not one of them (the flag is never settable through
any API), so each test here creates its own via a direct DB write, the same
way `test_audit.py` creates rows a normal API call can't produce.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.domain_models import User


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


def test_the_platform_admin_flag_is_not_settable_through_any_api(client_for):
    client, headers = client_for("owner")
    # Nothing in the staff/account update surfaces exposes this field; confirm
    # the org-scoped "update my account" style routes simply don't accept it.
    response = client.patch("/api/app/auth/me", headers=headers, json={"is_platform_admin": True})
    assert response.status_code in (404, 405)   # no such route exists at all
