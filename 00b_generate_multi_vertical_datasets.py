"""
00b_generate_multi_vertical_datasets.py
Generate realistic Bangladesh SME datasets for 5 business verticals.

Schema design
─────────────
Universal core (all verticals):
  transaction_id, customer_id, customer_name, phone, city, marketing_consent,
  product_id, product_name, category, quantity, unit_price_bdt,
  discount_amount_bdt, total_amount_bdt, transaction_date,
  month, year, quarter, crm_tier, vertical, dataset_type

Vertical-specific extensions (auto-detected by pipeline):
  pharmacy    → expiry_date, batch_no, drug_class, prescription_required
  grocery     → weight_unit, perishable, shelf_life_days
  clothing    → size, gender, season, fabric
  restaurant  → meal_time, order_type
  electronics → brand, warranty_months, product_condition

The pipeline adapter reads which columns are present and runs
universal models always, then vertical-specific models when columns exist.

Verticals:
  pharmacy    — medicines, OTC, vitamins
  grocery     — general grocery / kirana store
  clothing    — ready-made garments
  restaurant  — food & beverage
  electronics — mobile accessories & electronics

Run:
  python 00b_generate_multi_vertical_datasets.py
  python 00b_generate_multi_vertical_datasets.py --vertical grocery
  python 00b_generate_multi_vertical_datasets.py --vertical all

Outputs → normalized_data/verticals/<vertical>/<vertical>_dataset.csv
"""
import utf8_console  # noqa: F401 — must be first
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

OUT_DIR = Path("normalized_data/verticals")
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_CUSTOMERS   = 4_500
N_PRODUCTS    = 200
N_TRANSACTIONS = 30_000
START_DATE    = date(2022, 1, 1)
END_DATE      = date(2024, 12, 31)

# ── Helpers ─────────────────────────────────────────────────────────────────

def bd_male_names():
    return [
        "Rahim", "Karim", "Hasan", "Hossain", "Islam", "Ahmed", "Ali", "Khan",
        "Miah", "Sarkar", "Siddiqui", "Chowdhury", "Begum", "Akter", "Khatun",
        "Sultana", "Parveen", "Nasrin", "Fatema", "Rima", "Nila", "Sonia",
        "Shapla", "Mitu", "Shirin", "Ruhul", "Shahadat", "Farhan", "Sabbir",
        "Tanvir", "Shahed", "Riaz", "Rakib", "Rasel", "Polash", "Masum",
        "Mamun", "Mizan", "Rubel", "Jewel",
    ]

def random_bd_name():
    firsts = ["Md.", "A.", "S.", "M.", "R.", "T.", "F.", "N.", "K.", "H."]
    lasts  = bd_male_names()
    return f"{random.choice(firsts)} {random.choice(lasts)}"

def random_bd_phone():
    prefix = random.choice(["017", "018", "019", "013", "014", "015", "016"])
    return prefix + "".join(str(random.randint(0, 9)) for _ in range(8))

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta + 1)))

def seasonal_weight(d: date) -> float:
    """Higher weight in Oct-Dec (Eid ul-Adha, winter) and Mar-Apr (Eid ul-Fitr)."""
    m = d.month
    if m in (10, 11, 12, 3, 4):
        return 2.0
    if m in (1, 2, 5, 6):
        return 0.8
    return 1.0

def make_customers(n: int) -> pd.DataFrame:
    rows = []
    cities = ["Dhaka", "Chittagong", "Sylhet", "Rajshahi", "Khulna",
              "Barishal", "Comilla", "Mymensingh", "Gazipur", "Narayanganj"]
    for i in range(1, n + 1):
        rows.append({
            "Customer_ID": f"CUST{i:05d}",
            "Customer_Name": random_bd_name(),
            "Phone": random_bd_phone(),
            "City": random.choice(cities),
            "Marketing_Consent": int(rng.random() < 0.55),
        })
    return pd.DataFrame(rows)

# ── Vertical definitions ─────────────────────────────────────────────────────

