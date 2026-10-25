"""Regression: operational public store listing is never the synthetic RQ demo."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.domain_models import Store
from api.store_routes import public_router


def _client(make_app):
    app = make_app()
    app.include_router(public_router)
    return TestClient(app)


def test_store_directory_lists_active_owners_only(engine, world, make_app):
    with Session(engine) as db:
        db.add_all([
            Store(organization_id=world["org_a"], slug="a-merchant",
                  display_name="Sample Dhaka Mart", area="Dhanmondi",
                  category="Grocery", is_active=True),
            Store(organization_id=world["org_b"], slug="b-hidden",
                  display_name="Hidden Test Store", category="Electronics", is_active=False),
        ])
        db.commit()
    client = _client(make_app)
    resp = client.get("/api/public/store/")
    assert resp.status_code == 200
    stores = resp.json()
    assert len(stores) == 1
    assert stores[0]["display_name"] == "Sample Dhaka Mart"
    assert stores[0]["organization_id"] == world["org_a"]
    assert "customer" not in stores[0]
    assert "cost_price" not in stores[0]


def test_store_directory_filters_and_slug_resolution(engine, world, make_app):
    with Session(engine) as db:
        db.add(Store(organization_id=world["org_a"], slug="a-merchant",
                     display_name="Sample Dhaka Mart", area="Dhanmondi",
                     category="Grocery", is_active=True))
        db.commit()
    client = _client(make_app)
    assert len(client.get("/api/public/store/",params={"category":"grocery"}).json()) == 1
    assert client.get("/api/public/store/",params={"category":"pharmacy"}).json() == []
    assert client.get("/api/public/store/slug/a-merchant").status_code == 200
    assert client.get("/api/public/store/slug/missing").status_code == 404
