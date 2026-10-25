"""Opt-in presentation account and clearly labelled sample pharmacy workspace.

Only enabled when PRESENTATION_DEMO_ENABLED=true, AUTH_MODE=jwt and a strong
PRESENTATION_PASSWORD_HASH is configured in Render's private environment.
Never hardcode or print an administrative password. Existing users are never
promoted or have their passwords silently overwritten.
"""
from __future__ import annotations

import os
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .domain_models import (
    Batch, BatchStock, Branch, Customer, InventoryBalance, Membership,
    Organization, OrganizationSetting, Product, StockMovement, Supplier, User,
)
from .accounting import seed_default_accounts
from .approvals import seed_default_rules
from .loyalty import seed_default_rule as seed_loyalty
from .commission import seed_default_rule as seed_commission

log = logging.getLogger("api.presentation_demo")
DEMO_SLUG = "bsmart-presentation-pharmacy"


def ensure_presentation_demo() -> None:
    """Idempotently provision one real JWT account and one isolated demo tenant."""
    if os.getenv("PRESENTATION_DEMO_ENABLED", "").lower() != "true":
        return
    if os.getenv("AUTH_MODE", "").lower() != "jwt":
        log.warning("Presentation setup skipped: JWT authentication required")
        return
    email = os.getenv("PRESENTATION_DEMO_EMAIL", "").strip().lower()
    password_hash = os.getenv("PRESENTATION_PASSWORD_HASH", "").strip()
    if not email or "@" not in email or not password_hash.startswith("scrypt$"):
        log.error("Presentation setup skipped: email or scrypt password hash missing")
        return

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email, display_name="Thesis Presentation Admin",
                password_hash=password_hash, is_platform_admin=True, active=True,
            )
            db.add(user)
            db.flush()
        elif not user.is_platform_admin:
            # Never turn an existing user into a super-admin via environment config.
            log.error("Presentation email already belongs to a non-admin account; refusing elevation")
            return

        org = db.scalar(select(Organization).where(Organization.slug == DEMO_SLUG))
        if org is None:
            org = Organization(
                name="B-SMART Thesis Demo Pharmacy (SAMPLE DATA)",
                slug=DEMO_SLUG, sector="pharmacy", size_class="small",
                address="Sample demonstration workspace — Bangladesh",
                receipt_footer="DEMO ONLY — NOT A REAL TRANSACTION",
            )
            db.add(org)
            db.flush()
            db.add(OrganizationSetting(organization_id=org.id))
            db.add(Branch(organization_id=org.id, code="MAIN", name="Demo Main Branch", division="Dhaka"))
            db.flush()
            seed_default_accounts(db, org.id)
            seed_default_rules(db, org.id)
            seed_loyalty(db, org.id)
            seed_commission(db, org.id)

        membership = db.scalar(select(Membership).where(
            Membership.organization_id == org.id, Membership.user_id == user.id
        ))
        if membership is None:
            db.add(Membership(organization_id=org.id, user_id=user.id, role="owner", active=True))
        elif membership.role != "owner":
            log.error("Unexpected non-owner membership for presentation user; refusing change")
            return

        # Minimal, distinct sample data, never passed off as experimental findings.
        branch = db.scalar(select(Branch).where(Branch.organization_id == org.id, Branch.code == "MAIN"))
        if branch is None:
            branch = Branch(organization_id=org.id, code="MAIN", name="Demo Main Branch", division="Dhaka")
            db.add(branch)
            db.flush()
        supplier = db.scalar(select(Supplier).where(Supplier.organization_id == org.id, Supplier.code == "DEMO-SUP"))
        if supplier is None:
            supplier = Supplier(organization_id=org.id, code="DEMO-SUP", name="Example Supplier (Demo)", typical_lead_days=5)
            db.add(supplier)
            db.flush()

        example_items = [
            ("DEMO-PARA500", "Paracetamol 500 mg (DEMO)", "OTC", "strip", "20", "14", "60", 90),
            ("DEMO-ORS", "Oral Rehydration Salts (DEMO)", "OTC", "sachet", "12", "8", "120", 180),
            ("DEMO-VITC", "Vitamin C (DEMO)", "Supplement", "box", "150", "110", "32", 120),
            ("DEMO-BANDAGE", "Medical Bandage (DEMO)", "Supplies", "pcs", "40", "28", "70", 365),
        ]
        for sku, name, category, unit, price, cost, quantity, expiry_days in example_items:
            product = db.scalar(select(Product).where(Product.organization_id == org.id, Product.sku == sku))
            if product is not None:
                continue
            product = Product(
                organization_id=org.id, sku=sku, name=name, category=category, unit=unit,
                selling_price=Decimal(price), cost_price=Decimal(cost),
                reorder_level=Decimal("20"), track_expiry=True,
            )
            db.add(product)
            db.flush()
            batch = Batch(
                organization_id=org.id, product_id=product.id,
                batch_no="DEMO-LOT-" + sku[-5:], expiry_date=date.today() + timedelta(days=expiry_days),
                unit_cost=Decimal(cost), supplier_id=supplier.id, source="opening", status="active",
            )
            db.add(batch)
            db.flush()
            amount = Decimal(quantity)
            db.add(InventoryBalance(organization_id=org.id, branch_id=branch.id, product_id=product.id, quantity=amount))
            db.add(BatchStock(organization_id=org.id, branch_id=branch.id, batch_id=batch.id, quantity=amount))
            db.add(StockMovement(
                organization_id=org.id, branch_id=branch.id, product_id=product.id,
                batch_id=batch.id, movement_type="opening", quantity_delta=amount,
                unit_cost=Decimal(cost), reference_type="demo",
            ))
        for code, name in [("DEMO-C01", "Demo Customer A"), ("DEMO-C02", "Demo Customer B")]:
            if db.scalar(select(Customer).where(Customer.organization_id == org.id, Customer.code == code)) is None:
                db.add(Customer(organization_id=org.id, code=code, display_name=name, marketing_consent=False))
        db.commit()
        log.info("Presentation sample workspace available (no password logged)")