VERTICALS = {

    "pharmacy": {
        "description": "Retail pharmacy — medicines, OTC, vitamins",
        "categories": {
            "Antibiotics":       (80,  350,  0.12),
            "Analgesics":        (15,   80,  0.20),
            "Vitamins":          (120, 600,  0.15),
            "Antidiabetics":     (200, 900,  0.08),
            "Antihypertensives": (150, 700,  0.08),
            "Antihistamines":    (25,  120,  0.12),
            "Antacids":          (20,   90,  0.10),
            "OTC_General":       (10,   60,  0.15),
        },
        "products": [
            ("Napa 500mg","Analgesics"), ("Azithromycin 250mg","Antibiotics"),
            ("Metformin 500mg","Antidiabetics"), ("Amlodipine 5mg","Antihypertensives"),
            ("Cetirizine 10mg","Antihistamines"), ("Omeprazole 20mg","Antacids"),
            ("Vitamin C 500mg","Vitamins"), ("Paracetamol 500mg","Analgesics"),
            ("Amoxicillin 250mg","Antibiotics"), ("Zinc 20mg","Vitamins"),
            ("Calcium 500mg","Vitamins"), ("B-Complex","Vitamins"),
            ("Ranitidine 150mg","Antacids"), ("Losartan 50mg","Antihypertensives"),
            ("Glibenclamide 5mg","Antidiabetics"), ("Fexofenadine 120mg","Antihistamines"),
            ("Ibuprofen 400mg","Analgesics"), ("Ciprofloxacin 500mg","Antibiotics"),
            ("Metronidazole 400mg","Antibiotics"), ("ORS Saline","OTC_General"),
            ("Cough Syrup 100ml","OTC_General"), ("Eye Drop 5ml","OTC_General"),
            ("Antifungal Cream","OTC_General"), ("Insulin 10ml vial","Antidiabetics"),
            ("Lisinopril 10mg","Antihypertensives"),
        ],
    },

    "grocery": {
        "description": "General grocery / kirana store",
        "categories": {
            "Rice_Dal":     (50,  200,  0.25),
            "Oil_Ghee":     (150, 350,  0.12),
            "Spices":       (20,   80,  0.15),
            "Flour_Suji":   (40,  160,  0.10),
            "Sugar_Salt":   (15,   80,  0.10),
            "Biscuit_Snack":(20,  120,  0.12),
            "Soap_Detergent":(30, 200,  0.10),
            "Dairy":        (40,  250,  0.06),
        },
        "products": [
            ("মিনিকেট চাল (5kg)","Rice_Dal"), ("ব্রি-২৮ চাল (5kg)","Rice_Dal"),
            ("মসুর ডাল (1kg)","Rice_Dal"), ("মুগ ডাল (500g)","Rice_Dal"),
            ("সয়াবিন তেল (1L)","Oil_Ghee"), ("সরিষার তেল (1L)","Oil_Ghee"),
            ("ঘি ৫০০মি.লি.","Oil_Ghee"), ("হলুদ গুঁড়া ২০০গ্রাম","Spices"),
            ("মরিচ গুঁড়া ২০০গ্রাম","Spices"), ("ধনিয়া গুঁড়া ২০০গ্রাম","Spices"),
            ("আটা (2kg)","Flour_Suji"), ("সুজি ৫০০গ্রাম","Flour_Suji"),
            ("চিনি (1kg)","Sugar_Salt"), ("লবণ ১কেজি","Sugar_Salt"),
            ("টিসু বিস্কুট","Biscuit_Snack"), ("চানাচুর ২০০গ্রাম","Biscuit_Snack"),
            ("লাক্স সাবান","Soap_Detergent"), ("সার্ফ এক্সেল ৫০০গ্রাম","Soap_Detergent"),
            ("ঘোল/মাঠা ২৫০মি.লি.","Dairy"), ("দুধ ১লিটার","Dairy"),
            ("ডিম (১ হালি)","Dairy"), ("আলু (1kg)","Rice_Dal"),
            ("পেঁয়াজ (1kg)","Spices"), ("রসুন (250g)","Spices"),
            ("আদা (200g)","Spices"),
        ],
    },

    "clothing": {
        "description": "Ready-made garments & clothing boutique",
        "categories": {
            "Mens_Shirt":    (350, 1200, 0.18),
            "Womens_Dress":  (400, 1800, 0.20),
            "Kids_Clothing": (200,  900, 0.12),
            "Traditional":   (600, 3500, 0.15),
            "Pants_Jeans":   (500, 1600, 0.12),
            "Accessories":   (80,   600, 0.10),
            "Undergarments": (60,   300, 0.13),
        },
        "products": [
            ("ফর্মাল শার্ট সাদা","Mens_Shirt"), ("কটন শার্ট নীল","Mens_Shirt"),
            ("পাঞ্জাবি ঈদ স্পেশাল","Traditional"), ("লুঙ্গি চেক প্রিন্ট","Traditional"),
            ("শাড়ি কটন","Traditional"), ("সালোয়ার কামিজ সেট","Womens_Dress"),
            ("ক্যাজুয়াল টপ","Womens_Dress"), ("নাইটি সেট","Womens_Dress"),
            ("ছেলেদের টি-শার্ট","Kids_Clothing"), ("মেয়েদের ফ্রক","Kids_Clothing"),
            ("বাচ্চার পায়জামা সেট","Kids_Clothing"), ("জিন্স প্যান্ট পুরুষ","Pants_Jeans"),
            ("স্লিম ফিট প্যান্ট","Pants_Jeans"), ("লেগিংস কটন","Pants_Jeans"),
            ("হিজাব প্রিন্ট","Accessories"), ("বেল্ট লেদার","Accessories"),
            ("মোজা জুটি","Accessories"), ("আন্ডারওয়্যার পুরুষ","Undergarments"),
            ("ব্রা সেট","Undergarments"), ("শিশু আন্ডারগার্মেন্ট","Undergarments"),
            ("কামিজ ব্লক প্রিন্ট","Womens_Dress"), ("শিফন ওড়না","Accessories"),
            ("টাই ফর্মাল","Accessories"), ("থ্রি-পিস সেট","Womens_Dress"),
            ("বাচ্চার শীতের জ্যাকেট","Kids_Clothing"),
        ],
    },

    "restaurant": {
        "description": "Food & beverage — dine-in and takeaway",
        "categories": {
            "Rice_Curry":   (80,  250, 0.28),
            "Biryani":      (150, 350, 0.18),
            "Roti_Paratha": (15,   60, 0.15),
            "Drinks":       (20,   80, 0.12),
            "Sweets":       (30,  150, 0.10),
            "Snacks":       (20,  100, 0.10),
            "Iftar_Special":(50,  200, 0.07),
        },
        "products": [
            ("ভাত + মাছের তরকারি","Rice_Curry"), ("ভাত + মুরগির তরকারি","Rice_Curry"),
            ("ভাত + গরুর মাংস","Rice_Curry"), ("ভাত + ডাল + সবজি","Rice_Curry"),
            ("চিকেন বিরিয়ানি","Biryani"), ("মাটন বিরিয়ানি","Biryani"),
            ("ভেজ বিরিয়ানি","Biryani"), ("পরোটা + ডিম ভাজি","Roti_Paratha"),
            ("তন্দুর রুটি","Roti_Paratha"), ("নান রুটি","Roti_Paratha"),
            ("লেমন সোডা","Drinks"), ("মাঙ্গো লাচ্ছি","Drinks"),
            ("চা মালাই","Drinks"), ("কোল্ড কফি","Drinks"),
            ("রসগোল্লা","Sweets"), ("মিষ্টি দই","Sweets"),
            ("চমচম","Sweets"), ("সিঙ্গারা ২ পিস","Snacks"),
            ("সমুচা ২ পিস","Snacks"), ("পেঁয়াজু ৫ পিস","Snacks"),
            ("পিয়াজু বিশেষ","Snacks"), ("ইফতার প্যাকেজ ছোট","Iftar_Special"),
            ("ইফতার প্যাকেজ বড়","Iftar_Special"), ("খেজুর ৫০০গ্রাম","Iftar_Special"),
            ("হালিম বড় বাটি","Rice_Curry"),
        ],
    },

    "electronics": {
        "description": "Mobile accessories & consumer electronics",
        "categories": {
            "Phone_Case":       (50,   350, 0.20),
            "Charger_Cable":    (80,   600, 0.18),
            "Earphone":         (150, 1200, 0.12),
            "Screen_Guard":     (30,   200, 0.15),
            "Power_Bank":       (600, 2500, 0.08),
            "Smart_Watch":      (800, 4500, 0.07),
            "Memory_Storage":   (200, 1800, 0.10),
            "Lighting_Small":   (100,  800, 0.10),
        },
        "products": [
            ("আইফোন কভার ট্রান্সপারেন্ট","Phone_Case"), ("স্যামসাং কেস শকপ্রুফ","Phone_Case"),
            ("ওয়ালটন ব্যাক কভার","Phone_Case"), ("সিম্পো ফোন কভার","Phone_Case"),
            ("টাইপ-C চার্জার ২০W","Charger_Cable"), ("মাইক্রো USB ক্যাবল","Charger_Cable"),
            ("ওয়্যারলেস চার্জার ১৫W","Charger_Cable"), ("ট্রাভেল চার্জার ২ পোর্ট","Charger_Cable"),
            ("ব্লুটুথ ইয়ারফোন","Earphone"), ("ওয়্যার্ড ইয়ারফোন বেসিক","Earphone"),
            ("নেকব্যান্ড হেডফোন","Earphone"), ("টেম্পার্ড গ্লাস স্যামসাং","Screen_Guard"),
            ("স্ক্রিন প্রটেক্টর আইফোন","Screen_Guard"), ("পাওয়ার ব্যাংক ১০০০০mAh","Power_Bank"),
            ("পাওয়ার ব্যাংক ২০০০০mAh","Power_Bank"), ("স্মার্ট ওয়াচ বেসিক","Smart_Watch"),
            ("ফিটনেস ব্যান্ড","Smart_Watch"), ("মাইক্রো SD কার্ড ৩২GB","Memory_Storage"),
            ("পেনড্রাইভ ৬৪GB","Memory_Storage"), ("OTG অ্যাডাপ্টার","Memory_Storage"),
            ("LED ডেস্ক ল্যাম্প","Lighting_Small"), ("USB ফ্যান মিনি","Lighting_Small"),
            ("স্মার্ট বাল্ব WiFi","Lighting_Small"), ("এক্সটেনশন বোর্ড ৪ পোর্ট","Lighting_Small"),
            ("ক্যামেরা কভার স্টিকার","Phone_Case"),
        ],
    },
}

