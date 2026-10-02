"""
00c_generate_additional_datasets.py
Two additional Bangladesh SME vertical datasets for the research portal.

Verticals:
  auto_parts  — motorbike / CNG auto-rickshaw spare parts (highly BD-specific)
  stationery  — school & office stationery, books, art supplies

Schema matches 00b — same universal core + vertical-specific columns.

Run:
  python 00c_generate_additional_datasets.py
  python 00c_generate_additional_datasets.py --vertical auto_parts
  python 00c_generate_additional_datasets.py --vertical stationery
"""
import utf8_console  # noqa: F401
import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 43
rng = np.random.default_rng(SEED)
random.seed(SEED)

OUT_DIR = Path("normalized_data/verticals")
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_CUSTOMERS    = 3_500
N_TRANSACTIONS = 30_000
START_DATE     = date(2022, 1, 1)
END_DATE       = date(2024, 12, 31)

# ── Name helpers (same as 00b) ────────────────────────────────────────────────

BD_LAST_NAMES = [
    "Rahim", "Karim", "Hasan", "Hossain", "Islam", "Ahmed", "Ali", "Khan",
    "Miah", "Sarkar", "Siddiqui", "Chowdhury", "Mondal", "Bepari", "Pramanik",
    "Dey", "Roy", "Das", "Sen", "Biswas", "Majumder", "Ghosh",
]

def random_bd_name():
    firsts = ["Md.", "A.", "S.", "M.", "R.", "T.", "F.", "N.", "K.", "H."]
    return f"{random.choice(firsts)} {random.choice(BD_LAST_NAMES)}"

def random_bd_phone():
    prefix = random.choice(["017", "018", "019", "013", "014", "015", "016"])
    return prefix + "".join(str(random.randint(0, 9)) for _ in range(8))

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta + 1)))

def seasonal_weight_auto(d: date) -> float:
    """Auto-parts peak: Eid (Apr, Jul), year-end vehicle service (Dec)."""
    if d.month in (4, 7, 12): return 2.0
    if d.month in (1, 2, 8):  return 0.75
    return 1.0

def seasonal_weight_stationery(d: date) -> float:
    """Stationery peak: Jan (new year), Jun (exams), Sep-Oct (new term)."""
    if d.month in (1, 6, 9, 10): return 2.2
    if d.month in (7, 8):        return 0.65
    return 1.0

def make_customers(n: int) -> pd.DataFrame:
    cities = ["Dhaka", "Chittagong", "Sylhet", "Rajshahi", "Khulna",
              "Barishal", "Comilla", "Mymensingh", "Gazipur", "Narayanganj",
              "Tangail", "Bogra", "Jessore", "Narsingdi", "Faridpur"]
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "Customer_ID":       f"CUST{i:05d}",
            "Customer_Name":     random_bd_name(),
            "Phone":             random_bd_phone(),
            "City":              random.choice(cities),
            "Marketing_Consent": int(rng.random() < 0.52),
        })
    return pd.DataFrame(rows)


# ── AUTO PARTS vertical ───────────────────────────────────────────────────────
# BD motorbike market dominated by Hero, Honda, Yamaha, Bajaj, TVS.
# CNG auto-rickshaw (3-wheelers) are everywhere.

AUTO_PARTS_CATEGORIES = {
    "Engine_Parts":       (150,  2500, 0.15),
    "Brake_System":       (80,   800,  0.12),
    "Electrical":         (60,   600,  0.18),
    "Body_Plastic":       (100,  1500, 0.12),
    "Chain_Sprocket":     (180,  900,  0.10),
    "Filter_Consumable":  (40,   350,  0.20),
    "Tyre_Tube":          (250, 1800,  0.08),
    "Light_Mirror":       (60,   500,  0.05),
}

