from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.analytics_routes import router
from api.auth import get_current_user
from api.database import Base, get_db
from api.domain_models import (
    Branch, Customer, InventoryBalance, Membership, Organization, Product,
    SalesOrder, SalesOrderItem, User,
)


def test_dashboard_and_recommendations_use_only_operational_data():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        user = User(email="owner@example.com", display_name="Owner")
        org = Organization(name="Retail", slug="retail")
        db.add_all([user, org]); db.flush()
        branch = Branch(organization_id=org.id, code="MAIN", name="Main")
        product = Product(
            organization_id=org.id, sku="OIL", name="Soybean oil",
            selling_price=Decimal("180"), cost_price=Decimal("150"),
            reorder_level=Decimal("5"),
        )
        customer = Customer(
            organization_id=org.id, code="C-1", display_name="Rahim",
            marketing_consent=True,
        )
        db.add_all([branch, product, customer, Membership(
            organization_id=org.id, user_id=user.id, role="owner"
        )]); db.flush()
        db.add(InventoryBalance(
            organization_id=org.id, branch_id=branch.id,
            product_id=product.id, quantity=Decimal("1"),
        ))
        order = SalesOrder(
            organization_id=org.id, branch_id=branch.id, customer_id=customer.id,
            invoice_number="OLD-1", sold_at=now-timedelta(days=70), status="completed",
            subtotal=Decimal("1800"), discount_amount=0, tax_amount=0, total=Decimal("1800"),
        )
        db.add(order); db.flush()
        db.add(SalesOrderItem(
            organization_id=org.id, order_id=order.id, product_id=product.id,
            quantity=Decimal("10"), unit_price=Decimal("180"),
            unit_cost_at_sale=Decimal("150"), discount_amount=0, line_total=Decimal("1800"),
        ))
        db.commit(); ids = user.id, org.id

    def sessions():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    def owner():
        with Session(engine) as db:
            return db.get(User, ids[0])

    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[get_current_user] = owner
    client = TestClient(app)
    headers = {"X-Organization-ID": ids[1]}

    dashboard = client.get("/api/app/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["low_stock_products"] == 1
    strategy = client.get("/api/app/recommendations", headers=headers)
    assert strategy.status_code == 200, strategy.text
    assert strategy.json()["model_status"] == "baseline"
    assert {item["type"] for item in strategy.json()["actions"]} == {"reorder", "retention"}
