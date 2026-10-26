"""Restore storefront links from EXISTING operational organisations/products.

Never recreates lost customers/orders from research simulations, and never
creates public listings without an explicit operator opt-in.

Read-only by default:
    python scripts/reconcile_existing_stores.py
One confirmed organisation only:
    python scripts/reconcile_existing_stores.py --organization-id UUID --apply
Optional public activation and publishing of UNLISTED products:
    python scripts/reconcile_existing_stores.py --organization-id UUID --apply --activate --publish-new-products

IMPORTANT: Operates on DATABASE_URL selected by the backend. On ephemeral
SQLite it will not survive restart. It refuses production-looking SQLite.
This script cannot restore a lost database backup.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import func, select
from api.config import get_settings
from api.database import SessionLocal, engine
from api.domain_models import Organization, Product, Store, StoreProduct

SECTOR_CATEGORIES = {
    "pharmacy":"ফার্মেসি","grocery":"মুদি","clothing":"পোশাক",
    "fashion":"পোশাক","restaurant":"রেস্টুরেন্ট","electronics":"ইলেকট্রনিক্স",
    "hardware":"হার্ডওয়্যার","beauty":"বিউটি","stationery":"স্টেশনারি",
    "mobile":"মোবাইল","furniture":"ফার্নিচার",
}
SECTOR_THEMES = {
    "pharmacy":"pharmacy","grocery":"clean","clothing":"fashion",
    "fashion":"fashion","restaurant":"warm","electronics":"dark",
    "hardware":"clean","beauty":"fashion","stationery":"clean",
    "mobile":"dark","furniture":"warm",
}

def _safe_slug(org: Organization, db) -> str:
    original = (org.slug or "").lower()
    candidate = re.sub(r"[^a-z0-9-]+", "-", original).strip("-")
    candidate = re.sub(r"-{2,}", "-", candidate)
    if len(candidate) < 3:
        candidate = f"business-{org.id.replace('-', '')[:12]}"
    candidate = candidate[:75].rstrip("-")
    slug = candidate
    suffix = 2
    while db.scalar(select(Store.id).where(Store.slug == slug)):
        slug = f"{candidate[:70]}-{suffix}"
        suffix += 1
    return slug

def _record_counts(db, org: Organization) -> dict:
    store = db.scalar(select(Store).where(Store.organization_id == org.id))
    products = db.scalar(select(func.count(Product.id)).where(
        Product.organization_id == org.id, Product.active.is_(True)
    )) or 0
    listings = db.scalar(select(func.count(StoreProduct.id)).where(
        StoreProduct.store_id == store.id,
        StoreProduct.is_listed.is_(True)
    )) if store else 0
    return {"organization_id":org.id,"business":org.name,
            "has_store":store is not None,
            "active":bool(store.is_active) if store else False,
            "active_products":int(products),
            "published_products":int(listings or 0)}

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id",help="Selected existing business ID; required for write")
    parser.add_argument("--apply",action="store_true",help="Commit an isolated organisation change")
    parser.add_argument("--activate",action="store_true",help="Make selected storefront public")
    parser.add_argument("--publish-new-products",action="store_true",
                        help="Create opt-in online listings for currently unlisted active products")
    args = parser.parse_args(argv)
    if (args.activate or args.publish_new_products) and not args.apply:
        parser.error("--activate and --publish-new-products require --apply")
    if args.apply and not args.organization_id:
        parser.error("--apply requires an explicit --organization-id")
    if args.apply and engine.dialect.name == "sqlite" and (
        os.getenv("RENDER") or os.getenv("APP_ENV","").lower()=="production"
    ):
        parser.error("Refusing to update ephemeral Render/production SQLite: configure a durable DB")
    with SessionLocal() as db:
        if args.organization_id:
            org = db.get(Organization,args.organization_id)
            if not org:
                parser.error("Organization not found in currently configured database")
            orgs = [org]
        else:
            orgs = list(db.scalars(select(Organization).order_by(Organization.name)))
        if not args.apply:
            print(f"READ-ONLY AUDIT: backend={engine.dialect.name}; organizations={len(orgs)}")
            for org in orgs:
                print(_record_counts(db,org))
            print("No records created or modified.")
            return 0
        if len(orgs)!=1:
            parser.error("Exactly one existing organization may be changed per invocation")
        org=orgs[0]
        if (org.sector or "").lower() == "pharmacy" and args.publish_new_products:
            parser.error("Pharmacy items require manual licensed review before public listing")
        before=_record_counts(db,org)
        store=db.scalar(select(Store).where(Store.organization_id == org.id))
        try:
            if store is None:
                store=Store(
                    organization_id=org.id, slug=_safe_slug(org,db),
                    display_name=org.name,category=SECTOR_CATEGORIES.get((org.sector or "").lower(),"দোকান"),
                    theme_preset=SECTOR_THEMES.get((org.sector or "").lower(),"clean"),
                    is_active=False, show_price=True, show_stock_level="available_only",
                    show_phone=False,show_exact_address=False,
                    # Owner must choose actual supported checkout/delivery options.
                    payment_cod=False,payment_bkash=False,payment_nagad=False,
                )
                db.add(store);db.flush()
            if args.activate:
                if not args.publish_new_products and before["published_products"]==0:
                    parser.error("No published products. Add --publish-new-products or publish from owner panel first.")
                store.is_active=True
            newly_listed=0
            if args.publish_new_products:
                rows=list(db.scalars(select(Product).where(
                    Product.organization_id==org.id,Product.active.is_(True)
                ).order_by(Product.name)))
                for index,product in enumerate(rows):
                    row=db.scalar(select(StoreProduct).where(
                        StoreProduct.store_id==store.id,StoreProduct.product_id==product.id
                    ))
                    if row is not None:
                        # Never override an explicitly unlisted product.
                        continue
                    db.add(StoreProduct(store_id=store.id,product_id=product.id,
                        is_listed=True,sort_order=index))
                    newly_listed+=1
            db.commit()
        except Exception:
            db.rollback()
            raise
        print("BEFORE:",before)
        print("AFTER:",_record_counts(db,org))
        print(f"New listings created={newly_listed}. No customer/order rows touched.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
