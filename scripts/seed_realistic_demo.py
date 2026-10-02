"""Seed the live (operational) database with several realistic pharmacies.

Not a fresh invention: reuses this repo's own already-vetted real-anchored
catalog -- normalized_data/dim_product.csv (real Bangladeshi medicine names,
the Mendeley catalog) and normalized_data/dim_customer.csv (the thesis
dataset's real-pattern BD customer names, including their own
Marketing_Consent flag) -- the exact same source 00a_generate_pharmacy_dataset.py
draws on for the thesis pipeline. This script does NOT touch that pipeline or
its CSVs; it only populates the separate live multi-tenant app's own database
(api/domain_models.py tables) so the product looks like a populated system
instead of an empty one.

Writes ~15 months of daily sales per organization (enough real history for
ml.real_pipeline's forecast/churn/segment/return-risk models to all train
successfully -- each needs 90+ days / 300+ snapshots / 20+ customers /
300+ sold lines respectively), then trains all four models per org so
/api/app/recommendations and /api/app/segments show live model output
immediately, not baselines.

Usage:
    python -m scripts.seed_realistic_demo
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import utf8_console  # noqa: F401

from api.database import SessionLocal, engine
from api.domain_models import (
    Base, Branch, Customer, InventoryBalance, Membership, Organization,
    Product, SalesOrder, SalesOrderItem, SalesReturn, SalesReturnItem,
    Supplier, User,
)
from api.security import hash_password

DEMO_PASSWORD = "Pharmacy#2026"

random.seed(42)

CATALOG = pd.read_csv("normalized_data/dim_product.csv", encoding="utf-8-sig")
CUSTOMERS_POOL = pd.read_csv("normalized_data/dim_customer.csv", encoding="utf-8-sig")

SUPPLIER_NAMES = [
    "রহমান ফার্মা ডিস্ট্রিবিউটর্স", "বেঙ্গল হেলথকেয়ার সাপ্লাই", "মেডিপ্লাস হোলসেল",
    "নিউ সিটি ফার্মাসিউটিক্যাল এজেন্সি", "আল-বারাকা মেডিসিন হাউজ",
]

ORGS = [
    {"name": "আরোগ্য ফার্মেসী", "slug": "arogya-pharmacy", "branch": "ধানমন্ডি শাখা",
     "division": "Dhaka", "district": "Dhaka", "customer_offset": 0, "vertical": "pharmacy"},
    {"name": "সেবা মেডিকেল হল", "slug": "seba-medical-hall", "branch": "আগ্রাবাদ শাখা",
     "division": "Chattogram", "district": "Chattogram", "customer_offset": 90, "vertical": "pharmacy"},
    {"name": "জীবনদীপ ফার্মা পয়েন্ট", "slug": "jibondeep-pharma", "branch": "জিন্দাবাজার শাখা",
     "division": "Sylhet", "district": "Sylhet", "customer_offset": 180, "vertical": "pharmacy"},
    {"name": "নিত্য বাজার জেনারেল স্টোর", "slug": "nitto-bazar-grocery", "branch": "মিরপুর শাখা",
     "division": "Dhaka", "district": "Dhaka", "customer_offset": 270, "vertical": "grocery"},
    {"name": "রসনা রেস্তোরাঁ", "slug": "rosona-restaurant", "branch": "গুলশান শাখা",
     "division": "Dhaka", "district": "Dhaka", "customer_offset": 360, "vertical": "restaurant"},
    {"name": "স্টাইল হাউজ ফ্যাশন", "slug": "style-house-fashion", "branch": "নিউ মার্কেট শাখা",
     "division": "Dhaka", "district": "Dhaka", "customer_offset": 450, "vertical": "fashion"},
    {"name": "টেক জোন ইলেকট্রনিক্স", "slug": "tech-zone-electronics", "branch": "এলিফ্যান্ট রোড শাখা",
     "division": "Dhaka", "district": "Dhaka", "customer_offset": 540, "vertical": "electronics"},
]

# Real Bangladeshi brands and genuine approximate retail market prices (BDT,
# 2025 price levels) -- not invented SKUs. What's synthetic is the *linkage*
# (which customer bought which of these on which day), exactly the same
# declared-synthetic boundary 00a_generate_pharmacy_dataset.py draws for the
# thesis dataset: real catalog + real prices, synthetic transaction history.
VERTICAL_CATALOGS = {
    "grocery": [
        ("Pran Chinigura Rice 1kg", "rice", 95, 115), ("Pran Soyabean Oil 1L", "oil", 155, 178),
        ("Teer Soyabean Oil 1L", "oil", 150, 172), ("ACI Pure Salt 1kg", "grocery", 30, 38),
        ("Fresh Sugar 1kg", "grocery", 118, 132), ("Rupchanda Soyabean Oil 1L", "oil", 158, 180),
        ("Pran Mustard Oil 500ml", "oil", 140, 160), ("Radhuni Turmeric Powder 200g", "spice", 55, 70),
        ("Radhuni Chili Powder 200g", "spice", 60, 78), ("Pran Chanachur 200g", "snack", 45, 58),
        ("Olympic Energy Plus Biscuit", "snack", 8, 12), ("Pran Lassi 250ml", "beverage", 20, 28),
        ("Danish Butter 200g", "dairy", 190, 220), ("Aarong Dairy Milk 1L", "dairy", 85, 98),
        ("Igloo Vanilla Ice Cream 1L", "dairy", 280, 320), ("Fresh Full Cream Milk Powder 500g", "dairy", 320, 360),
        ("Pran Mango Juice 1L", "beverage", 110, 135), ("RC Cola 500ml", "beverage", 30, 40),
        ("Mojo 500ml", "beverage", 28, 38), ("Nestle Maggi Noodles 2-min", "snack", 15, 20),
        ("Pran Egg Noodles 200g", "snack", 20, 26), ("Square Toiletries Tibet Snow 100g", "personal_care", 55, 68),
        ("Kohinoor Chemical Tibet Toothpaste", "personal_care", 45, 58), ("Lux Soap 100g", "personal_care", 35, 45),
        ("Lifebuoy Soap 100g", "personal_care", 32, 42), ("Meril Petroleum Jelly 100ml", "personal_care", 65, 80),
        ("Keya Detergent Powder 1kg", "household", 95, 115), ("Rin Detergent Bar", "household", 18, 25),
        ("ACI Mosquito Coil", "household", 25, 35), ("Pran Dal (Lentil) 1kg", "grocery", 130, 150),
        ("ACI Pure Atta (Flour) 2kg", "grocery", 115, 135), ("Fresh Semai (Vermicelli) 200g", "grocery", 30, 40),
    ],
    "restaurant": [
        ("Chicken Biryani (Plate)", "main_course", 160, 280), ("Beef Tehari (Plate)", "main_course", 150, 260),
        ("Kacchi Biryani (Plate)", "main_course", 220, 380), ("Plain Rice with Chicken Curry", "main_course", 90, 160),
        ("Beef Curry with Paratha", "main_course", 110, 190), ("Mixed Vegetable Curry", "main_course", 60, 110),
        ("Fish Curry (Rui) with Rice", "main_course", 130, 220), ("Chicken Roast", "main_course", 140, 240),
        ("Khasir Mangsho (Mutton Curry)", "main_course", 250, 420), ("Dal with Rice", "main_course", 40, 75),
        ("Chicken Fried Rice", "fast_food", 120, 200), ("Chicken Burger", "fast_food", 90, 160),
        ("Beef Shawarma", "fast_food", 110, 190), ("Chicken Shingara (per piece)", "snack", 8, 15),
        ("Samosa (per piece)", "snack", 8, 15), ("Fuchka (plate)", "snack", 40, 70),
        ("Chotpoti (plate)", "snack", 50, 90), ("Haleem (bowl)", "snack", 70, 120),
        ("Borhani 250ml", "beverage", 25, 40),
        ("Lassi (glass)", "beverage", 40, 70), ("Cold Coffee", "beverage", 90, 150),
        ("Lemon Tea", "beverage", 15, 30), ("Masala Chai", "beverage", 12, 25),
        ("Mango Shake", "beverage", 80, 140), ("Rasmalai (2 pieces)", "dessert", 60, 110),
        ("Mishti Doi (bowl)", "dessert", 40, 70), ("Firni (bowl)", "dessert", 35, 60),
        ("Gulab Jamun (2 pieces)", "dessert", 40, 70),
    ],
    "fashion": [
        ("Aarong Cotton Panjabi", "menswear", 850, 1450), ("Yellow Men's Casual Shirt", "menswear", 650, 1100),
        ("Westecs Slim Fit Shirt", "menswear", 700, 1200), ("Ecstasy Men's T-Shirt", "menswear", 350, 650),
        ("Cats Eye Formal Trouser", "menswear", 900, 1500), ("Sailor Men's Jeans", "menswear", 950, 1600),
        ("Aarong Printed Saree (Cotton)", "womenswear", 1800, 3200), ("Rang Bangladesh Salwar Kameez", "womenswear", 1400, 2400),
        ("Kay Kraft Three-Piece", "womenswear", 1600, 2800), ("Le Reve Women's Kurti", "womenswear", 700, 1200),
        ("Anjan's Designer Saree", "womenswear", 2200, 3800), ("Dorjibari Women's Abaya", "womenswear", 1500, 2600),
        ("Bata Men's Formal Shoe", "footwear", 1800, 2800), ("Apex Men's Leather Shoe", "footwear", 2000, 3200),
        ("Bay Emporium Women's Sandal", "footwear", 900, 1500), ("Lotto Sports Shoe", "footwear", 2500, 4000),
        ("Bashundhara Kids T-Shirt", "kidswear", 300, 550), ("Kids Panjabi (Eid Collection)", "kidswear", 600, 1100),
        ("Shimmer Women's Scarf (Hijab)", "accessory", 250, 450), ("Rico Men's Belt (Leather)", "accessory", 450, 750),
        ("Walton Fashion Watch", "accessory", 800, 1400), ("Easy Fashion Ladies Bag", "accessory", 900, 1600),
    ],
    "electronics": [
        ("Walton Refrigerator 253L", "appliance", 32000, 42000), ("Walton WRAD Washing Machine 7kg", "appliance", 28000, 38000),
        ("Singer LED TV 43 inch", "appliance", 30000, 40000), ("Walton LED TV 32 inch", "appliance", 14000, 19000),
        ("Vision Rice Cooker 1.8L", "appliance", 2200, 3200), ("Walton Microwave Oven 20L", "appliance", 9500, 13500),
        ("Miyako Blender", "appliance", 1800, 2800), ("Walton Air Conditioner 1 Ton", "appliance", 42000, 56000),
        ("Jamuna Electric Fan (Ceiling)", "appliance", 1800, 2600), ("Walton Iron (Steam)", "appliance", 1400, 2100),
        ("Samsung Galaxy A15 Smartphone", "mobile", 18500, 22000), ("Xiaomi Redmi 13C", "mobile", 13500, 16500),
        ("Symphony Z25 Feature Phone", "mobile", 1500, 2200), ("Walton Primo RX8 Mini", "mobile", 7500, 9500),
        ("Realme C53 Smartphone", "mobile", 16000, 19500), ("HP 15 Laptop (Core i3)", "computing", 48000, 58000),
        ("Walton Tamarind Laptop", "computing", 42000, 52000), ("Dell Vostro Laptop (Core i5)", "computing", 62000, 75000),
        ("A4Tech Wireless Mouse", "computing", 500, 850), ("Logitech Keyboard & Mouse Combo", "computing", 1200, 1900),
        ("Transcend 32GB Pendrive", "accessory", 450, 700), ("Anker Power Bank 10000mAh", "accessory", 1800, 2600),
        ("JBL Bluetooth Speaker (Go 3)", "accessory", 3500, 4800), ("Havit Wired Earphone", "accessory", 250, 450),
        ("Walton Extension Socket", "accessory", 350, 550),
    ],
}

PRODUCTS_PER_ORG = 50
CUSTOMERS_PER_ORG = 90
MONTHS_OF_HISTORY = 15
AVG_INVOICES_PER_DAY = (8, 22)  # weekday range; Fri/Sat get a multiplier below
RETURN_RATE = 0.045


def _price_for(row) -> tuple[Decimal, Decimal]:
    """Deterministic but varied BDT prices, Rx items priced higher."""
    base = 15 + (hash(row.Product_ID) % 180)
    cost = Decimal(base)
    markup = Decimal("1.35") if row.Prescription_Only else Decimal("1.22")
    selling = (cost * markup).quantize(Decimal("1"))
    return cost, selling


def seed_organization(db, spec: dict) -> None:
    org = db.query(Organization).filter_by(slug=spec["slug"]).first()
    if org is not None:
        print(f"skip (exists): {spec['name']}")
        return

    org = Organization(name=spec["name"], slug=spec["slug"], sector=spec.get("vertical", "pharmacy"))
    db.add(org)
    db.flush()

    owner_email = f"owner@{spec['slug']}.bsmart.local"
    stale = db.query(User).filter_by(email=owner_email).first()
    if stale is not None:
        db.delete(stale)
        db.flush()
    owner = User(email=owner_email, display_name=f"{spec['name']} মালিক",
                 password_hash=hash_password(DEMO_PASSWORD))
    db.add(owner)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=owner.id, role="owner"))

    branch = Branch(organization_id=org.id, code="MAIN", name=spec["branch"],
                     division=spec["division"], district=spec["district"])
    db.add(branch)
    db.flush()

    suppliers = []
    for i, name in enumerate(SUPPLIER_NAMES):
        s = Supplier(organization_id=org.id, code=f"SUP-{i+1}", name=name,
                     typical_lead_days=random.choice([3, 5, 7, 10]))
        db.add(s)
        suppliers.append(s)
    db.flush()

    vertical = spec.get("vertical", "pharmacy")
    products = []
    if vertical == "pharmacy":
        catalog_slice = CATALOG.sample(n=min(PRODUCTS_PER_ORG, len(CATALOG)), random_state=hash(spec["slug"]) % (2**31))
        for row in catalog_slice.itertuples():
            cost, selling = _price_for(row)
            p = Product(
                organization_id=org.id, sku=row.Product_ID, name=row.Product_Name,
                category="prescription" if row.Prescription_Only else "otc",
                unit="pcs", selling_price=selling, cost_price=cost,
                reorder_level=Decimal(10), track_expiry=False, active=True,
            )
            db.add(p)
            products.append(p)
    else:
        for i, (name, category, cost, selling) in enumerate(VERTICAL_CATALOGS[vertical]):
            p = Product(
                organization_id=org.id, sku=f"{vertical.upper()[:3]}-{i+1:03d}", name=name,
                category=category, unit="pcs",
                selling_price=Decimal(selling), cost_price=Decimal(cost),
                reorder_level=Decimal(10), track_expiry=False, active=True,
            )
            db.add(p)
            products.append(p)
    db.flush()
    for p in products:
        db.add(InventoryBalance(organization_id=org.id, branch_id=branch.id,
                                 product_id=p.id, quantity=Decimal(500)))

    pool = CUSTOMERS_POOL.iloc[spec["customer_offset"]: spec["customer_offset"] + CUSTOMERS_PER_ORG]
    customers = []
    for i, row in enumerate(pool.itertuples()):
        c = Customer(
            organization_id=org.id, code=f"CUST-{i+1:03d}",
            display_name=row.Customer_Name, marketing_consent=bool(row.Marketing_Consent),
            price_tier="retail",
        )
        db.add(c)
        customers.append(c)
    db.flush()

    print(f"seeded shell: {spec['name']} ({len(products)} products, {len(customers)} customers)")
    _seed_sales_history(db, org, branch, products, customers)


def _seed_sales_history(db, org, branch, products, customers) -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=MONTHS_OF_HISTORY * 30)
    # A realistic loyalty split: most invoices from a core repeat group
    # (so churn/segmentation features have real recency variance), the rest
    # one-off walk-ins recorded against no customer.
    regulars = random.sample(customers, k=max(1, len(customers) // 2))
    invoice_no = 0
    order_rows, item_rows, inventory_deltas = [], [], {}

    day = start
    while day < now:
        is_weekend = day.weekday() in (4, 5)  # Bangladesh Fri/Sat
        month_factor = 1.0 + 0.15 * (1 if day.month in (4, 10, 11) else 0)  # mild seasonality
        n_invoices = int(random.randint(*AVG_INVOICES_PER_DAY) * (1.3 if is_weekend else 1.0) * month_factor)
        for _ in range(n_invoices):
            invoice_no += 1
            use_regular = random.random() < 0.55
            customer = random.choice(regulars) if use_regular else (
                random.choice(customers) if random.random() < 0.3 else None
            )
            n_items = random.randint(1, 4)
            chosen = random.sample(products, k=min(n_items, len(products)))
            sold_at = day + timedelta(hours=random.randint(9, 20), minutes=random.randint(0, 59))
            subtotal = Decimal(0)
            local_items = []
            for product in chosen:
                qty = Decimal(random.randint(1, 3))
                discount = Decimal(0)
                line_total = (product.selling_price * qty) - discount
                subtotal += line_total
                local_items.append((product, qty, discount, line_total))
            order = SalesOrder(
                organization_id=org.id, branch_id=branch.id,
                customer_id=customer.id if customer else None,
                invoice_number=f"INV-{org.id[:8]}-{invoice_no}", sold_at=sold_at,
                channel="in_store", status="completed",
                subtotal=subtotal, discount_amount=Decimal(0), tax_amount=Decimal(0),
                total=subtotal,
            )
            db.add(order)
            db.flush()
            for product, qty, discount, line_total in local_items:
                returned = Decimal(0)
                will_return = random.random() < RETURN_RATE
                item = SalesOrderItem(
                    organization_id=org.id, order_id=order.id, product_id=product.id,
                    quantity=qty, unit_price=product.selling_price,
                    unit_cost_at_sale=product.cost_price, discount_amount=discount,
                    line_total=line_total, returned_quantity=qty if will_return else Decimal(0),
                )
                db.add(item)
                db.flush()
                key = product.id
                inventory_deltas[key] = inventory_deltas.get(key, Decimal(0)) + qty
                if will_return:
                    sr = SalesReturn(
                        organization_id=org.id, branch_id=branch.id, sales_order_id=order.id,
                        return_number=f"RET-{org.id[:8]}-{invoice_no}-{product.sku}",
                        reason=random.choice(["damaged", "wrong_item", "customer_changed_mind"]),
                        returned_at=sold_at + timedelta(days=random.randint(1, 10)),
                        total=line_total,
                    )
                    db.add(sr)
                    db.flush()
                    db.add(SalesReturnItem(
                        organization_id=org.id, sales_return_id=sr.id, sales_order_item_id=item.id,
                        product_id=product.id, quantity=qty, amount=line_total, restock=False,
                    ))
        day += timedelta(days=1)
        db.flush()

    for product_id, delta in inventory_deltas.items():
        bal = db.query(InventoryBalance).filter_by(
            organization_id=org.id, branch_id=branch.id, product_id=product_id,
        ).first()
        if bal:
            bal.quantity = max(Decimal(0), bal.quantity - delta)
    db.commit()
    print(f"  -> {invoice_no} invoices across {MONTHS_OF_HISTORY} months")


def train_models_for(org_id: str) -> None:
    from api.canonical_sales import canonical_sales_frame
    from ml.real_pipeline import train_churn, train_forecast, train_returns, train_segments, validate_sales

    db = SessionLocal()
    try:
        frame = canonical_sales_frame(db, org_id)
        if frame.empty:
            print(f"  no sales for {org_id}, skipping training")
            return
        sales = validate_sales(frame)
        output_dir = Path("artifacts/real") / org_id
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, trainer in [
            ("forecast", train_forecast), ("churn", train_churn),
            ("segments", train_segments), ("return_risk", train_returns),
        ]:
            try:
                result = trainer(sales, output_dir)
                print(f"  {name}: trained ({result.get('train_rows', result.get('customers', '?'))} rows)")
            except ValueError as exc:
                print(f"  {name}: skipped ({exc})")
    finally:
        db.close()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    org_ids = []
    try:
        for spec in ORGS:
            seed_organization(db, spec)
        orgs = db.query(Organization).filter(Organization.slug.in_([s["slug"] for s in ORGS])).all()
        org_ids = [o.id for o in orgs]
    finally:
        db.close()

    for org_id in org_ids:
        print(f"training models for {org_id}")
        train_models_for(org_id)

    print(f"\nDone. Password for every seeded owner: {DEMO_PASSWORD}")
    for spec in ORGS:
        print(f"  {spec['name']}: owner@{spec['slug']}.bsmart.local")


if __name__ == "__main__":
    main()
