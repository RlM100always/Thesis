"""
seed_demo_data.py
Creates 5 demo SME accounts (pharmacy, grocery, clothing, restaurant, electronics)
and seeds each with 1 year of realistic Bangladeshi business data.

Usage:
    .\.venv312\Scripts\python.exe seed_demo_data.py
"""

import utf8_console  # noqa: F401
import random, datetime, json, sys, time
import urllib.request, urllib.error

BASE       = "http://127.0.0.1:8000"
SEED_DAYS  = 365
TODAY      = datetime.date.today()
START_DATE = TODAY - datetime.timedelta(days=SEED_DAYS)

random.seed(42)

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _req(method, path, body=None, token=None, org_id=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:  headers["Authorization"] = f"Bearer {token}"
    if org_id: headers["X-Organization-ID"] = org_id
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        if e.code in (404, 409, 422): return None
        raise RuntimeError(f"{method} {path} → {e.code}: {msg[:300]}")

def get(path, t=None, o=None):        return _req("GET",   path, None, t, o)
def post(path, body, t=None, o=None): return _req("POST",  path, body, t, o)

def jitter(v, pct=0.20):
    return max(1, round(v * (1 + random.uniform(-pct, pct))))

def seasonal(d, profile):
    """Return sales multiplier for the given date and business profile."""
    m = d.month
    base = profile["monthly"][m - 1]
    dow = d.weekday()  # 0=Mon … 6=Sun
    dow_m = profile["dow"][dow]
    return base * dow_m

def date_str(d, hour=10): return d.isoformat() + f"T{hour:02d}:00:00"
def inv_num(prefix, d):   return f"{prefix}-{d.strftime('%Y%m%d')}-{random.randint(1000,9999)}"

# ── Business profiles ─────────────────────────────────────────────────────────

PROFILES = {
    # ── 1. Pharmacy ───────────────────────────────────────────────────────────
    "pharmacy": {
        "email":    "pharma_owner@bsmart.local",
        "password": "Bsmart1234!",
        "name":     "মেডি ফার্মা",
        "slug":     "medi-pharma",
        "sector":   "pharmacy",
        "industry": "pharmacy",
        "monthly":  [1.1, 1.0, 0.9, 1.2, 1.3, 1.3, 1.1, 1.0, 0.9, 1.0, 1.2, 1.3],
        "dow":      [1.0, 1.05, 1.0, 1.05, 0.6, 1.2, 0.9],
        "daily_invoices": 12,
        "methods": ["cash", "bkash", "nagad", "bank"],
        "method_weights": [0.55, 0.25, 0.15, 0.05],
        "products": [
            # (name, brand, unit, cost, sell, cat, reorder, init_stock, expiry_months)
            ("Napa 500mg",       "Beximco",       "strip",  8,  12, "pain_fever",   50, 200, 18),
            ("Napa Extra",       "Beximco",       "strip", 10,  14, "pain_fever",   40, 150, 18),
            ("Ace 500mg",        "Square",        "strip",  8,  11, "pain_fever",   50, 180, 18),
            ("Neofen 400mg",     "Incepta",       "strip",  9,  13, "pain_fever",   40, 120, 18),
            ("Fexo 120mg",       "Renata",        "strip", 18,  25, "allergy",      30, 100, 18),
            ("Histacin",         "Square",        "strip", 10,  15, "allergy",      25,  80, 18),
            ("Seclo 20mg",       "Square",        "strip", 12,  18, "antacid",      35, 120, 18),
            ("Omeprazole 20mg",  "Beximco",       "strip", 10,  15, "antacid",      30, 100, 18),
            ("Azithromycin 500", "Renata",        "strip", 45,  65, "antibiotic",   20,  60, 12),
            ("Amoxicillin 500",  "Square",        "strip", 25,  38, "antibiotic",   25,  70, 12),
            ("Ciprofloxacin 500","Beximco",       "strip", 30,  42, "antibiotic",   20,  60, 12),
            ("Cefixime 200",     "Incepta",       "strip", 55,  75, "antibiotic",   15,  50, 12),
            ("Metformin 500",    "Beximco",       "strip", 12,  18, "diabetes",     40, 120, 18),
            ("Glibenclamide",    "Square",        "strip", 10,  15, "diabetes",     30,  90, 18),
            ("Insulin Novomix",  "Novo Nordisk",  "vial", 450, 580, "diabetes",     10,  20,  6),
            ("Atenolol 50",      "Renata",        "strip",  8,  12, "cardiac",      30, 100, 18),
            ("Amlodipine 5mg",   "Beximco",       "strip", 15,  22, "cardiac",      25,  80, 18),
            ("Losartan 50mg",    "Square",        "strip", 18,  26, "cardiac",      20,  60, 18),
            ("Atorvastatin 20",  "Incepta",       "strip", 22,  32, "cardiac",      20,  60, 18),
            ("Vitamin C 500",    "Beximco",       "strip",  6,   9, "vitamin",      60, 200, 24),
            ("Zinc 20mg",        "Square",        "strip",  8,  12, "vitamin",      50, 160, 24),
            ("Calcium D3",       "Renata",        "strip", 16,  22, "vitamin",      30,  90, 18),
            ("ORS sachet",       "Beximco",       "sachet", 3,   5, "rehydration",  60, 200, 24),
            ("Saline 500ml",     "Square",        "bottle",18,  25, "rehydration",  20,  50, 12),
            ("Dettol 100ml",     "Reckitt",       "bottle",45,  60, "antiseptic",   15,  40, 24),
            ("Betadine 30ml",    "Mundipharma",   "bottle",35,  48, "antiseptic",   15,  40, 24),
            ("Panadol Extra",    "GSK",           "strip", 12,  17, "pain_fever",   30, 100, 18),
            ("Flagyl 400",       "Sanofi",        "strip", 20,  28, "antibiotic",   20,  60, 12),
            ("Cough Syrup",      "Square",        "bottle",40,  55, "respiratory",  12,  35, 12),
            ("Salbutamol 4mg",   "Renata",        "strip", 25,  35, "respiratory",  15,  50, 18),
            ("Diclofenac 50mg",  "Beximco",       "strip", 12,  18, "pain_fever",   25,  80, 18),
            ("Eye Drop 5ml",     "Renata",        "bottle",55,  72, "eye_ear",       8,  25, 12),
            ("Multivitamin",     "Aristopharma",  "strip", 20,  28, "vitamin",      25,  80, 18),
            ("Antacid Syrup",    "Beximco",       "bottle",35,  48, "antacid",      12,  30, 12),
            ("Montelukast 10",   "Incepta",       "strip", 35,  50, "respiratory",  12,  40, 18),
        ],
        "customers": [
            ("আহমেদ হোসেন","01711-111001"),("রহিমা বেগম","01711-111002"),("করিম সাহেব","01711-111003"),
            ("ফাতেমা খানম","01711-111004"),("মোঃ আলী","01711-111005"),("সুমাইয়া আক্তার","01711-111006"),
            ("আবদুল্লাহ","01711-111007"),("নাসরিন বেগম","01711-111008"),("তানভীর আহমেদ","01711-111009"),
            ("শাহানা পারভীন","01711-111010"),("মোতাহার হোসেন","01711-111011"),("রাহেলা খানম","01711-111012"),
        ],
        "suppliers": [
            ("Beximco Pharma","01755-100001","Dhaka",30),
            ("Square Pharma","01755-100002","Dhaka",30),
            ("Renata Ltd","01755-100003","Dhaka",45),
        ],
        "expenses": [("rent","দোকান ভাড়া",15000),("electricity","বিদ্যুৎ",2000),("salary","কর্মচারী বেতন",30000),("misc","বিবিধ",3000)],
    },

    # ── 2. Grocery ───────────────────────────────────────────────────────────
    "grocery": {
        "email":    "grocery_owner@bsmart.local",
        "password": "Bsmart1234!",
        "name":     "আল-আমিন গ্রোসারি",
        "slug":     "al-amin-grocery",
        "sector":   "grocery",
        "industry": "grocery",
        "monthly":  [1.0, 0.9, 1.0, 1.4, 1.5, 1.2, 1.4, 1.0, 1.0, 1.1, 1.0, 1.3],
        "dow":      [1.0, 1.0, 1.0, 1.1, 0.8, 1.3, 1.2],
        "daily_invoices": 20,
        "methods": ["cash", "bkash", "nagad"],
        "method_weights": [0.60, 0.25, 0.15],
        "products": [
            ("মিনিকেট চাল ৫কেজি",     "Pran",    "bag",  230, 280, "rice_grain",  20, 100, 18),
            ("নাজিরশাইল চাল ৫কেজি",   "ACI",     "bag",  320, 380, "rice_grain",  15,  80, 18),
            ("ময়দা ২কেজি",            "Fresh",   "pack",  90, 120, "flour",       25, 100, 12),
            ("আটা ২কেজি",             "ACI",     "pack",  75, 100, "flour",       25, 100, 12),
            ("সয়াবিন তেল ১লিটার",     "Rupchanda","bottle",155, 185, "oil",        30, 120, 12),
            ("সানফ্লাওয়ার তেল ১লি",  "Teer",    "bottle",160, 190, "oil",        25,  80, 12),
            ("চিনি ১কেজি",            "Local",   "packet", 90, 120, "sugar_salt",  30, 150, 18),
            ("লবণ ১কেজি",             "Molla",   "packet", 25,  35, "sugar_salt",  40, 200, 24),
            ("মসুর ডাল ১কেজি",        "Pran",    "packet",110, 140, "pulses",      25, 100, 12),
            ("মুগ ডাল ১কেজি",         "ACI",     "packet",130, 165, "pulses",      20,  80, 12),
            ("হলুদ গুঁড়ো ২০০গ্রাম",  "Radhuni", "packet", 40,  55, "spice",       30, 100, 18),
            ("মরিচ গুঁড়ো ২০০গ্রাম",  "Radhuni", "packet", 55,  70, "spice",       30, 100, 18),
            ("ধনে গুঁড়ো ২০০গ্রাম",   "Radhuni", "packet", 40,  55, "spice",       25,  80, 18),
            ("গরম মসলা ৫০গ্রাম",      "Pran",    "packet", 35,  50, "spice",       20,  60, 18),
            ("Pran লাচ্ছা সেমাই",     "Pran",    "packet", 65,  85, "snacks",      20,  80, 18),
            ("বিস্কুট টিন",           "Olympic", "tin",    95, 120, "snacks",      15,  50, 12),
            ("কেরোসিন ১লিটার",        "BPC",     "bottle", 55,  65, "fuel",        10,  30, 24),
            ("সাবান (Lifebuoy)",       "Unilever","bar",    35,  50, "hygiene",     30, 100, 24),
            ("শ্যাম্পু ৩৪০মিলি",     "Unilever","bottle", 95, 125, "hygiene",     20,  60, 18),
            ("ডিটারজেন্ট ৫০০গ্রাম",  "Wheel",   "packet", 50,  70, "hygiene",     25,  80, 18),
            ("টুথপেস্ট ১৫০গ্রাম",    "Close Up","tube",   80, 105, "hygiene",     20,  60, 18),
            ("দুধ ১ লিটার",           "Aarong",  "packet", 90, 110, "dairy",       20,  60,  7),
            ("ঘি ৫০০গ্রাম",           "Aarong",  "jar",   350, 420, "dairy",       10,  30, 12),
            ("চা পাতা ২৫০গ্রাম",      "Taaza",   "packet", 95, 125, "tea_coffee",  25,  80, 18),
            ("নেসক্যাফে ২০০গ্রাম",    "Nestle",  "jar",   380, 450, "tea_coffee",  10,  30, 18),
        ],
        "customers": [
            ("সালমা বেগম","01712-222001"),("জহির উদ্দিন","01712-222002"),("রুমানা আক্তার","01712-222003"),
            ("কবির হোসেন","01712-222004"),("মর্জিনা বেগম","01712-222005"),("তোফায়েল আহমেদ","01712-222006"),
            ("সাহেলা পারভীন","01712-222007"),("ইউনুস আলী","01712-222008"),("ফরিদা খানম","01712-222009"),
            ("বাবুল হোসেন","01712-222010"),("নাহার বেগম","01712-222011"),("সেলিম রেজা","01712-222012"),
        ],
        "suppliers": [
            ("Pran-RFL Group","01756-200001","Dhaka",15),
            ("ACI Agribusiness","01756-200002","Dhaka",15),
            ("Local Wholesale Market","01756-200003","Dhaka",7),
        ],
        "expenses": [("rent","দোকান ভাড়া",12000),("electricity","বিদ্যুৎ",1800),("salary","কর্মচারী বেতন",25000),("misc","পরিবহন",4000)],
    },

    # ── 3. Clothing ───────────────────────────────────────────────────────────
    "clothing": {
        "email":    "clothing_owner@bsmart.local",
        "password": "Bsmart1234!",
        "name":     "ফ্যাশন হাউস",
        "slug":     "fashion-house-bd",
        "sector":   "clothing",
        "industry": "retail",
        "monthly":  [0.8, 0.7, 0.9, 1.8, 1.6, 0.8, 1.7, 1.5, 0.9, 1.0, 0.9, 1.4],
        "dow":      [0.9, 0.9, 1.0, 1.0, 0.7, 1.4, 1.3],
        "daily_invoices": 8,
        "methods": ["cash", "bkash", "card"],
        "method_weights": [0.50, 0.35, 0.15],
        "products": [
            ("পাঞ্জাবি (S)",           "Aarong",    "pcs",  550, 850, "mens_top",    10,  50, 36),
            ("পাঞ্জাবি (M)",           "Aarong",    "pcs",  550, 850, "mens_top",    10,  50, 36),
            ("পাঞ্জাবি (L)",           "Aarong",    "pcs",  550, 850, "mens_top",    10,  50, 36),
            ("টি-শার্ট কটন (M)",       "Local Brand","pcs", 220, 380, "mens_top",    15,  80, 36),
            ("টি-শার্ট কটন (L)",       "Local Brand","pcs", 220, 380, "mens_top",    15,  80, 36),
            ("শার্ট ফর্মাল (M)",       "Ecstasy",   "pcs",  450, 750, "mens_top",    10,  40, 36),
            ("শার্ট ফর্মাল (L)",       "Ecstasy",   "pcs",  450, 750, "mens_top",    10,  40, 36),
            ("প্যান্ট কটন (32)",       "Yellow",    "pcs",  680,1100, "mens_bottom", 10,  40, 36),
            ("প্যান্ট কটন (34)",       "Yellow",    "pcs",  680,1100, "mens_bottom", 10,  40, 36),
            ("প্যান্ট কটন (36)",       "Yellow",    "pcs",  680,1100, "mens_bottom", 10,  40, 36),
            ("সালোয়ার কামিজ (S)",     "Aarong",    "set",  950,1500, "womens_set",  10,  40, 36),
            ("সালোয়ার কামিজ (M)",     "Aarong",    "set",  950,1500, "womens_set",  10,  40, 36),
            ("সালোয়ার কামিজ (L)",     "Aarong",    "set",  950,1500, "womens_set",  10,  40, 36),
            ("শাড়ি সুতি",             "Tangail",   "pcs", 1200,1800, "saree",        8,  30, 60),
            ("শাড়ি জামদানি",          "Jamdani",   "pcs", 3500,5500, "saree",        5,  20, 60),
            ("কুর্তি ছাপা (M)",        "Deshal",    "pcs",  350, 600, "womens_top",  12,  50, 36),
            ("কুর্তি ছাপা (L)",        "Deshal",    "pcs",  350, 600, "womens_top",  12,  50, 36),
            ("ছেলেদের জিন্স (30)",    "Levi's BD", "pcs", 1200,1900, "mens_bottom", 10,  30, 60),
            ("ছেলেদের জিন্স (32)",    "Levi's BD", "pcs", 1200,1900, "mens_bottom", 10,  30, 60),
            ("হিজাব কটন",             "Pious",     "pcs",  180, 320, "hijab",       20,  80, 60),
            ("হিজাব শিফন",            "Pious",     "pcs",  220, 380, "hijab",       20,  80, 60),
            ("ওড়না",                 "Local",     "pcs",  120, 220, "accessories", 15,  60, 60),
            ("জ্যাকেট হুডি (M)",      "Local Brand","pcs", 650,1100, "outerwear",    8,  30, 60),
            ("মোজা (প্যাক ৩টি)",      "ACI",       "pack",  80, 140, "accessories", 20,  80, 36),
            ("বেল্ট চামড়া",           "Bata",      "pcs",  250, 450, "accessories", 10,  40, 60),
        ],
        "customers": [
            ("রাফিয়া সুলতানা","01713-333001"),("মাহবুব আলম","01713-333002"),("পারভীন আক্তার","01713-333003"),
            ("সাইফুল ইসলাম","01713-333004"),("নিলুফার রহমান","01713-333005"),("আল-আমিন","01713-333006"),
            ("মেহেরুন নেছা","01713-333007"),("রফিকুল ইসলাম","01713-333008"),("শবনম নাহার","01713-333009"),
            ("শামছুল হক","01713-333010"),
        ],
        "suppliers": [
            ("Aarong (BRAC)","01757-300001","Dhaka",30),
            ("Yellow Apparel","01757-300002","Dhaka",30),
            ("Local Garments","01757-300003","Narsingdi",15),
        ],
        "expenses": [("rent","শোরুম ভাড়া",25000),("electricity","বিদ্যুৎ",3500),("salary","কর্মচারী বেতন",40000),("misc","ডিসপ্লে ও মার্কেটিং",5000)],
    },

    # ── 4. Restaurant ────────────────────────────────────────────────────────
    "restaurant": {
        "email":    "restaurant_owner@bsmart.local",
        "password": "Bsmart1234!",
        "name":     "ঢাকাই রান্নাঘর",
        "slug":     "dhakai-rannaghar",
        "sector":   "restaurant",
        "industry": "food_beverage",
        "monthly":  [1.0, 0.9, 1.0, 1.3, 1.4, 1.1, 1.3, 1.1, 1.0, 1.0, 1.1, 1.2],
        "dow":      [0.9, 0.9, 1.0, 1.1, 1.3, 1.4, 1.2],
        "daily_invoices": 30,
        "methods": ["cash", "bkash", "nagad", "card"],
        "method_weights": [0.45, 0.30, 0.15, 0.10],
        "products": [
            ("ভাত + মুরগির কারি",      "Chef",    "plate", 55, 120, "rice_dishes",  30, 100, 1),
            ("ভাত + গরুর মাংস",        "Chef",    "plate", 90, 180, "rice_dishes",  25,  80, 1),
            ("ভাত + মাছ ভাজা",         "Chef",    "plate", 60, 130, "rice_dishes",  30, 100, 1),
            ("ভাত + ডাল + সবজি",       "Chef",    "plate", 35,  80, "rice_dishes",  40, 120, 1),
            ("বিরিয়ানি মুরগি",         "Chef",    "plate",100, 220, "biryani",      20,  60, 1),
            ("বিরিয়ানি গরু",           "Chef",    "plate",130, 280, "biryani",      15,  50, 1),
            ("খিচুড়ি + ডিম",          "Chef",    "plate", 40,  90, "rice_dishes",  25,  80, 1),
            ("রুটি (২টি)",             "Chef",    "serve", 15,  30, "bread",        50, 150, 1),
            ("পরোটা (২টি)",            "Chef",    "serve", 20,  40, "bread",        50, 150, 1),
            ("চিকেন ফ্রাই",            "Chef",    "pcs",   45, 100, "fried",        20,  60, 1),
            ("সিঙ্গারা",               "Chef",    "pcs",   10,  20, "snacks",       60, 200, 1),
            ("সমুচা",                  "Chef",    "pcs",   12,  25, "snacks",       50, 150, 1),
            ("চা",                     "Chef",    "cup",    8,  15, "beverage",     80, 300, 1),
            ("কোকাকোলা ক্যান",         "Coke BD", "can",   35,  60, "beverage",     30, 100, 6),
            ("পেপসি ৫০০মিলি",          "Pepsi BD","bottle",45,  70, "beverage",     25,  80, 6),
            ("মিনারেল ওয়াটার",        "Mum",     "bottle",12,  25, "beverage",     50, 200, 12),
            ("লাচ্ছি",                 "Chef",    "glass", 20,  50, "beverage",     20,  60, 1),
            ("বোরহানি",               "Chef",    "glass", 15,  40, "beverage",     25,  80, 1),
            ("ফালুদা",                 "Chef",    "glass", 30,  70, "dessert",      15,  50, 1),
            ("মিষ্টি দই",             "Grameen", "cup",   25,  55, "dessert",      20,  60, 3),
            ("রসমালাই",               "Chef",    "pcs",   30,  65, "dessert",      15,  50, 1),
            ("মুরগির স্যুপ",           "Chef",    "bowl",  50, 110, "soup",         15,  50, 1),
            ("লেমন ড্রিংক",           "Chef",    "glass", 15,  40, "beverage",     20,  60, 1),
            ("স্পেশাল থালি",           "Chef",    "set",  160, 320, "combos",       10,  30, 1),
            ("ফ্যামিলি প্যাক",         "Chef",    "pack", 350, 700, "combos",        5,  20, 1),
        ],
        "customers": [
            ("অফিস কাস্টমার ১","01714-444001"),("অফিস কাস্টমার ২","01714-444002"),
            ("নিয়মিত খদ্দের","01714-444003"),("ক্যাটারিং ক্লায়েন্ট","01714-444004"),
            ("ডেলিভারি কাস্টমার","01714-444005"),("পার্টি বুকিং","01714-444006"),
        ],
        "suppliers": [
            ("Fresh Agro BD","01758-400001","Dhaka",7),
            ("Meghna Group","01758-400002","Dhaka",15),
            ("Local Bazaar Supplier","01758-400003","Dhaka",3),
        ],
        "expenses": [("rent","রেস্তোরাঁ ভাড়া",35000),("electricity","বিদ্যুৎ+গ্যাস",8000),("salary","কর্মচারী বেতন",55000),("misc","রান্নার কাঁচামাল",20000)],
    },

    # ── 5. Electronics ───────────────────────────────────────────────────────
    "electronics": {
        "email":    "electronics_owner@bsmart.local",
        "password": "Bsmart1234!",
        "name":     "টেকনো শপ",
        "slug":     "techno-shop-bd",
        "sector":   "electronics",
        "industry": "retail",
        "monthly":  [0.9, 0.8, 0.9, 1.1, 1.2, 1.0, 1.1, 1.0, 1.0, 1.2, 1.3, 1.5],
        "dow":      [0.9, 1.0, 1.0, 1.05, 0.8, 1.3, 1.3],
        "daily_invoices": 6,
        "methods": ["cash", "bkash", "card", "bank"],
        "method_weights": [0.35, 0.35, 0.20, 0.10],
        "products": [
            ("Walton স্মার্টফোন এন্ট্রি",  "Walton",  "pcs",  5500,  7500, "smartphone",  5, 20, 24),
            ("Walton স্মার্টফোন মিড",       "Walton",  "pcs", 12000, 16000, "smartphone",  4, 15, 24),
            ("Samsung A05 4G",               "Samsung", "pcs", 13000, 17500, "smartphone",  4, 15, 24),
            ("Xiaomi Redmi 12",              "Xiaomi",  "pcs", 16000, 21000, "smartphone",  3, 10, 24),
            ("ফিচার ফোন Walton",             "Walton",  "pcs",  1200,  1800, "feature_phone",10, 40, 24),
            ("Headphone (Wired)",            "Havit",   "pcs",   450,   750, "accessory",   15, 60, 24),
            ("Bluetooth Headset",            "Havit",   "pcs",  1800,  2800, "accessory",   10, 40, 24),
            ("TWS Earbuds",                  "Baseus",  "pcs",  2500,  3800, "accessory",    8, 30, 24),
            ("চার্জিং ক্যাবল USB-C",        "Baseus",  "pcs",   180,   320, "accessory",   30,120, 24),
            ("চার্জিং ক্যাবল মাইক্রো",     "Baseus",  "pcs",   120,   220, "accessory",   30,120, 24),
            ("পাওয়ার ব্যাংক ১০০০০",       "Baseus",  "pcs",  1800,  2800, "accessory",   10, 40, 24),
            ("মোবাইল কভার (Universal)",     "Local",   "pcs",   120,   250, "accessory",   25,100, 24),
            ("স্ক্রিন প্রটেক্টর",           "Local",   "pcs",    80,   180, "accessory",   30,120, 24),
            ("ল্যাপটপ ব্যাগ ১৫.৬''",       "Havit",   "pcs",  1200,  1900, "laptop_acc",   8, 30, 36),
            ("Walton ল্যাপটপ i3",           "Walton",  "pcs", 40000, 52000, "laptop",       2,  5, 24),
            ("পেনড্রাইভ ৩২GB",              "Transcend","pcs",  450,   750, "storage",     20, 80, 24),
            ("মেমোরি কার্ড ৩২GB",           "Samsung", "pcs",   350,   600, "storage",     20, 80, 24),
            ("স্মার্ট ওয়াচ বেসিক",         "Amazfit", "pcs",  3500,  5200, "wearable",     5, 20, 24),
            ("Walton স্মার্ট TV ৩২''",     "Walton",  "pcs", 22000, 29000, "tv",           2,  5, 36),
            ("বাল্ব LED ৯W",                "Philips", "pcs",   120,   200, "electrical",  20, 80, 36),
            ("বাল্ব LED ১৮W",               "Philips", "pcs",   200,   320, "electrical",  15, 60, 36),
            ("চার্জার ফাস্ট ৬৫W",           "Baseus",  "pcs",  1600,  2500, "accessory",   10, 40, 24),
            ("ডেস্কটপ মাউস",                "Havit",   "pcs",   350,   600, "computer_acc", 10, 40, 24),
            ("কীবোর্ড",                     "Havit",   "pcs",   650,  1100, "computer_acc", 8, 30, 24),
            ("Router WiFi",                  "TP-Link", "pcs",  3500,  5200, "networking",   5, 20, 36),
        ],
        "customers": [
            ("আরিফ টেলিকম","01715-555001"),("রাকিব হোসেন","01715-555002"),("তাহমিনা আক্তার","01715-555003"),
            ("নুরুল ইসলাম","01715-555004"),("ফারজানা বেগম","01715-555005"),("মনির হোসেন","01715-555006"),
            ("অফিস ক্লায়েন্ট","01715-555007"),("স্কুল সাপ্লাই","01715-555008"),
        ],
        "suppliers": [
            ("Walton Hi-Tech","01759-500001","Gazipur",30),
            ("Star Tech","01759-500002","Dhaka",15),
            ("Ryans Computers","01759-500003","Dhaka",15),
        ],
        "expenses": [("rent","শোরুম ভাড়া",30000),("electricity","বিদ্যুৎ",3000),("salary","কর্মচারী বেতন",45000),("misc","বিজ্ঞাপন",5000)],
    },
}

# ── Core seeder function ──────────────────────────────────────────────────────

def register_or_login(profile):
    # Try register
    r = post("/api/app/auth/register", {
        "email": profile["email"], "password": profile["password"],
        "full_name": profile["name"], "display_name": profile["name"],
    })
    if r and "access_token" in r:
        print(f"  ✓ Registered {profile['email']}")
        return r["access_token"]
    # Already exists — login
    r = post("/api/app/auth/login", {"email": profile["email"], "password": profile["password"]})
    if r and "access_token" in r:
        print(f"  ✓ Logged in {profile['email']}")
        return r["access_token"]
    raise RuntimeError(f"Cannot auth {profile['email']}: {r}")


def seed_business(profile):
    print(f"\n{'='*60}")
    print(f"  {profile['name'].upper()} ({profile['sector']})")
    print(f"{'='*60}")

    token = register_or_login(profile)

    # Get or create org
    orgs = get("/api/app/organizations", token) or []
    org = next((o for o in orgs if o.get("sector") == profile["sector"]), None)
    if not org:
        # Try slug, fall back to slug-2, slug-3 on conflict
        for suffix in ["", "-2", "-3", "-4"]:
            org = post("/api/app/organizations", {
                "name": profile["name"], "slug": profile["slug"] + suffix,
                "sector": profile["sector"], "industry": profile.get("industry","retail"),
                "payment_methods": profile["methods"],
            }, token)
            if org:
                break
    if not org:
        print("  ✗ Could not create org — trying first available")
        org = orgs[0] if orgs else None
    if not org:
        print("  ✗ Skipping — no org")
        return

    org_id = org["id"]
    print(f"  Org: {org.get('name')} ({org_id})")

    # Branch
    branches = get("/api/app/branches", token, org_id) or []
    if not branches:
        b = post("/api/app/branches", {"name": "মূল শাখা", "code": "MAIN", "address": "ঢাকা"}, token, org_id)
        branch_id = b["id"] if b and "id" in b else None
    else:
        branch_id = branches[0]["id"]
    if not branch_id:
        print("  ✗ No branch — skipping")
        return
    print(f"  Branch: {branch_id[:8]}…")

    # Customers
    existing_customers = get("/api/app/customers", token, org_id) or []
    existing_phones = {c.get("phone") for c in existing_customers}
    customer_ids = [c["id"] for c in existing_customers]
    for ci, (cname, phone) in enumerate(profile["customers"]):
        clean_phone = phone.replace("-", "")
        if clean_phone not in existing_phones:
            c = post("/api/app/customers", {
                "name": cname, "code": f"C{ci+1:04d}",
                "phone": clean_phone,
                "credit_limit": random.choice([0, 500, 1000, 2000, 5000]),
            }, token, org_id)
            if c and "id" in c:
                customer_ids.append(c["id"])
                existing_phones.add(clean_phone)
    print(f"  Customers: {len(customer_ids)}")

    # Suppliers
    existing_suppliers = get("/api/app/suppliers", token, org_id) or []
    existing_sup_names = {s.get("name") for s in existing_suppliers}
    supplier_ids = [s["id"] for s in existing_suppliers]
    for si, (sname, phone, address, credit_days) in enumerate(profile["suppliers"]):
        clean_phone = phone.replace("-", "")
        if sname not in existing_sup_names:
            s = post("/api/app/suppliers", {
                "name": sname, "code": f"S{si+1:04d}",
                "phone": clean_phone, "address": address, "credit_days": credit_days,
            }, token, org_id)
            if s and "id" in s:
                supplier_ids.append(s["id"])
    print(f"  Suppliers: {len(supplier_ids)}")

    # Products
    existing_products = get("/api/app/products", token, org_id) or []
    product_map = {p["name"]: p for p in existing_products}
    for prod_data in profile["products"]:
        name, brand, unit, cost, sell, cat, reorder, _, _ = prod_data
        if name in product_map: continue
        sku = f"{cat[:3].upper()}-{name[:3].upper()}-{random.randint(100,999)}"
        track_expiry = profile["sector"] in ("pharmacy", "grocery", "restaurant")
        p = post("/api/app/products", {
            "name": name, "sku": sku.replace(" ",""), "unit": unit,
            "cost_price": str(cost), "selling_price": str(sell),
            "category": cat, "reorder_level": reorder,
            "track_expiry": track_expiry,
        }, token, org_id)
        if p and "id" in p:
            product_map[name] = p

    all_products = get("/api/app/products", token, org_id) or []
    product_map = {p["name"]: p for p in all_products}
    print(f"  Products: {len(product_map)}")

    # Purchase orders (stock loading)
    existing_purchases = get("/api/app/purchases", token, org_id) or []
    if not supplier_ids:
        print("  ✗ No suppliers — cannot create purchases")
    elif len(existing_purchases) < 2:
        restock_dates = [START_DATE + datetime.timedelta(days=d) for d in [0, 90, 180, 270]]
        for ri, restock_date in enumerate(restock_dates):
            sup_id = supplier_ids[ri % len(supplier_ids)]
            items = []
            for prod_data in profile["products"]:
                name, brand, unit, cost, sell, cat, reorder, init_stock, exp_months = prod_data
                if name not in product_map: continue
                prod = product_map[name]
                qty = jitter(init_stock if ri == 0 else init_stock // 2, 0.25)
                exp_date = (restock_date + datetime.timedelta(days=30 * exp_months)).isoformat()
                items.append({
                    "product_id": prod["id"],
                    "quantity": qty,
                    "unit_cost": str(cost),
                    "expiry_date": exp_date,
                    "batch_no": f"B{restock_date.strftime('%y%m')}{random.randint(1000,9999)}",
                })
            if not items: continue
            po = post("/api/app/purchases", {
                "supplier_id": sup_id,
                "order_number": inv_num("PO", restock_date),
                "branch_id": branch_id,
                "ordered_at": date_str(restock_date),
                "items": items,
            }, token, org_id)
            if po and "id" in po:
                total_cost = sum(i["quantity"] * float(i["unit_cost"]) for i in items)
                # Use item IDs from the created PO
                po_detail = get(f"/api/app/purchases", token, org_id)
                po_full = next((p for p in (po_detail or []) if p["id"] == po["id"]), None)
                if po_full and po_full.get("items"):
                    item_id_map = {it["product_id"]: it["id"] for it in po_full["items"]}
                    receive_items = []
                    for i in items:
                        po_item_id = item_id_map.get(i["product_id"])
                        if po_item_id:
                            receive_items.append({
                                "purchase_order_item_id": po_item_id,
                                "product_id": i["product_id"],
                                "quantity": i["quantity"],
                                "batch_no": i["batch_no"],
                                "expiry_date": i["expiry_date"],
                            })
                    if receive_items:
                        post(f"/api/app/purchases/{po['id']}/receive", {
                            "received_at": date_str(restock_date),
                            "items": receive_items,
                            "payment_amount": str(round(total_cost * 0.6)),
                            "payment_method": "bank",
                        }, token, org_id)
        print(f"  Stock loaded (4 restocks over 1 year)")

    # Sales
    existing_sales = get("/api/app/sales", token, org_id) or []
    if len(existing_sales) > 20:
        print(f"  Sales: {len(existing_sales)} already exist, skipping")
    else:
        prods = []
        for pd in profile["products"]:
            name = pd[0]
            if name in product_map:
                prods.append({"id": product_map[name]["id"], "price": pd[4], "sell_freq": pd[6]})
        if not prods:
            print("  No products to sell — skipping sales")
        else:
            weights = [p["sell_freq"] for p in prods]
            ws = sum(weights)
            nw = [w / ws for w in weights]

            total_invoices = 0
            current = START_DATE
            while current <= TODAY:
                smul = seasonal(current, profile)
                base_daily = profile["daily_invoices"]
                n_sales = max(1, round(random.gauss(base_daily * smul, base_daily * 0.2)))

                for _ in range(n_sales):
                    n_items = random.choices([1, 2, 3, 4], weights=[0.50, 0.28, 0.14, 0.08])[0]
                    chosen = random.choices(range(len(prods)), weights=nw, k=n_items)
                    seen = set(); lines = []
                    for idx in chosen:
                        prod = prods[idx]
                        if prod["id"] in seen: continue
                        seen.add(prod["id"])
                        qty = random.choices([1, 2, 3, 5], weights=[0.55, 0.25, 0.12, 0.08])[0]
                        price_mult = random.choices([1.0, 1.0, 1.0, 0.95], weights=[0.7, 0.1, 0.1, 0.1])[0]
                        price = round(prod["price"] * price_mult, 2)
                        lines.append({"product_id": prod["id"], "quantity": qty,
                                      "unit_price": str(price), "discount_amount": "0"})

                    cust = random.choices(
                        [None] + customer_ids,
                        weights=[0.40] + [0.60 / max(1, len(customer_ids))] * len(customer_ids)
                    )[0]
                    method = random.choices(profile["methods"], weights=profile["method_weights"])[0]
                    total_amt = sum(int(l["quantity"]) * float(l["unit_price"]) for l in lines)
                    hour = random.randint(9, 21)
                    sale_time = current.isoformat() + f"T{hour:02d}:{random.randint(0,59):02d}:00"

                    r = post("/api/app/sales", {
                        "invoice_number": inv_num("INV", current),
                        "sold_at": sale_time,
                        "branch_id": branch_id,
                        "customer_id": cust,
                        "items": lines,
                        "payments": [{"method": method, "amount": str(round(total_amt, 2))}],
                    }, token, org_id)
                    if r and "id" in r:
                        total_invoices += 1

                if current.day == 1:
                    sys.stdout.write(f"\r  Sales: {current.strftime('%Y-%m')} — {total_invoices} invoices…   ")
                    sys.stdout.flush()
                current += datetime.timedelta(days=1)

            print(f"\n  Sales: {total_invoices} invoices ✓")

    # Expenses
    existing_expenses = get("/api/app/expenses", token, org_id) or []
    if len(existing_expenses) < 10:
        for m in range(12):
            exp_date = START_DATE + datetime.timedelta(days=30 * m + 1)
            if exp_date > TODAY: break
            for cat, desc, amt in profile["expenses"]:
                post("/api/app/expenses", {
                    "category": cat, "description": desc,
                    "amount": str(jitter(amt, 0.12)),
                    "incurred_at": exp_date.isoformat() + "T09:00:00",
                    "payment_method": "bank",
                }, token, org_id)
        print(f"  Expenses: 12 months seeded")

    print(f"  ✅ {profile['name']} done!")


def main():
    print("B-SMART Demo Data Seeder")
    print(f"Seeding {SEED_DAYS} days of data ({START_DATE} → {TODAY})")
    print(f"Creating {len(PROFILES)} business accounts...\n")

    for sector, profile in PROFILES.items():
        try:
            seed_business(profile)
        except Exception as e:
            print(f"  ✗ Error seeding {sector}: {e}")
            continue

    print(f"\n{'='*60}")
    print("✅ All 5 demo businesses seeded!")
    print("\nLogin credentials:")
    for p in PROFILES.values():
        print(f"  {p['name']:20s}  {p['email']:35s}  {p['password']}")
    print(f"\nOpen http://localhost:5173 to explore.")

if __name__ == "__main__":
    main()
