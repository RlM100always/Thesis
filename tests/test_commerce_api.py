from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.auth import get_current_user
from api.commerce_routes import router
from api.database import Base, get_db
from api.domain_models import (
    Branch, InventoryBalance, Membership, Organization, Product, StockMovement, User,
)


def test_sale_is_atomic_and_decrements_tenant_stock():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="owner@example.com", display_name="Owner")
        org = Organization(name="Test Shop", slug="test-shop")
        db.add_all([user, org])
        db.flush()
        branch = Branch(organization_id=org.id, code="MAIN", name="Main")
        product = Product(
            organization_id=org.id, sku="RICE-1", name="Rice",
            selling_price=Decimal("80"), cost_price=Decimal("70"),
        )
        db.add_all([branch, product, Membership(
            organization_id=org.id, user_id=user.id, role="owner"
        )])
        db.flush()
        db.add(InventoryBalance(
            organization_id=org.id, branch_id=branch.id,
            product_id=product.id, quantity=Decimal("10"),
        ))
        db.commit()
        ids = user.id, org.id, branch.id, product.id

    def session_override():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    def user_override():
        with Session(engine) as db:
            return db.get(User, ids[0])

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_current_user] = user_override
    client = TestClient(app)
    response = client.post(
        "/api/app/sales",
        headers={"X-Organization-ID": ids[1]},
        json={
            "branch_id": ids[2], "invoice_number": "INV-001",
            "sold_at": "2026-09-04T10:00:00+06:00",
            "items": [{"product_id": ids[3], "quantity": "2"}],
            "payments": [{"method": "bkash", "amount": "160"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == "160.00"
    assert response.json()["due"] == "0.00"
    with Session(engine) as db:
        balance = db.scalar(select(InventoryBalance.quantity))
        movement = db.scalar(select(StockMovement).where(StockMovement.movement_type == "sale"))
        assert balance == Decimal("8.000")
        assert movement.quantity_delta == Decimal("-2.000")

    failed = client.post(
        "/api/app/sales",
        headers={"X-Organization-ID": ids[1]},
        json={
            "branch_id": ids[2], "invoice_number": "INV-002",
            "sold_at": "2026-09-04T11:00:00+06:00",
            "items": [{"product_id": ids[3], "quantity": "99"}],
        },
    )
    assert failed.status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(InventoryBalance.quantity)) == Decimal("8.000")
