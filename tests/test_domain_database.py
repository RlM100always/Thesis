from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.database import Base
from api.domain_models import Branch, Organization, Product, StockMovement


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_tenant_scoped_sku_and_append_only_stock_balance(db: Session):
    first = Organization(name="Shop A", slug="shop-a")
    second = Organization(name="Shop B", slug="shop-b")
    db.add_all([first, second])
    db.flush()
    branch = Branch(organization_id=first.id, code="MAIN", name="Main")
    product_a = Product(
        organization_id=first.id, sku="SKU-1", name="Rice",
        selling_price=Decimal("80"), cost_price=Decimal("70"),
    )
    product_b = Product(
        organization_id=second.id, sku="SKU-1", name="Rice",
        selling_price=Decimal("82"), cost_price=Decimal("71"),
    )
    db.add_all([branch, product_a, product_b])
    db.flush()
    db.add_all([
        StockMovement(
            organization_id=first.id, branch_id=branch.id, product_id=product_a.id,
            movement_type="purchase", quantity_delta=Decimal("20"),
            occurred_at=datetime.now(timezone.utc),
        ),
        StockMovement(
            organization_id=first.id, branch_id=branch.id, product_id=product_a.id,
            movement_type="sale", quantity_delta=Decimal("-3"),
            occurred_at=datetime.now(timezone.utc),
        ),
    ])
    db.commit()
    balance = db.scalar(select(func.sum(StockMovement.quantity_delta)))
    assert balance == Decimal("17.000")


def test_duplicate_sku_is_rejected_within_same_tenant(db: Session):
    org = Organization(name="Shop", slug="shop")
    db.add(org)
    db.flush()
    db.add_all([
        Product(organization_id=org.id, sku="DUP", name="One"),
        Product(organization_id=org.id, sku="DUP", name="Two"),
    ])
    with pytest.raises(IntegrityError):
        db.commit()