AUTO_PARTS_PRODUCTS = [
    # Engine
    ("পিস্টন রিং সেট Honda CD80",      "Engine_Parts"),
    ("ক্র্যাংকশাফট সিল Bajaj Pulsar",   "Engine_Parts"),
    ("ক্লাচ প্লেট সেট Hero Splendor",  "Engine_Parts"),
    ("ইঞ্জিন গ্যাসকেট কিট Yamaha FZS", "Engine_Parts"),
    ("কার্বুরেটর CNG Three-Wheeler",    "Engine_Parts"),
    ("ভাল্ব সেট TVS Apache",            "Engine_Parts"),
    # Brake
    ("ব্রেক শু Honda CB",               "Brake_System"),
    ("ব্রেক ক্যালিপার Yamaha R15",      "Brake_System"),
    ("ব্রেক ওয়্যার সেট",               "Brake_System"),
    ("ডিস্ক ব্রেক প্যাড Bajaj",         "Brake_System"),
    # Electrical
    ("ব্যাটারি ১২V ৫Ah",                "Electrical"),
    ("স্পার্ক প্লাগ NGK CR6HSA",        "Electrical"),
    ("ইগনিশন কয়েল",                    "Electrical"),
    ("হেডলাইট বাল্ব H4",               "Electrical"),
    ("CDI ইউনিট Yamaha",                "Electrical"),
    ("রেগুলেটর রেকটিফায়ার",            "Electrical"),
    # Body
    ("ফ্রন্ট ফেন্ডার Honda Dream",      "Body_Plastic"),
    ("ফুয়েল ট্যাংক কভার Bajaj",        "Body_Plastic"),
    ("সাইড প্যানেল সেট Hero",           "Body_Plastic"),
    # Chain & Sprocket
    ("চেইন স্প্রকেট সেট ৪২T",          "Chain_Sprocket"),
    ("ড্রাইভ চেইন ৪২০ লিংক",           "Chain_Sprocket"),
    # Filters & consumables
    ("এয়ার ফিল্টার Honda",             "Filter_Consumable"),
    ("অয়েল ফিল্টার Bajaj",             "Filter_Consumable"),
    ("ইঞ্জিন অয়েল ৪T ১লিটার",         "Filter_Consumable"),
    ("Coolant ৫০০মিলি",                  "Filter_Consumable"),
    # Tyre
    ("টায়ার ২.৭৫-১৭ MRF",             "Tyre_Tube"),
    ("টিউব ২.৫০-১৭",                   "Tyre_Tube"),
    # Light & Mirror
    ("রিয়ার ভিউ মিরর জোড়া",           "Light_Mirror"),
    ("টার্ন সিগনাল লাইট",               "Light_Mirror"),
]

AUTO_PARTS_VEHICLE_TYPES  = ["motorbike", "motorbike", "motorbike", "CNG_auto", "bicycle", "car"]
AUTO_PARTS_BRANDS         = ["Honda", "Bajaj", "Yamaha", "TVS", "Hero", "Suzuki",
                              "Runner", "Walton", "Lifan", "Generic"]
AUTO_PARTS_CONDITION      = ["new", "new", "new", "reconditioned"]

def _auto_parts_fields(cat: str, d: date) -> dict:
    # vehicle_type driven by category
    if cat in ("Tyre_Tube", "Engine_Parts"):
        vtype = rng.choice(["motorbike", "CNG_auto", "car"])
    else:
        vtype = rng.choice(["motorbike", "motorbike", "CNG_auto"])
    brand = random.choice(AUTO_PARTS_BRANDS)
    part_no = f"PT-{random.choice(['HN','BJ','YM','TVS','HR'])}-{int(rng.integers(1000,9999))}"
    return {
        "Vehicle_Type":       vtype,
        "Brand":              brand,
        "Part_Number":        part_no,
        "Product_Condition":  random.choice(AUTO_PARTS_CONDITION),
        "Warranty_Days":      int(rng.choice([0, 0, 30, 90, 180])),
    }


# ── STATIONERY vertical ───────────────────────────────────────────────────────
# BD stationery: dominated by Navana (notebooks), BIC/Bic (pens),
# Camlin/Faber-Castell (art), Meril/Pilot, plus book publishers.

