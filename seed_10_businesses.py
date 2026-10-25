"""
seed_10_businesses.py
=====================
Creates 10 realistic Bangladeshi SME demo businesses with:
  - Proper accounts (email/password)
  - Sector-specific products (real BD market prices & SKUs)
  - 12 months of realistic sales data (Oct 2025 – Oct 2026)
  - Bangladesh seasonal demand patterns (Eid, winter, monsoon)
  - Enough data for ML model training (forecast + churn)

Run AFTER cleanup_duplicates.py has cleared all old orgs.
"""
import utf8_console  # noqa: F401
import sys, random, uuid, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, ".")

import requests
from sqlalchemy import text
from api.database import SessionLocal

BASE   = os.getenv("BSMART_DEMO_API_URL", "http://127.0.0.1:8000")
TODAY  = datetime(2026, 10, 3)
START  = datetime(2025, 10, 1)
RNG    = random.Random(42)

# This is a DESTRUCTIVE-volume DEMONSTRATION seed; never auto-run on a live shop.
if os.getenv("BSMART_ALLOW_SYNTHETIC_SEED") != "YES":
    raise SystemExit("Synthetic demo seeding is disabled. Set BSMART_ALLOW_SYNTHETIC_SEED=YES explicitly in a LOCAL, EMPTY development database.")
if not BASE.startswith(("http://127.0.0.1:", "http://localhost:")):
    raise SystemExit("Refusing to seed remote/business-facing API URLs.")
if (os.getenv("DATABASE_URL", "").startswith(("postgresql", "postgres:"))
        or os.getenv("RENDER", "").lower() == "true"):
    raise SystemExit("Refusing to seed a remote/Render/PostgreSQL environment.")
DEMO_PASSWORD = os.getenv("BSMART_DEMO_PASSWORD", "")
if len(DEMO_PASSWORD) < 14 or DEMO_PASSWORD in {"Bsmart1234!", "password12345678"}:
    raise SystemExit("Set a unique BSMART_DEMO_PASSWORD (14+ characters); never use public sample credentials.")