# ── Vertical-specific field generators ───────────────────────────────────────

PHARMACY_DRUG_CLASS = {
    "Antibiotics":       ("antibiotic",   True),
    "Analgesics":        ("analgesic",    False),
    "Vitamins":          ("supplement",   False),
    "Antidiabetics":     ("antidiabetic", True),
    "Antihypertensives": ("antihypertensive", True),
    "Antihistamines":    ("antihistamine", False),
    "Antacids":          ("antacid",      False),
    "OTC_General":       ("otc",          False),
}

CLOTHING_SIZES    = ["XS", "S", "M", "L", "XL", "XXL"]
CLOTHING_GENDERS  = ["male", "female", "kids", "unisex"]
CLOTHING_SEASONS  = ["summer", "winter", "eid", "all-season"]
CLOTHING_FABRICS  = ["cotton", "polyester", "linen", "silk", "denim", "georgette"]

RESTAURANT_MEALTIMES  = ["morning", "lunch", "afternoon", "evening", "dinner"]
RESTAURANT_ORDER_TYPES = ["dine_in", "takeaway", "delivery"]

ELECTRONICS_BRANDS    = ["Samsung", "Xiaomi", "Walton", "Symphony", "Realme",
                          "Oppo", "Vivo", "itel", "Tecno", "Generic"]