STATIONERY_CATEGORIES = {
    "Notebooks":          (25,   180, 0.20),
    "Pens_Pencils":       (8,    120, 0.25),
    "Art_Craft":          (30,   400, 0.12),
    "Paper_Files":        (20,   250, 0.12),
    "School_Supplies":    (15,   200, 0.15),
    "Office_Supplies":    (30,   500, 0.10),
    "Books_Publishers":   (80,   600, 0.06),
}

STATIONERY_PRODUCTS = [
    ("নাভানা নোটবুক ২০০ পাতা",        "Notebooks"),
    ("এক্সারসাইজ বুক লাইন্ড ১০০ পাতা","Notebooks"),
    ("ফুলস্ক্যাপ খাতা",               "Notebooks"),
    ("স্পাইরাল নোটবুক A5",            "Notebooks"),
    ("BIC বলপয়েন্ট পেন নীল",          "Pens_Pencils"),
    ("Pilot G-2 জেল পেন",              "Pens_Pencils"),
    ("ফেবার-কাস্টেল পেন্সিল HB",       "Pens_Pencils"),
    ("মার্কার পেন সেট ১২ রঙ",          "Pens_Pencils"),
    ("হাইলাইটার সেট ৬ রঙ",            "Pens_Pencils"),
    ("Camlin রঙিন পেন্সিল ২৪ রঙ",     "Art_Craft"),
    ("আঁকার খাতা স্কেচপ্যাড A4",      "Art_Craft"),
    ("কারুকাজ গাম স্টিক",              "Art_Craft"),
    ("স্কচ টেপ ১ইঞ্চি",               "Art_Craft"),
    ("A4 পেপার রিম (৫০০ শিট)",         "Paper_Files"),
    ("ফাইল ফোল্ডার",                   "Paper_Files"),
    ("কার্বন পেপার প্যাক",              "Paper_Files"),
    ("স্ট্যাপলার মাঝারি",              "School_Supplies"),
    ("স্কেল ৩০সেমি মেটাল",            "School_Supplies"),
    ("জ্যামিতি বাক্স সেট",             "School_Supplies"),
    ("প্রট্র্যাক্টর ১৮০°",             "School_Supplies"),
    ("ইরেজার নরম সাদা",                "School_Supplies"),
    ("পোস্ট-ইট নোট প্যাড",             "Office_Supplies"),
    ("ডেস্ক অর্গানাইজার",              "Office_Supplies"),
    ("স্ট্যাম্প প্যাড নীল",            "Office_Supplies"),
    ("বাংলা গ্র্যামার ও রচনা (SSC)",  "Books_Publishers"),
    ("ইংরেজি ডিকশনারি বাংলা-ইংরেজি",  "Books_Publishers"),
    ("গণিত গাইড HSC",                  "Books_Publishers"),
    ("বিজ্ঞান বই JSC",                 "Books_Publishers"),
]

STATIONERY_CUSTOMER_TYPES = ["student", "student", "student", "office", "institution"]
STATIONERY_SEASONS = {
    1: "new_year_term", 2: "regular", 3: "regular", 4: "exam_prep",
    5: "exam_prep", 6: "exam_season", 7: "vacation", 8: "vacation",
    9: "new_term", 10: "new_term", 11: "regular", 12: "year_end",
}

def _stationery_fields(cat: str, d: date) -> dict:
    ctype = random.choice(STATIONERY_CUSTOMER_TYPES)
    if cat in ("Books_Publishers", "School_Supplies"):
        ctype = rng.choice(["student", "student", "institution"])
    elif cat == "Office_Supplies":
        ctype = rng.choice(["office", "institution"])
    return {
        "Customer_Type": ctype,
        "Season_Tag":    STATIONERY_SEASONS.get(d.month, "regular"),
        "Paper_Size":    random.choice(["A4", "A4", "A4", "A3", "legal", "custom"])
                         if cat in ("Paper_Files", "Notebooks") else "N/A",
    }


# ── Dataset builder ───────────────────────────────────────────────────────────