# ─────────────────────────────────────────────────────────────────────────────
# 10 Businesses — diverse sectors, real Bangladeshi SMEs
# ─────────────────────────────────────────────────────────────────────────────
BUSINESSES = [
    {
        "email": "pharma_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "আল-হেলাল ফার্মেসি",
        "org_name": "আল-হেলাল ফার্মেসি",
        "sector": "pharmacy",
        "address": "মিরপুর-১০, ঢাকা",
        "daily_orders": (12, 30),   # typical BD pharmacy footfall
    },
    {
        "email": "grocery_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "মা-মণি জেনারেল স্টোর",
        "org_name": "মা-মণি জেনারেল স্টোর",
        "sector": "grocery",
        "address": "আগ্রাবাদ, চট্টগ্রাম",
        "daily_orders": (18, 45),
    },
    {
        "email": "clothing_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "নিউ লুক ফ্যাশন",
        "org_name": "নিউ লুক ফ্যাশন",
        "sector": "clothing",
        "address": "বসুন্ধরা সিটি, ঢাকা",
        "daily_orders": (6, 20),
    },
    {
        "email": "restaurant_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "স্বাদের রান্নাঘর",
        "org_name": "স্বাদের রান্নাঘর",
        "sector": "restaurant",
        "address": "জিন্দাবাজার, সিলেট",
        "daily_orders": (30, 80),
    },
    {
        "email": "electronics_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "ডিজিটাল জোন",
        "org_name": "ডিজিটাল জোন",
        "sector": "electronics",
        "address": "এলিফ্যান্ট রোড, ঢাকা",
        "daily_orders": (8, 22),
    },
    {
        "email": "hardware_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "বিল্ডার্স হার্ডওয়্যার",
        "org_name": "বিল্ডার্স হার্ডওয়্যার",
        "sector": "hardware",
        "address": "চাষাঢ়া, নারায়ণগঞ্জ",
        "daily_orders": (10, 25),
    },
    {
        "email": "beauty_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "গ্লামার বিউটি শপ",
        "org_name": "গ্লামার বিউটি শপ",
        "sector": "beauty",
        "address": "গুলশান-১, ঢাকা",
        "daily_orders": (10, 28),
    },
    {
        "email": "stationery_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "জ্ঞান ভাণ্ডার স্টেশনারি",
        "org_name": "জ্ঞান ভাণ্ডার স্টেশনারি",
        "sector": "stationery",
        "address": "সাহেব বাজার, রাজশাহী",
        "daily_orders": (15, 35),
    },
    {
        "email": "mobile_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "স্মার্ট মোবাইল সেন্টার",
        "org_name": "স্মার্ট মোবাইল সেন্টার",
        "sector": "mobile",
        "address": "কান্দিরপাড়, কুমিল্লা",
        "daily_orders": (10, 25),
    },
    {
        "email": "furniture_owner@bsmart.local",
        "password": DEMO_PASSWORD,
        "display_name": "আরামদায়ক ফার্নিচার",
        "org_name": "আরামদায়ক ফার্নিচার",
        "sector": "furniture",
        "address": "হাতিরপুল, ঢাকা",
        "daily_orders": (3, 10),
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Products per sector — real BD market prices (BDT), 2026 rates
# (sku, name, category, selling_price, cost_price)
# ─────────────────────────────────────────────────────────────────────────────
PRODUCTS = {
    "pharmacy": [
        ("PARA-500",   "নাপা ৫০০মিগ্রা (১০ট্যাব)",        "ব্যথানাশক",    12,   9),
        ("PARA-EXTRA", "নাপা এক্সট্রা (১০ট্যাব)",          "ব্যথানাশক",    20,  16),
        ("AMOX-500",   "এমোক্সিসিলিন ৫০০মিগ্রা",          "অ্যান্টিবায়োটিক",55,  44),
        ("AZI-500",    "অ্যাজিথ্রোমাইসিন ৫০০মিগ্রা",      "অ্যান্টিবায়োটিক",65,  52),
        ("ORS-PKT",    "ওআরএস স্যাশে (২০পিস)",             "ওআরএস",         45,  36),
        ("OMEP-20",    "ওমেপ্রাজল ২০মিগ্রা",               "গ্যাস্ট্রিক",   35,  28),
        ("METRO-400",  "মেট্রোনিডাজল ৪০০মিগ্রা",           "অ্যান্টিবায়োটিক",30,  24),
        ("CETIRIZ-10", "সেটিরিজিন ১০মিগ্রা",               "অ্যালার্জি",    22,  17),
        ("DICLOF-50",  "ডাইক্লোফেনাক ৫০মিগ্রা",           "ব্যথানাশক",    25,  20),
        ("CALCIUM-D",  "ক্যালসিয়াম+ভিটামিন-ডি",           "সাপ্লিমেন্ট",  85,  68),
        ("VIT-C-500",  "ভিটামিন সি ৫০০মিগ্রা",             "সাপ্লিমেন্ট",  35,  28),
        ("ZINC-SULF",  "জিঙ্ক সালফেট ট্যাবলেট",            "সাপ্লিমেন্ট",  40,  32),
        ("ANTAC-SYP",  "গ্যাস্ট্রিক সিরাপ ১৭০মিলি",        "গ্যাস্ট্রিক",  95,  76),
        ("INSULIN-PEN","ইনসুলিন (হিউমুলিন)",               "ডায়াবেটিস",   350, 280),
        ("GLUCO-STRIP","গ্লুকোমিটার স্ট্রিপ (৫০পিস)",      "ডায়াবেটিস",   380, 304),
        ("BANDAGE-2",  "ব্যান্ডেজ ২ইঞ্চি",                 "ড্রেসিং",       25,  20),
        ("COTTON-100", "তুলা ১০০গ্রাম",                    "ড্রেসিং",       40,  32),
        ("SALINE-NS",  "নরমাল স্যালাইন ৫০০মিলি",           "আইভি",          70,  56),
        ("COUGH-SYP",  "কফ সিরাপ ১০০মিলি",                 "কাশি",          75,  60),
        ("FEVER-PATCH","জ্বর কমানোর প্যাচ",                 "জ্বর",          45,  36),
    ],
    "grocery": [
        ("RICE-MIN-5",  "মিনিকেট চাল ৫কেজি",               "চাল",          340, 280),
        ("RICE-BASM-1", "বাসমতী চাল ১কেজি",                 "চাল",          130, 107),
        ("LENTIL-MAS",  "মসুর ডাল ১কেজি",                  "ডাল",          135, 111),
        ("LENTIL-MUG",  "মুগ ডাল ৫০০গ্রাম",                "ডাল",           75,  62),
        ("OIL-SOY-2L",  "সয়াবিন তেল ২লিটার",              "তেল",          340, 280),
        ("OIL-MUST-1",  "সরিষার তেল ১লিটার",               "তেল",          220, 181),
        ("SUGAR-1KG",   "চিনি ১কেজি",                      "চিনি",          75,  62),
        ("SALT-1KG",    "আয়োডিনযুক্ত লবণ ১কেজি",           "লবণ",           28,  23),
        ("FLOUR-ATT-2", "আটা ২কেজি",                       "আটা",           95,  78),
        ("SEMOLINA-1",  "সুজি ১কেজি",                      "সুজি",          65,  54),
        ("TEA-ISPAH",   "ইস্পাহানি চা ২০০গ্রাম",           "চা",           195, 160),
        ("MILK-TET-1",  "তেত্রাপ্যাক দুধ ১লিটার",          "দুধ",           80,  66),
        ("EGG-HAL-12",  "দেশি ডিম ১২পিস",                  "ডিম",          165, 136),
        ("SOAP-LUX",    "লাক্স সাবান ১০০গ্রাম",            "সাবান",         45,  37),
        ("TOOTHP-CLOSE","ক্লোজআপ পেস্ট ১৫০গ্রাম",          "টুথপেস্ট",     120,  99),
        ("SHAMPOO-HC",  "হেড শোল্ডার শ্যাম্পু ১৮০মিলি",    "শ্যাম্পু",     225, 185),
        ("BISCUIT-TUC", "TUC বিস্কিট",                     "স্ন্যাকস",      45,  37),
        ("NOODLES-MAC", "ম্যাগি নুডলস ৫পিস",               "নুডলস",         75,  62),
        ("VINEGAR-1L",  "সিরকা ১লিটার",                    "মশলা",          55,  45),
        ("SPICE-TUR",   "হলুদ গুঁড়া ২০০গ্রাম",             "মশলা",          55,  45),
    ],
    "clothing": [
        ("SHIRT-F-M",   "পুরুষ ফর্মাল শার্ট (M)",           "শার্ট",        750, 563),
        ("SHIRT-F-L",   "পুরুষ ফর্মাল শার্ট (L)",           "শার্ট",        750, 563),
        ("PANT-J-32",   "জিন্স প্যান্ট ৩২ইঞ্চি",            "প্যান্ট",     1350,1013),
        ("PANT-J-34",   "জিন্স প্যান্ট ৩৪ইঞ্চি",            "প্যান্ট",     1350,1013),
        ("TSHIRT-M",    "টি-শার্ট (M)",                     "টি-শার্ট",     490, 368),
        ("TSHIRT-L",    "টি-শার্ট (L)",                     "টি-শার্ট",     490, 368),
        ("SAREE-COT",   "সুতি শাড়ি",                       "শাড়ি",       1950,1463),
        ("SAREE-SLK",   "সিল্ক শাড়ি",                      "শাড়ি",       4500,3375),
        ("KAMEEZ-L",    "মহিলা কামিজ সেট (L)",              "কামিজ",        950, 713),
        ("KAMEEZ-XL",   "মহিলা কামিজ সেট (XL)",             "কামিজ",        950, 713),
        ("PAJAMA-M",    "পাজামা (M)",                        "নিচের পোশাক",  380, 285),
        ("KURTA-M",     "পাঞ্জাবি (M)",                     "পাঞ্জাবি",    1100, 825),
        ("KURTA-L",     "পাঞ্জাবি (L)",                     "পাঞ্জাবি",    1100, 825),
        ("SCARF-COT",   "সুতি ওড়না",                       "আনুষঙ্গিক",   280, 210),
        ("INNERWEAR-M", "গেঞ্জি সেট (M)",                   "আন্ডারওয়্যার", 380, 285),
        ("SOCK-3PK",    "মোজা ৩ জোড়া",                     "আনুষঙ্গিক",   195, 146),
        ("BELT-BLK",    "চামড়ার বেল্ট",                    "আনুষঙ্গিক",   420, 315),
        ("BLAZER-M",    "ব্লেজার (M)",                      "আনুষ্ঠানিক", 3800,2850),
        ("KIDS-SHIRT",  "বাচ্চাদের শার্ট (৬-৮বছর)",        "শিশু পোশাক",  450, 338),
        ("KIDS-PANT",   "বাচ্চাদের প্যান্ট (৬-৮বছর)",      "শিশু পোশাক",  520, 390),
    ],
    "restaurant": [
        ("RICE-PLATE",  "ভাত (বড় প্লেট)",                  "প্রধান",        70,  22),
        ("BEEF-CURRY",  "গরুর মাংস ভুনা",                  "মাংস",         200,  78),
        ("MUTTON-CURRY","খাসির মাংস ভুনা",                  "মাংস",         260, 104),
        ("CHICKEN-ROAST","চিকেন রোস্ট (হাফ)",              "মুরগি",         200,  75),
        ("CHICKEN-CURRY","মুরগির তরকারি",                   "মুরগি",         160,  58),
        ("FISH-HILSHA", "ইলিশ মাছের ঝোল",                  "মাছ",          350, 140),
        ("FISH-ROHU",   "রুই মাছের কারি",                   "মাছ",          180,  68),
        ("DAL-MASOOR",  "মসুর ডালের তরকারি",                "ডাল",           60,  18),
        ("BIRYANI-BEEF","গরুর বিরিয়ানি (প্লেট)",           "বিরিয়ানি",    250,  95),
        ("BIRYANI-CHICK","মুরগির বিরিয়ানি (প্লেট)",        "বিরিয়ানি",    200,  72),
        ("KHICHURI",    "খিচুড়ি (প্লেট)",                   "প্রধান",        80,  25),
        ("PARATHA-2PC", "পরোটা ২পিস",                       "রুটি",          40,  12),
        ("ROTI-4PC",    "রুটি ৪পিস",                        "রুটি",          40,  11),
        ("HALIM-BOWL",  "হালিম (বাটি)",                     "স্পেশাল",      160,  58),
        ("LASSI-GL",    "লাচ্ছি (গ্লাস)",                   "পানীয়",        60,  18),
        ("SHERBET",     "শরবত (গ্লাস)",                     "পানীয়",        40,  10),
        ("TEA-CUP",     "চা (কাপ)",                         "পানীয়",        20,   5),
        ("WATER-500",   "পানীয় জল (৫০০মিলি)",              "পানীয়",        25,   8),
        ("MISHTI-DOI",  "মিষ্টি দই (বাটি)",                 "মিষ্টি",        90,  32),
        ("FIRNI",       "ফিরনি (বাটি)",                     "মিষ্টি",        70,  24),
    ],
    "electronics": [
        ("EARPHONE-WL", "JBL ওয়্যারলেস ইয়ারফোন",           "অডিও",        1850,1388),
        ("EARPHONE-WD", "ওয়্যারড ইয়ারফোন",                 "অডিও",         450, 338),
        ("SPEAKER-BT",  "ব্লুটুথ স্পিকার পোর্টেবল",         "অডিও",        1600,1200),
        ("POWERBANK-20","পাওয়ার ব্যাংক ২০০০০mAh",          "পাওয়ার",     2200,1650),
        ("POWERBANK-10","পাওয়ার ব্যাংক ১০০০০mAh",          "পাওয়ার",     1300, 975),
        ("CHARGER-65W", "৬৫W GaN চার্জার",                   "চার্জার",     1200, 900),
        ("CHARGER-20W", "২০W ফাস্ট চার্জার",                 "চার্জার",      650, 488),
        ("USB-C-CABLE", "USB-C কেবল ১.৫মি (ফাস্ট চার্জ)",   "কেবল",         220, 165),
        ("HDMI-CABLE",  "HDMI কেবল ১.৮মি",                  "কেবল",         350, 263),
        ("MEMORY-128",  "১২৮GB মেমোরি কার্ড (Class 10)",     "স্টোরেজ",     1100, 825),
        ("PEN-DRIVE-32","৩২GB পেনড্রাইভ",                   "স্টোরেজ",      450, 338),
        ("PHONE-COVER", "ফোন ব্যাক কভার",                   "আনুষঙ্গিক",   280, 210),
        ("SCREEN-GUARD","টেম্পার্ড গ্লাস স্ক্রিন প্রোটেক্টর","আনুষঙ্গিক",  150, 113),
        ("SELFIE-STICK","সেলফি স্টিক + ট্রাইপড",            "আনুষঙ্গিক",   650, 488),
        ("KEYBOARD-WL", "ওয়্যারলেস কীবোর্ড+মাউস সেট",      "কম্পিউটার",  1950,1463),
        ("MOUSE-OPT",   "অপটিক্যাল মাউস (USB)",              "কম্পিউটার",   450, 338),
        ("LED-BULB-9W", "LED বাল্ব ৯W",                     "আলো",          130,  98),
        ("FAN-TABLE",   "USB টেবিল ফ্যান",                   "গ্যাজেট",      420, 315),
        ("WEBCAM-HD",   "HD ওয়েবক্যাম ১০৮০p",               "কম্পিউটার",  1200, 900),
        ("ROUTER-WIFI", "ওয়াই-ফাই রাউটার (TP-Link)",        "নেটওয়ার্ক",  1800,1350),
    ],
    "hardware": [
        ("CEMENT-BAG",  "সিমেন্ট (৫০কেজি ব্যাগ)",           "নির্মাণ",      550, 462),
        ("ROD-10MM",    "রড ১০মিমি (পিস)",                   "লোহা",         350, 294),
        ("PAINT-INT-4", "ইন্টেরিয়র পেইন্ট ৪লিটার",          "পেইন্ট",      1200,1008),
        ("PAINT-EXT-4", "এক্সটেরিয়র পেইন্ট ৪লিটার",         "পেইন্ট",      1400,1176),
        ("SAND-PAPER",  "স্যান্ডপেপার (১০পিস)",              "টুলস",          80,  67),
        ("SCREW-BOX",   "স্ক্রু সেট (১০০পিস মিক্স)",         "হার্ডওয়্যার",  120, 101),
        ("NAIL-1KG",    "পেরেক ১কেজি মিক্স",                 "হার্ডওয়্যার",   90,  76),
        ("WIRE-ELEC",   "বৈদ্যুতিক তার ১০মি রোল",           "বৈদ্যুতিক",    380, 319),
        ("SWITCH-2G",   "বৈদ্যুতিক সুইচ সকেট ২গ্যাং",       "বৈদ্যুতিক",    250, 210),
        ("PVC-PIPE-1",  "PVC পাইপ ১ইঞ্চি (মিটার)",          "পাইপ",          90,  76),
        ("HAMMER-CLAW", "ক্লো হ্যামার",                     "টুলস",          380, 319),
        ("DRILL-BIT",   "ড্রিল বিট সেট (১০পিস)",            "টুলস",          450, 378),
        ("TAPE-DUCT",   "ডাক্ট টেপ ৫০মিমি",                 "আনুষঙ্গিক",    120, 101),
        ("PUTTY-1KG",   "পুটি ১কেজি",                       "পেইন্টিং",     180, 151),
        ("BRUSH-PAINT", "পেইন্ট ব্রাশ সেট",                 "পেইন্টিং",     350, 294),
        ("LOCK-DOOR",   "দরজার তালা (সিকিউরিটি)",            "লক",           450, 378),
        ("HINGE-3IN",   "হিঞ্জ ৩ইঞ্চি (জোড়া)",              "হার্ডওয়্যার",   80,  67),
        ("TILE-ADH-5",  "টাইলস অ্যাডহেসিভ ৫কেজি",           "নির্মাণ",      480, 403),
        ("GROUT-2KG",   "গ্রাউট ২কেজি",                     "নির্মাণ",      320, 269),
        ("GAS-CYLINDER","এলপিজি সিলিন্ডার (খালি ফেরত)",     "গ্যাস",       1200,1008),
    ],
    "beauty": [
        ("CREAM-FAIR",  "ফেয়ার অ্যান্ড লাভলি ক্রিম ৫০গ্রা", "ক্রিম",        180, 148),
        ("CREAM-PONDS", "পন্ডস কোল্ড ক্রিম ১৫০মিলি",         "ক্রিম",        320, 263),
        ("SUNSCREEN-50","সানস্ক্রিন SPF৫০ ৫০মিলি",            "ত্বক",         650, 535),
        ("SERUM-VIT-C", "ভিটামিন সি সেরাম ৩০মিলি",            "সেরাম",        950, 780),
        ("FACEWASH-GL", "গার্নিয়ার ফেসওয়াশ ১৫০মিলি",        "ফেসওয়াশ",     280, 230),
        ("LIPSTICK-RED","লিপস্টিক (৫ রঙের কালেকশন)",          "মেকআপ",        450, 370),
        ("FOUNDATION",  "লিকুইড ফাউন্ডেশন",                  "মেকআপ",        850, 698),
        ("MASCARA",     "ম্যাসকারা ওয়াটারপ্রুফ",             "মেকআপ",        650, 534),
        ("EYELINER",    "আই লাইনার পেন",                      "মেকআপ",        280, 230),
        ("NAIL-POLISH", "নেইল পলিশ ১০রঙ সেট",                "নেইল",         350, 288),
        ("HAIR-OIL-PAR","প্যারাসুট নারিকেল তেল ৩০০মিলি",     "চুলের যত্ন",   220, 181),
        ("HAIR-SERUM",  "হেয়ার সেরাম অ্যান্টি-ফ্রিজ",       "চুলের যত্ন",   550, 452),
        ("SHAMPOO-DOVE","ডাভ শ্যাম্পু ৩৪০মিলি",              "শ্যাম্পু",     450, 370),
        ("CONDITIONER", "হেয়ার কন্ডিশনার ৩০০মিলি",           "চুলের যত্ন",   420, 345),
        ("BODY-LOTION", "বডি লোশন ৪০০মিলি",                  "বডি কেয়ার",   380, 312),
        ("DEODORANT",   "রেক্সোনা ডিওডরেন্ট ১৫০মিলি",        "বডি কেয়ার",   280, 230),
        ("PERFUME-SMK", "স্মার্ট কালেকশন পারফিউম ৩০মিলি",    "পারফিউম",      350, 288),
        ("KAJAL",       "কাজল পেন্সিল",                       "মেকআপ",        120,  99),
        ("FACE-MASK",   "শীট ফেস মাস্ক (৫পিস)",               "ত্বক",         280, 230),
        ("WAXING-STRIP","ওয়্যাক্সিং স্ট্রিপ কিট",            "বডি কেয়ার",   350, 288),
    ],
    "stationery": [
        ("PEN-BALL-12", "বলপয়েন্ট পেন ডজন (১২পিস)",         "পেন",          120,  98),
        ("PEN-GEL-6",   "জেল পেন ৬পিস সেট",                  "পেন",           90,  74),
        ("PENCIL-12",   "পেন্সিল ডজন (H)",                   "পেন্সিল",       60,  49),
        ("NOTEBOOK-A4", "A4 নোটবুক ৮০পেজ",                  "নোটবুক",       100,  82),
        ("NOTEBOOK-A5", "A5 নোটবুক ৬০পেজ",                  "নোটবুক",        70,  57),
        ("COPY-200PG",  "২০০ পেজ হার্ডকভার কপি",             "কপি",          160, 131),
        ("ERASER-2PC",  "রাবার ২পিস",                        "ইরেজার",        20,  16),
        ("RULER-30",    "স্কেল ৩০সেমি",                     "স্কেল",          25,  21),
        ("SHARPENER",   "পেন্সিল শার্পেনার",                  "শার্পেনার",     15,  12),
        ("SCISSOR",     "কাঁচি ৬ইঞ্চি",                     "কাঁচি",          95,  78),
        ("TAPE-CELLO",  "স্কচ টেপ ১ইঞ্চি",                  "টেপ",           40,  33),
        ("GLUE-UHU",    "UHU গ্লু ২১গ্রাম",                  "গ্লু",           80,  66),
        ("STAPLER",     "স্টেপলার + পিন সেট",                "অফিস",         220, 181),
        ("FILE-COVER",  "ক্লিয়ার ফাইল কভার (১০পিস)",        "ফাইল",          90,  74),
        ("CALC-SCI",    "সায়েন্টিফিক ক্যালকুলেটর",          "ক্যালকুলেটর",  680, 558),
        ("A4-PAPER-500","A4 পেপার ৫০০শিট",                  "পেপার",         480, 394),
        ("PAINT-WATER", "ওয়াটার কালার ১২ রঙ",               "আর্ট",          180, 148),
        ("CRAYON-24",   "ক্রেয়ন ২৪ রঙ",                     "আর্ট",          220, 181),
        ("MARKER-10",   "মার্কার পেন ১০ রঙ",                 "মার্কার",       280, 230),
        ("DRAWING-A3",  "A3 ড্রইং খাতা",                    "আর্ট",          130, 107),
    ],
    "mobile": [
        ("CASE-SAMSUNG","Samsung Galaxy কেস",                 "ফোন কেস",       350, 263),
        ("CASE-IPHONE", "iPhone কেস (সিলিকন)",               "ফোন কেস",       450, 338),
        ("SCREEN-SAM",  "Samsung টেম্পার্ড গ্লাস",           "স্ক্রিন গার্ড", 200, 150),
        ("SCREEN-IP",   "iPhone টেম্পার্ড গ্লাস",            "স্ক্রিন গার্ড", 250, 188),
        ("CHARGER-ORG", "অরিজিনাল চার্জার ২৫W",              "চার্জার",      1200, 900),
        ("CHARGER-LOCAL","লোকাল চার্জার ২০W",                "চার্জার",       450, 338),
        ("DATA-CABLE",  "টাইপ-সি ডেটা কেবল (ফাস্ট চার্জ)",  "কেবল",          280, 210),
        ("EARPHONE-ORG","অরিজিনাল ইয়ারফোন",                 "ইয়ারফোন",      850, 638),
        ("EARPHONE-COPY","কপি ইয়ারফোন",                     "ইয়ারফোন",      250, 188),
        ("POWERBANK-SL","স্লিম পাওয়ার ব্যাংক ১০০০০mAh",    "পাওয়ার ব্যাংক",1200, 900),
        ("MEM-CARD-64", "৬৪GB মেমোরি কার্ড (অরিজিনাল)",     "মেমোরি",        850, 638),
        ("POP-SOCKET",  "পপ সকেট",                           "আনুষঙ্গিক",    120,  90),
        ("RING-HOLDER", "ফোন রিং হোল্ডার",                  "আনুষঙ্গিক",    150, 113),
        ("USB-HUB-4P",  "USB হাব ৪ পোর্ট",                   "আনুষঙ্গিক",    480, 360),
        ("SELFIE-RING", "সেলফি রিং লাইট (১০ইঞ্চি)",          "আনুষঙ্গিক",    850, 638),
        ("REPAIR-GLASS","ডিসপ্লে গ্লাস রিপেয়ার সেট",        "রিপেয়ার",      350, 263),
        ("BATTERY-RPLC","রিপ্লেসমেন্ট ব্যাটারি",             "রিপেয়ার",      950, 713),
        ("SIMCARD-SLOT","সিম কার্ড ট্রে রিপ্লেসমেন্ট",       "রিপেয়ার",      150, 113),
        ("BACK-GLASS",  "ব্যাক গ্লাস প্যানেল",               "রিপেয়ার",      650, 488),
        ("CAR-HOLDER",  "কার ফোন হোল্ডার",                   "আনুষঙ্গিক",    380, 285),
    ],
    "furniture": [
        ("WARDROBE-3DR","৩ দরজার আলমারি (সেগুন)",            "আলমারি",     28000,21000),
        ("WARDROBE-2DR","২ দরজার আলমারি (মেলামাইন)",         "আলমারি",     12000, 9000),
        ("BED-KING",    "কিং সাইজ খাট (সেগুন)",             "খাট",        35000,26250),
        ("BED-SINGLE",  "সিঙ্গেল খাট (মেহগনি)",              "খাট",        12000, 9000),
        ("MATTRESS-KG", "কিং সাইজ ম্যাট্রেস (স্প্রিং)",     "ম্যাট্রেস",  18000,13500),
        ("MATTRESS-SG", "সিঙ্গেল ম্যাট্রেস (ফোম)",           "ম্যাট্রেস",   6500, 4875),
        ("DINING-6CH",  "ডাইনিং টেবিল ৬ চেয়ার সেট",        "ডাইনিং",     25000,18750),
        ("SOFA-3SEAT",  "৩ সিটার সোফা সেট",                  "সোফা",       22000,16500),
        ("SOFA-L-SHAPE","এল-শেপ সোফা (৫ সিট)",              "সোফা",       38000,28500),
        ("CENTER-TABLE","সেন্টার টেবিল (গ্লাস টপ)",          "টেবিল",       8500, 6375),
        ("OFFICE-CHAIR","অফিস চেয়ার (মেস)",                 "চেয়ার",       6500, 4875),
        ("STUDY-TABLE", "স্টাডি টেবিল + চেয়ার",             "টেবিল",       8000, 6000),
        ("BOOKSHELF-5", "৫ তাকের বুকশেলফ",                  "শেলফ",        7500, 5625),
        ("SHOE-RACK",   "জুতার র‍্যাক (১৮ পেয়ার)",          "র‍্যাক",      3500, 2625),
        ("TV-UNIT",     "TV ক্যাবিনেট (৬৫ইঞ্চি পর্যন্ত)",  "ক্যাবিনেট",   9500, 7125),
        ("DRESSER",     "ড্রেসিং টেবিল (মিরর সহ)",          "ড্রেসিং",     8500, 6375),
        ("KIDS-BED",    "বাচ্চাদের বাংক বেড",                "বাচ্চাদের",  15000,11250),
        ("PILLOW-PAIR", "বালিশ জোড়া (মাইক্রোফাইবার)",       "আনুষঙ্গিক",   950,  713),
        ("BED-SHEET",   "ডাবল বেড শিট সেট",                  "আনুষঙ্গিক",  1200,  900),
        ("CURTAIN-PR",  "পর্দা (এক জোড়া, ৭ফুট)",           "আনুষঙ্গিক",  2800, 2100),
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Seasonal demand multipliers for Bangladesh
# Week of year → multiplier
# Major peaks: Eid ul-Fitr (~Mar/Apr), Eid ul-Adha (~Jun), Puja (Oct), Winter (Dec-Jan)
# ─────────────────────────────────────────────────────────────────────────────
def seasonal_multiplier(dt: datetime, sector: str) -> float:
    m, d = dt.month, dt.day
    # Eid ul-Fitr 2026 ≈ March 30 (fasting month = March, shopping peaks last 10 days)
    if m == 3 and d >= 20: return 2.8 if sector in ("clothing","beauty","mobile") else 1.8
    if m == 4 and d <= 3:  return 2.2 if sector in ("clothing","beauty","mobile") else 1.5
    # Eid ul-Adha 2026 ≈ June 7
    if m == 5 and d >= 25: return 2.5 if sector in ("grocery","restaurant") else 1.6
    if m == 6 and d <= 10: return 2.2 if sector in ("grocery","restaurant") else 1.4
    # Winter Dec-Jan: clothing, beauty peaks; restaurant busy
    if m in (12, 1):       return 1.6 if sector in ("clothing","beauty","stationery") else 1.2
    # Back to school Jan-Feb
    if m == 2:             return 1.8 if sector == "stationery" else 1.0
    # Monsoon (Jul-Sep): hardware, grocery steady; clothing drops
    if m in (7, 8, 9):
        if sector == "hardware": return 1.3
        if sector == "clothing": return 0.7
        return 0.9
    # Puja (October): clothing, beauty, electronics
    if m == 10 and d <= 20: return 1.5 if sector in ("clothing","beauty","electronics") else 1.1
    return 1.0

# ─────────────────────────────────────────────────────────────────────────────
# Customer names (Bangladeshi)
# ─────────────────────────────────────────────────────────────────────────────
CUSTOMERS = [
    "মোঃ আব্দুর রহিম","করিম মিয়া","নূর মোহাম্মদ","জামাল উদ্দিন","আবুল কালাম",
    "সেলিনা আক্তার","নাসরিন বেগম","ফাতেমা খাতুন","রুবিনা বেগম","সাহানা পারভীন",
    "মিজানুর রহমান","তানভীর হোসেন","শাহিন আহমেদ","বিল্লাল হোসেন","হাসান আলী",
    "সুমাইয়া ইসলাম","মর্জিনা বেগম","রোকেয়া বেগম","মমতাজ বেগম","শিরিন আক্তার",
    "আশরাফুল ইসলাম","মাহমুদুর রহমান","রফিকুল ইসলাম","আনিসুর রহমান","শফিকুল ইসলাম",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def api_post(path, body, token=None):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{BASE}{path}", json=body, headers=h, timeout=15)
    try: return r.status_code, r.json()
    except: return r.status_code, {}

def api_get(path, token, org_id=None):
    h = {"Authorization": f"Bearer {token}"}
    if org_id: h["X-Organization-ID"] = org_id
    r = requests.get(f"{BASE}{path}", headers=h, timeout=15)
    try: return r.json()
    except: return {}


def ensure_user(email, password, display_name):
    sc, r = api_post("/api/app/auth/register", {"email": email, "password": password, "display_name": display_name})
    token = r.get("access_token")
    if not token:
        sc, r = api_post("/api/app/auth/login", {"email": email, "password": password})
        token = r.get("access_token")
    return token


biz_slug_map = {
    "আল-হেলাল ফার্মেসি": "al-helal-pharma",
    "মা-মণি জেনারেল স্টোর": "ma-moni-grocery",
    "নিউ লুক ফ্যাশন": "new-look-fashion",
    "স্বাদের রান্নাঘর": "shwader-kitchen",
    "ডিজিটাল জোন": "digital-zone",
    "বিল্ডার্স হার্ডওয়্যার": "builders-hardware",
    "গ্লামার বিউটি শপ": "glamour-beauty",
    "জ্ঞান ভাণ্ডার স্টেশনারি": "gyan-bhandar-stationery",
    "স্মার্ট মোবাইল সেন্টার": "smart-mobile-center",
    "আরামদায়ক ফার্নিচার": "aramdayak-furniture",
}

def ensure_org(token, name, sector, address):
    orgs = api_get("/api/app/organizations", token)
    org_list = orgs if isinstance(orgs, list) else orgs.get("organizations", [])
    existing = next((o for o in org_list if o["name"] == name), None)
    if existing:
        return existing["id"]
    slug = biz_slug_map.get(name, "biz") + "-" + str(RNG.randint(100, 999))
    sc, r = api_post("/api/app/organizations", {"name": name, "sector": sector, "slug": slug, "address": address}, token)
    return r.get("id")


def db_insert_products(db, org_id, sector):
    prods = PRODUCTS.get(sector, [])
    existing = {r[0] for r in db.execute(text("SELECT sku FROM products WHERE organization_id=:o"), {"o": org_id})}
    prod_map = {}
    for sku, name, cat, sell, cost in prods:
        if sku not in existing:
            pid = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO products
                  (id,organization_id,sku,name,category,unit,selling_price,cost_price,
                   reorder_level,active,track_expiry,created_at,updated_at)
                VALUES (:id,:org,:sku,:name,:cat,'pcs',:sell,:cost,20,1,0,datetime('now'),datetime('now'))
            """), {"id": pid,"org": org_id,"sku": sku,"name": name,"cat": cat,"sell": sell,"cost": cost})
    db.commit()
    rows = db.execute(text("SELECT sku,id,selling_price FROM products WHERE organization_id=:o"), {"o": org_id}).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


STORE_META = {
    "pharmacy":    {"theme": "pharmacy", "area": "মিরপুর-১০, ঢাকা",      "tagline": "স্বাস্থ্যসেবায় বিশ্বস্ত",        "category": "ফার্মেসি"},
    "grocery":     {"theme": "clean",    "area": "উত্তরা, ঢাকা",          "tagline": "তাজা পণ্য, সহজ লাভ",             "category": "গ্রোসারি"},
    "clothing":    {"theme": "fashion",  "area": "গুলশান, ঢাকা",          "tagline": "নিজেকে সাজিয়ে তুলুন",           "category": "পোশাক"},
    "restaurant":  {"theme": "warm",     "area": "ধানমণ্ডি, ঢাকা",        "tagline": "ঘরের রান্নার স্বাদ",             "category": "রেস্তোরাঁ"},
    "electronics": {"theme": "dark",     "area": "এলিফ্যান্ট রোড, ঢাকা", "tagline": "সঠিক পণ্য, সঠিক দাম",           "category": "ইলেকট্রনিক্স"},
    "hardware":    {"theme": "clean",    "area": "যাত্রাবাড়ী, ঢাকা",    "tagline": "নির্মাণের সাথী",                 "category": "হার্ডওয়্যার"},
    "beauty":      {"theme": "fashion",  "area": "বনানী, ঢাকা",           "tagline": "সৌন্দর্যের সর্বোত্তম সংগ্রহ",   "category": "বিউটি"},
    "stationery":  {"theme": "clean",    "area": "শান্তিনগর, ঢাকা",       "tagline": "লেখাপড়ার সেরা সাথী",            "category": "স্টেশনারি"},
    "mobile":      {"theme": "dark",     "area": "নিউ মার্কেট, ঢাকা",    "tagline": "স্মার্ট ফোন, স্মার্ট দাম",       "category": "মোবাইল"},
    "furniture":   {"theme": "warm",     "area": "ডেমরা, ঢাকা",           "tagline": "ঘর সাজানোর বিশ্বস্ত সাথী",      "category": "ফার্নিচার"},
}

THEME_COLOR = {
    "pharmacy": "#0e7c67",
    "clean":    "#0a8752",
    "fashion":  "#c43a8a",
    "warm":     "#e07b39",
    "dark":     "#f5c842",
}

def db_seed_store(db, org_id, sector, biz_name):
    """Create store + list first 8 products. Idempotent."""
    existing = db.execute(text("SELECT id FROM stores WHERE organization_id=:o"), {"o": org_id}).fetchone()
    if existing:
        return existing[0]

    meta = STORE_META.get(sector, {"theme": "clean", "area": "ঢাকা", "tagline": "", "category": sector})
    slug = biz_slug_map.get(biz_name, "store-" + str(RNG.randint(1000, 9999)))
    # ensure slug unique
    slug_check = db.execute(text("SELECT id FROM stores WHERE slug=:s"), {"s": slug}).fetchone()
    if slug_check:
        slug = slug + "-" + str(RNG.randint(100, 999))

    store_id = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO stores
          (id, organization_id, slug, is_active, display_name, tagline, theme_preset, theme_color,
           category, area, payment_cod, payment_bkash, payment_nagad,
           show_phone, show_exact_address, show_hours, show_price, show_stock_level, created_at, updated_at)
        VALUES (:id, :org, :slug, 1, :name, :tagline, :preset, :color,
                :cat, :area, 1, 1, 1,
                0, 0, 1, 1, 'available_only', datetime('now'), datetime('now'))
    """), {
        "id": store_id, "org": org_id, "slug": slug, "name": biz_name,
        "tagline": meta["tagline"], "preset": meta["theme"],
        "color": THEME_COLOR.get(meta["theme"], "#0a8752"),
        "cat": meta["category"], "area": meta["area"],
    })

    # list first 8 products
    prods = db.execute(text(
        "SELECT id FROM products WHERE organization_id=:o AND active=1 ORDER BY name LIMIT 8"
    ), {"o": org_id}).fetchall()
    for i, (pid,) in enumerate(prods):
        sp_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO store_products
              (id, store_id, product_id, is_listed, is_featured, sort_order, created_at, updated_at)
            VALUES (:id, :store, :prod, 1, :feat, :sort, datetime('now'), datetime('now'))
        """), {
            "id": sp_id, "store": store_id, "prod": pid,
            "feat": 1 if i < 2 else 0, "sort": i,
        })
    db.commit()
    return store_id


def db_ensure_branch(db, org_id, address):
    r = db.execute(text("SELECT id FROM branches WHERE organization_id=:o LIMIT 1"), {"o": org_id}).fetchone()
    if r: return r[0]
    bid = str(uuid.uuid4())
    db.execute(text("""
        INSERT INTO branches (id,organization_id,name,address,active,created_at,updated_at)
        VALUES (:id,:org,'প্রধান শাখা',:addr,1,datetime('now'),datetime('now'))
    """), {"id": bid,"org": org_id,"addr": address})
    db.commit()
    return bid


def db_ensure_customers(db, org_id, n=25):
    existing = db.execute(text("SELECT id FROM customers WHERE organization_id=:o"), {"o": org_id}).fetchall()
    if len(existing) >= n:
        return [r[0] for r in existing[:n]]
    cids = [r[0] for r in existing]
    for i in range(len(existing), n):
        cid = str(uuid.uuid4())
        code = f"CUST-{RNG.randint(1000,9999)}"
        db.execute(text("""
            INSERT INTO customers (id,organization_id,code,display_name,marketing_consent,created_at,updated_at)
            VALUES (:id,:org,:code,:name,1,datetime('now'),datetime('now'))
        """), {"id": cid,"org": org_id,"code": code,"name": CUSTOMERS[i % len(CUSTOMERS)]})
        cids.append(cid)
    db.commit()
    return cids


def db_get_existing_dates(db, org_id):
    rows = db.execute(text("SELECT DISTINCT date(sold_at) FROM sales_orders WHERE organization_id=:o"), {"o": org_id}).fetchall()
    return {r[0] for r in rows}


def db_seed_day(db, org_id, branch_id, prod_map, customer_ids, sector, day_dt, inv_ctr):
    skus = list(prod_map.keys())
    lo, hi = BUSINESSES[next(i for i,b in enumerate(BUSINESSES) if b["sector"] == sector)]["daily_orders"]
    n = int(RNG.randint(lo, hi) * seasonal_multiplier(day_dt, sector))
    n = max(1, min(n, hi * 3))

    weekday = day_dt.weekday()
    if weekday == 5: n = int(n * 0.55)   # Saturday half-day in BD
    if weekday == 4: n = int(n * 1.35)   # Friday busy

    for _ in range(max(1, n)):
        inv_ctr[0] += 1
        order_id   = str(uuid.uuid4())
        inv_no     = f"INV-{org_id[:6].upper()}-{day_dt.strftime('%Y%m%d')}-{inv_ctr[0]:05d}"
        hour       = RNG.randint(9, 21)
        sold_at    = day_dt.replace(hour=hour, minute=RNG.randint(0,59), second=RNG.randint(0,59))
        customer_id = RNG.choice(customer_ids) if RNG.random() < 0.65 else None
        n_items    = RNG.randint(1, 4 if sector != "furniture" else 2)
        chosen     = RNG.sample(skus, min(n_items, len(skus)))

        total = 0
        items = []
        for sku in chosen:
            pid, unit_price = prod_map[sku]
            qty     = RNG.randint(1, 3 if sector != "furniture" else 1)
            disc    = round(unit_price * RNG.uniform(0, 0.05), 2) if RNG.random() < 0.18 else 0.0
            lt      = round((unit_price - disc) * qty, 2)
            total  += lt
            items.append((sku, pid, qty, unit_price, disc, lt))

        db.execute(text("""
            INSERT OR IGNORE INTO sales_orders
              (id,organization_id,branch_id,customer_id,invoice_number,sold_at,
               channel,subtotal,discount_amount,tax_amount,total,status,created_at,updated_at)
            VALUES (:id,:org,:br,:cust,:inv,:sold,
                    'walk_in',:tot,0,0,:tot,'completed',datetime('now'),datetime('now'))
        """), {"id": order_id,"org": org_id,"br": branch_id,"cust": customer_id,
               "inv": inv_no,"sold": sold_at.strftime("%Y-%m-%d %H:%M:%S"),"tot": round(total,2)})

        for sku, pid, qty, up, disc, lt in items:
            db.execute(text("""
                INSERT INTO sales_order_items
                  (id,organization_id,order_id,product_id,quantity,unit_price,unit_cost_at_sale,
                   discount_amount,line_total,returned_quantity,created_at,updated_at)
                VALUES (:id,:org,:oid,:pid,:qty,:up,:cost,:disc,:lt,0,datetime('now'),datetime('now'))
            """), {"id": str(uuid.uuid4()),"org": org_id,"oid": order_id,"pid": pid,
                   "qty": qty,"up": up,"cost": round(up * 0.75, 2),"disc": disc,"lt": lt})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
db = SessionLocal()
db.execute(text("PRAGMA journal_mode=WAL"))
db.execute(text("PRAGMA synchronous=NORMAL"))

print("=" * 60)
print("  B-SMART  —  10 Bangladeshi SME Demo Businesses")
print("=" * 60)

for biz in BUSINESSES:
    print(f"\n▶ {biz['org_name']}  [{biz['sector']}]")

    token = ensure_user(biz["email"], biz["password"], biz["display_name"])
    if not token:
        print("  ✗ Auth failed"); continue
    print(f"  ✓ User OK")

    org_id = ensure_org(token, biz["org_name"], biz["sector"], biz["address"])
    if not org_id:
        print("  ✗ Org create failed"); continue
    print(f"  ✓ Org: {org_id[:8]}")

    branch_id  = db_ensure_branch(db, org_id, biz["address"])
    prod_map   = db_insert_products(db, org_id, biz["sector"])
    cust_ids   = db_ensure_customers(db, org_id, 25)
    store_id   = db_seed_store(db, org_id, biz["sector"], biz["org_name"])
    print(f"  ✓ Branch + {len(prod_map)} products + {len(cust_ids)} customers + store {store_id[:8] if store_id else 'skip'}")

    existing_dates = db_get_existing_dates(db, org_id)
    print(f"  Existing dates: {len(existing_dates)} — seeding gaps...")

    current = START
    added, inv_ctr = 0, [RNG.randint(10000, 50000)]
    while current <= TODAY:
        ds = current.strftime("%Y-%m-%d")
        if ds not in existing_dates:
            db_seed_day(db, org_id, branch_id, prod_map, cust_ids, biz["sector"], current, inv_ctr)
            added += 1
        if added % 60 == 0 and added > 0:
            db.commit()
            print(f"    ... {added} days seeded")
        current += timedelta(days=1)

    db.commit()
    total_dates = len(db_get_existing_dates(db, org_id))
    orders_count = db.execute(text("SELECT COUNT(*) FROM sales_orders WHERE organization_id=:o"), {"o": org_id}).fetchone()[0]
    print(f"  ✓ {added} new days added. Total: {total_dates} dates, {orders_count} orders")

db.close()


print("\n10 synthetic business demo seed completed. Old ML training intentionally NOT run.\n")