ELECTRONICS_CONDITIONS = ["new", "new", "new", "refurbished"]

GROCERY_WEIGHT_UNITS  = ["kg", "g", "pcs", "litre", "ml", "dozen"]
GROCERY_PERISHABLE_MAP = {
    "Rice_Dal": (False, 365), "Oil_Ghee": (False, 180),
    "Spices": (False, 270), "Flour_Suji": (False, 180),
    "Sugar_Salt": (False, 730), "Biscuit_Snack": (False, 90),
    "Soap_Detergent": (False, 730), "Dairy": (True, 7),
}


def _vertical_fields(vertical: str, cat: str, prod_name: str, d: date) -> dict:
    """Return extra columns for the given vertical."""
    if vertical == "pharmacy":
        drug_class, rx = PHARMACY_DRUG_CLASS.get(cat, ("otc", False))
        shelf = int(rng.integers(180, 730))
        return {
            "Drug_Class":             drug_class,
            "Prescription_Required":  int(rx),
            "Batch_No":               f"B{int(rng.integers(1000, 9999))}",
            "Expiry_Date":            (d + timedelta(days=shelf)).isoformat(),
        }
    elif vertical == "grocery":
        perishable, shelf_days = GROCERY_PERISHABLE_MAP.get(cat, (False, 180))
        return {
            "Weight_Unit":     random.choice(GROCERY_WEIGHT_UNITS),
            "Perishable":      int(perishable),
            "Shelf_Life_Days": shelf_days,
        }
    elif vertical == "clothing":
        return {
            "Size":    random.choice(CLOTHING_SIZES),
            "Gender":  random.choice(CLOTHING_GENDERS),
            "Season":  random.choice(CLOTHING_SEASONS),
            "Fabric":  random.choice(CLOTHING_FABRICS),
        }
    elif vertical == "restaurant":
        return {
            "Meal_Time":  random.choice(RESTAURANT_MEALTIMES),
            "Order_Type": random.choice(RESTAURANT_ORDER_TYPES),
        }
    elif vertical == "electronics":
        return {
            "Brand":             random.choice(ELECTRONICS_BRANDS),
            "Warranty_Months":   int(rng.choice([0, 6, 12, 24])),
            "Product_Condition": random.choice(ELECTRONICS_CONDITIONS),
        }
    return {}