def build_dataset(vertical: str) -> pd.DataFrame:
    customers = make_customers(N_CUSTOMERS)

    if vertical == "auto_parts":
        cats     = AUTO_PARTS_CATEGORIES
        products_list = AUTO_PARTS_PRODUCTS
        seasonal_fn   = seasonal_weight_auto
        extra_fn      = lambda cat, d: _auto_parts_fields(cat, d)
    else:  # stationery
        cats     = STATIONERY_CATEGORIES
        products_list = STATIONERY_PRODUCTS
        seasonal_fn   = seasonal_weight_stationery
        extra_fn      = lambda cat, d: _stationery_fields(cat, d)

    # Product table
    prod_rows = []
    for pname, cat in products_list:
        lo, hi, _ = cats[cat]
        prod_rows.append({
            "Product_ID":     f"P{len(prod_rows)+1:04d}",
            "Product_Name":   pname,
            "Category":       cat,
            "Unit_Price_BDT": round(rng.uniform(lo, hi), 2),
        })
    prod_df = pd.DataFrame(prod_rows)

    cat_weight = {c: v[2] for c, v in cats.items()}
    prod_cat_w = prod_df["Category"].map(cat_weight).values
    prod_cat_w = prod_cat_w / prod_cat_w.sum()

    # Generate dates weighted by seasonal function
    all_dates = [START_DATE + timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1)]
    date_weights = np.array([seasonal_fn(d) for d in all_dates], dtype=float)
    date_weights /= date_weights.sum()
    chosen_dates = [all_dates[i] for i in
                    rng.choice(len(all_dates), size=N_TRANSACTIONS, p=date_weights)]

    rows = []
    for i, d in enumerate(chosen_dates):
        cust  = customers.iloc[int(rng.integers(0, N_CUSTOMERS))]
        prod  = prod_df.iloc[rng.choice(len(prod_df), p=prod_cat_w)]
        qty   = int(rng.integers(1, 5))
        price = prod["Unit_Price_BDT"]
        disc_pct = float(rng.choice([0, 0, 0, 0.05, 0.08, 0.10, 0.15]))
        disc_amt = round(price * qty * disc_pct, 2)
        total    = round(price * qty - disc_amt, 2)

        row = {
            "Transaction_ID":      f"TXN{i+1:07d}",
            "Customer_ID":         cust["Customer_ID"],
            "Customer_Name":       cust["Customer_Name"],
            "Phone":               cust["Phone"],
            "City":                cust["City"],
            "Marketing_Consent":   cust["Marketing_Consent"],
            "Product_ID":          prod["Product_ID"],
            "Product_Name":        prod["Product_Name"],
            "Category":            prod["Category"],
            "Quantity":            qty,
            "Unit_Price_BDT":      price,
            "Discount_Amount_BDT": disc_amt,
            "Total_Amount_BDT":    total,
            "Transaction_Date":    d.isoformat(),
            "Month":               d.month,
            "Year":                d.year,
            "Quarter":             (d.month - 1) // 3 + 1,
            "Vertical":            vertical,
            "Dataset_Type":        "declared_synthetic",
        }
        row.update(extra_fn(prod["Category"], d))
        rows.append(row)

    df = pd.DataFrame(rows)

    # CRM tier by spend
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
    print(f"→ Generating {vertical} dataset…")
    df = build_dataset(vertical)
    out = OUT_DIR / vertical
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{vertical}_dataset.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  ✓ {len(df):,} rows, {df['Customer_ID'].nunique()} customers → {path}")
    manifest = [
        f"# {vertical}_dataset.csv manifest",
        f"vertical: {vertical}",
        f"rows: {len(df)}",
        f"customers: {df['Customer_ID'].nunique()}",
        f"products: {df['Product_ID'].nunique()}",
        f"date_range: {df['Transaction_Date'].min()} to {df['Transaction_Date'].max()}",
        "dataset_type: declared_synthetic",
        "real_columns: none (BD price bands, seasonal patterns, product names are realistic)",
    ]
    (out / "MANIFEST.md").write_text("\n".join(manifest), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default="all",
                        choices=["auto_parts", "stationery", "all"])
    args = parser.parse_args()

    targets = ["auto_parts", "stationery"] if args.vertical == "all" else [args.vertical]
    for v in targets:
        generate(v)
    print("Done.")
