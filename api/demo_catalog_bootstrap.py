"""Opt-in, PostgreSQL-only storefront DEMO catalogue.

This is *not* a recovery of old business/customer/order records. Products and
prices are examples for a software demonstration, not verified merchant data.
Never run on SQLite / ephemeral Render storage, nor over any existing stores.
Re-running is safe: if there are any Store rows, no writes are made.
"""
from __future__ import annotations

import ast
import logging
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .domain_models import (
    Branch, InventoryBalance, Organization, Product, Store, StoreProduct,
)

log = logging.getLogger("bsmart.demo_catalog")
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "seed_10_businesses.py"

# Short, unambiguous labels help users distinguish examples from actual SMEs.
SPECS = (
    ("pharmacy", "আল-হেলাল ফার্মেসি", "মিরপুর-১০, ঢাকা", "ফার্মেসি", "pharmacy"),
    ("grocery", "মা-মণি জেনারেল স্টোর", "আগ্রাবাদ, চট্টগ্রাম", "মুদি", "clean"),
    ("clothing", "নিউ লুক ফ্যাশন", "বসুন্ধরা সিটি, ঢাকা", "পোশাক", "fashion"),
    ("restaurant", "স্বাদের রান্নাঘর", "জিন্দাবাজার, সিলেট", "রেস্টুরেন্ট", "warm"),
    ("electronics", "ডিজিটাল জোন", "এলিফ্যান্ট রোড, ঢাকা", "ইলেকট্রনিক্স", "dark"),
    ("hardware", "বিল্ডার্স হার্ডওয়্যার", "চাষাঢ়া, নারায়ণগঞ্জ", "হার্ডওয়্যার", "clean"),
    ("beauty", "গ্লামার বিউটি শপ", "গুলশান-১, ঢাকা", "বিউটি", "fashion"),
    ("stationery", "জ্ঞান ভাণ্ডার স্টেশনারি", "সাহেব বাজার, রাজশাহী", "স্টেশনারি", "clean"),
    ("mobile", "স্মার্ট মোবাইল সেন্টার", "কান্দিরপাড়, কুমিল্লা", "মোবাইল", "dark"),
    ("furniture", "আরামদায়ক ফার্নিচার", "হাতিরপুল, ঢাকা", "ফার্নিচার", "warm"),
)
COLORS = {"pharmacy":"#0e7c67","clean":"#0a8752","fashion":"#c43a8a","warm":"#e07b39","dark":"#1e3a5f"}

def _catalogue() -> dict:
    """Read only the literal PRODUCTS constant; DO NOT execute old seed code."""
    source = SOURCE.read_text(encoding="utf-8-sig")
    parsed = ast.parse(source, filename=str(SOURCE))
    for node in parsed.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PRODUCTS" for t in node.targets
        ):
            result = ast.literal_eval(node.value)
            if not isinstance(result, dict):
                raise ValueError("Seed PRODUCTS is not a constant dictionary")
            return result
    raise ValueError("No literal PRODUCTS catalogue available")

def seed_demo_catalogue() -> dict:
    """Called at startup only under explicit opt-in; no deletion or overwrite."""
    if os.getenv("BSMART_BOOTSTRAP_DEMO_CATALOG", "") != "YES":
        return {"status": "disabled"}
    if engine.dialect.name != "postgresql":
        log.warning("DEMO_CATALOG_SKIPPED: persistent PostgreSQL DATABASE_URL required, got %s", engine.dialect.name)
        return {"status": "skipped", "reason": "requires_postgresql"}
    template = _catalogue()
    with SessionLocal() as db:
        try:
            # Preserve *all* pre-existing stores, even inactive ones.
            existing = db.scalar(select(func.count(Store.id))) or 0
            if existing:
                log.warning("DEMO_CATALOG_SKIPPED: %d existing stores; no changes made", existing)
                return {"status": "skipped", "reason": "stores_already_present", "count": existing}
            created = []
            for sector, name, area, category, theme in SPECS:
                slug = f"demo-bsmart-{sector}"
                # If an older partial demo org exists, refuse to mutate it.
                if db.scalar(select(Organization.id).where(Organization.slug == slug)):
                    raise ValueError(f"Demo slug already exists; refusing to touch {slug}")
                org = Organization(
                    name=f"ডেমো · {name}", slug=slug, sector=sector,
                    address=area, active=True,
                )
                db.add(org); db.flush()
                branch = Branch(
                    organization_id=org.id, code="DEMO", name="ডেমো প্রধান শাখা",
                    address=area, active=True,
                )
                db.add(branch); db.flush()
                store = Store(
                    organization_id=org.id, slug=slug,
                    is_active=True, display_name=f"ডেমো · {name}",
                    tagline="শুধু সফটওয়্যার পরীক্ষার নমুনা দোকান; বাস্তব অর্ডার নয়",
                    theme_preset=theme, theme_color=COLORS[theme],
                    category=category, area=area,
                    show_price=True, show_stock_level="available_only",
                    show_phone=False, show_exact_address=False,
                    payment_cod=True, payment_bkash=False, payment_nagad=False,
                    delivery_note="ডেমো অর্ডার; বাস্তবে কোনো পণ্য পাঠানো হবে না",
                )
                db.add(store); db.flush()
                goods = template.get(sector) or []
                if len(goods) < 5:
                    raise ValueError(f"Missing realistic sample products for {sector}")
                for index, (sku, title, cat, sell, cost) in enumerate(goods[:24]):
                    selling = Decimal(str(sell))
                    buying = Decimal(str(cost))
                    if selling < 0 or buying < 0:
                        raise ValueError("Invalid example price")
                    prod = Product(
                        organization_id=org.id, sku=str(sku), name=str(title),
                        category=str(cat), unit="pcs", selling_price=selling,
                        cost_price=buying, active=True, track_expiry=False,
                    )
                    db.add(prod); db.flush()
                    db.add(StoreProduct(
                        store_id=store.id, product_id=prod.id,
                        is_listed=True, is_featured=index < 3, sort_order=index,
                        description_long="নমুনা পণ্য — মূল্য ও স্টক কৃত্রিম",
                    ))
                    db.add(InventoryBalance(
                        organization_id=org.id, branch_id=branch.id,
                        product_id=prod.id, quantity=Decimal("100"),
                    ))
                created.append(slug)
            db.commit()
            log.warning("DEMO_CATALOG_CREATED: %d clearly labelled synthetic stores and catalogues; no real tenants changed", len(created))
            return {"status": "created", "stores": created}
        except Exception:
            db.rollback()
            log.exception("DEMO_CATALOG_FAILED: transaction rolled back without creating partial stores")
            raise