# ── Dataset builder ──────────────────────────────────────────────────────────

def build_dataset(vertical: str, spec: dict) -> pd.DataFrame:
    customers = make_customers(N_CUSTOMERS)
    cats      = spec["categories"]
    products  = spec["products"][:N_PRODUCTS]

    # Build product table
    prod_rows = []
    for pname, cat in products:
        lo, hi, _ = cats[cat]
        unit_price = round(rng.uniform(lo, hi), 2)
        prod_rows.append({
            "Product_ID":     f"P{len(prod_rows)+1:04d}",
            "Product_Name":   pname,
            "Category":       cat,
            "Unit_Price_BDT": unit_price,
        })
    prod_df = pd.DataFrame(prod_rows)

    # Pick product per transaction weighted by category demand multiplier
    cat_weight = {c: v[2] for c, v in cats.items()}
    prod_cat_w = prod_df["Category"].map(cat_weight).values
    prod_cat_w = prod_cat_w / prod_cat_w.sum()

    dates = [random_date(START_DATE, END_DATE) for _ in range(N_TRANSACTIONS)]

    rows = []
    for i, d in enumerate(dates):
        cust  = customers.iloc[int(rng.integers(0, N_CUSTOMERS))]
        prod  = prod_df.iloc[rng.choice(len(prod_df), p=prod_cat_w)]
        qty   = int(rng.integers(1, 6))
        price = prod["Unit_Price_BDT"]
        disc_pct = float(rng.choice([0, 0, 0, 0.05, 0.10, 0.15]))
        disc_amt  = round(price * qty * disc_pct, 2)
        total     = round(price * qty - disc_amt, 2)

        row = {
            # ── Universal core ──────────────────────────────────────────────
            "Transaction_ID":       f"TXN{i+1:07d}",
            "Customer_ID":          cust["Customer_ID"],
            "Customer_Name":        cust["Customer_Name"],
            "Phone":                cust["Phone"],
            "City":                 cust["City"],
            "Marketing_Consent":    cust["Marketing_Consent"],
            "Product_ID":           prod["Product_ID"],
            "Product_Name":         prod["Product_Name"],
            "Category":             prod["Category"],
            "Quantity":             qty,
            "Unit_Price_BDT":       price,
            "Discount_Amount_BDT":  disc_amt,
            "Total_Amount_BDT":     total,
            "Transaction_Date":     d.isoformat(),
            "Month":                d.month,
            "Year":                 d.year,
            "Quarter":              (d.month - 1) // 3 + 1,
            "Vertical":             vertical,
            "Dataset_Type":         "declared_synthetic",
        }
        # ── Vertical-specific extras ────────────────────────────────────────
        row.update(_vertical_fields(vertical, prod["Category"], prod["Product_Name"], d))
        rows.append(row)

    df = pd.DataFrame(rows)

    # Derive CRM tier from total spend (universal)
    spend = df.groupby("Customer_ID")["Total_Amount_BDT"].sum()
    q = spend.quantile([0.35, 0.65, 0.85]).values
    def crm_tier(s):
        if s <= q[0]: return "Low"
        if s <= q[1]: return "Moderate"
        if s <= q[2]: return "High"
        return "VIP"
    df["CRM_Tier"] = df["Customer_ID"].map(spend.map(crm_tier))

    return df.sort_values("Transaction_Date").reset_index(drop=True)


def generate(vertical: str):
    spec = VERTICALS[vertical]
    print(f"→ Generating {vertical} dataset ({spec['description']})…")
    df = build_dataset(vertical, spec)
    out = OUT_DIR / vertical
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{vertical}_dataset.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  ✓ {len(df):,} rows → {path}")
    # Write a mini manifest
    manifest_lines = [
        f"# {vertical}_dataset.csv manifest",
        f"vertical: {vertical}",
        f"description: {spec['description']}",
        f"rows: {len(df)}",
        f"customers: {df['Customer_ID'].nunique()}",
        f"products: {df['Product_ID'].nunique()}",
        f"date_range: {df['Transaction_Date'].min()} to {df['Transaction_Date'].max()}",
        "dataset_type: declared_synthetic",
        "real_columns: none (all synthetic; uses BD price bands and seasonal shape)",
    ]
    (out / "MANIFEST.md").write_text("\n".join(manifest_lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default="all",
                        choices=list(VERTICALS.keys()) + ["all"])
    args = parser.parse_args()

    targets = list(VERTICALS.keys()) if args.vertical == "all" else [args.vertical]
    for v in targets:
        generate(v)

    print("\n✓ Done. Datasets in normalized_data/verticals/")
