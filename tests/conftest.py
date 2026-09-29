"""Shared fixtures: an in-memory multi-tenant world with one user per role.

``world`` builds two organizations. Organization A has one user for every role;
organization B has a single owner and exists only to prove that tenants cannot
see each other. ``client_for`` returns a TestClient authenticated as a given
user, so a test can say "as a cashier, call this" in one line.
"""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.analytics_routes import router as analytics_router
from api.app_routes import router as app_router
from api.auth import get_current_user
from api.audit_routes import router as audit_router
from api.auth_routes import router as auth_router
from api.batch_routes import router as batch_router
from api.insights_routes import router as insights_router
from api.bulk_import_routes import router as bulk_import_router
from api.planning_routes import router as planning_router
from api.receivables_routes import router as receivables_router
from api.insights_advanced_routes import router as insights_advanced_router
from api.bsmart_routes import router as bsmart_router
from api.commerce_routes import router as commerce_router
from api.data_import_routes import router as data_import_router
from api.database import Base, get_db
from api.directory_routes import router as directory_router
from api.domain_models import Branch, InventoryBalance, Membership, Organization, Product, User
from api.finance_routes import router as finance_router
from api.permissions import ROLES

ROUTERS = (
    auth_router, app_router, commerce_router, directory_router, finance_router,
    data_import_router, analytics_router, bsmart_router, audit_router, batch_router, insights_router, bulk_import_router, planning_router, receivables_router, insights_advanced_router,
)


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def build_app(engine, current_user_id: str | None = None) -> FastAPI:
    """App with every operational router. With ``current_user_id`` the caller is
    fixed to that user; without it the real authentication path runs."""
    app = FastAPI()
    for router in ROUTERS:
        app.include_router(router)

    def session_override():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = session_override
    if current_user_id is not None:
        def user_override():
            with Session(engine) as db:
                return db.get(User, current_user_id)
        app.dependency_overrides[get_current_user] = user_override
    return app


@pytest.fixture()
def make_app(engine):
    """Factory for an app over the test database (see ``build_app``)."""
    def make(current_user_id: str | None = None) -> FastAPI:
        return build_app(engine, current_user_id)
    return make


@pytest.fixture()
def world(engine):
    with Session(engine) as db:
        org_a = Organization(name="Shop A", slug="shop-a")
        org_b = Organization(name="Shop B", slug="shop-b")
        db.add_all([org_a, org_b])
        db.flush()
        users = {}
        for role in ROLES:
            user = User(email=f"{role}@a.example", display_name=f"{role} A")
            db.add(user)
            db.flush()
            db.add(Membership(organization_id=org_a.id, user_id=user.id, role=role))
            users[role] = user.id
        owner_b = User(email="owner@b.example", display_name="Owner B")
        db.add(owner_b)
        db.flush()
        db.add(Membership(organization_id=org_b.id, user_id=owner_b.id, role="owner"))
        branch_a = Branch(organization_id=org_a.id, code="MAIN", name="Main")
        product_a = Product(
            organization_id=org_a.id, sku="RICE-1", name="Rice",
            selling_price=Decimal("80"), cost_price=Decimal("70"),
        )
        db.add_all([branch_a, product_a])
        db.flush()
        db.add(InventoryBalance(
            organization_id=org_a.id, branch_id=branch_a.id,
            product_id=product_a.id, quantity=Decimal("10"),
        ))
        db.commit()
        return {
            "org_a": org_a.id, "org_b": org_b.id, "users": users, "owner_b": owner_b.id,
            "branch_a": branch_a.id, "product_a": product_a.id,
        }


@pytest.fixture()
def client_for(engine, world):
    def make(role: str, org: str = "org_a") -> tuple[TestClient, dict]:
        user_id = world["owner_b"] if org == "org_b" else world["users"][role]
        client = TestClient(build_app(engine, user_id))
        return client, {"X-Organization-ID": world[org]}
    return make
