"""
=============================================================
STEP 0a: GENERATE THE BANGLADESH-PHARMACY DATASET
AI-Powered Business Analytics System - CSE 4th Year Thesis
=============================================================
Replaces the old legacy 32k-row multi-sector Faker dataset with one that is
actually representative of a Bangladeshi retail pharmacy, built from real
data wherever real data exists on the internet, and honestly-labeled
synthetic data everywhere it does not (no public dataset anywhere combines
Bangladeshi origin + observed pharmacy transactions + customer identity --
see docs/REAL_DATA_SOURCES.md for the exhaustive prior search that
established this gap).

REAL inputs used here:
  - data/real_public/bd_medicine_catalog.csv
        Mendeley "Medicinal Products in Bangladesh - A Dataset of Generic and
        Brand Names, Dosage Strengths, and Manufacturers" (DOI
        10.17632/zhtvkny53n.1, CC BY 4.0). 21,360 real Bangladeshi medicine
        SKUs: genericName, brandName, packageMark, dosageType, strength,
        manufacturer. NO price column.
  - data/real_public/bd_retailer_demand.xlsx
        Mendeley Bangladeshi daily-demand series (DOI 10.17632/xwmbk7n3c8.1,
        CC BY 4.0), already in this repo. Used only to fit real demand SHAPE
        (day-of-week, month-of-year, year-over-year growth, noise scale) --
        never blended with its own quantity/customer numbers, which belong to
        a different retailer entirely.

SYNTHETIC, explicitly labeled (no real public source exists for these, per
docs/REAL_DATA_SOURCES.md's Tier-1 finding):
  - Unit_Price_BDT: no source dataset has real per-SKU price, so prices are
    assigned from published/typical Bangladeshi pharmacy retail price BANDS
    per drug class and dosage form -- a declared assumption, not a fabricated
    "real" number, same discipline as the ASSUMPTIONS dict in
    13_bsmart_recommendation_engine.py.
  - Customers, transactions, branches, Marketing_Consent, Batch_No/Expiry_Date.

Writes:
  BD_Pharmacy_Dataset.csv   (flat file, same schema contract as the
                                        legacy file -- 00_normalize_dataset.py
                                        runs on it unmodified)
  normalized_data/DATASET_MANIFEST.md (declares exactly which columns are
                                        real-sourced vs. synthetic-generated)
"""
import utf8_console  # noqa: F401
import zlib
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
rng = np.random.default_rng(SEED)

# ============================================================ 1. REAL CATALOG
print("[1] Loading real Bangladeshi medicine catalog ...")
catalog = pd.read_csv("data/real_public/bd_medicine_catalog.csv")

# A single retail pharmacy stocks a bounded assortment, not all 21k SKUs on
# the national market. Pick real, recognisable generics spanning the classes
# a BD retail pharmacy actually carries day-to-day (matches the pharmacy
# scope guideline: antibiotics, analgesics, chronic-disease meds, vitamins).
DRUG_CLASS_GENERICS = {
    "Analgesic/Antipyretic": ["Paracetamol", "Ibuprofen", "Diclofenac", "Aceclofenac"],
    "Antibiotic":            ["Amoxicillin", "Azithromycin", "Ciprofloxacin", "Doxycycline", "Ceftriaxone"],
    "Antacid/PPI":           ["Omeprazole", "Esomeprazole", "Pantoprazole", "Ranitidine", "Domperidone"],
    "Antidiabetic":          ["Metformin", "Glimepiride", "Insulin"],
    "Antihypertensive":      ["Losartan", "Amlodipine", "Atorvastatin"],
    "Antihistamine/Cold":    ["Cetirizine", "Montelukast", "Salbutamol"],
    "Vitamins/Supplements":  ["Vitamin C", "Vitamin B", "Vitamin D", "Multivitamin"],
    "Antiparasitic":         ["Metronidazole"],
}
# Declared assumption (no real per-SKU price source exists): typical retail
# strip/unit price bands in BDT, by drug class. Printed to the manifest.
PRICE_BAND_BDT = {
    "Analgesic/Antipyretic": (1.5, 8),
    "Antibiotic":            (8, 35),
    "Antacid/PPI":           (5, 25),
    "Antidiabetic":          (3, 20),
    "Antihypertensive":      (4, 18),
    "Antihistamine/Cold":    (2, 12),
    "Vitamins/Supplements":  (2, 15),
    "Antiparasitic":         (3, 10),
}
QTY_RANGE = {  # units per transaction (tablets/pieces), by class
    "Analgesic/Antipyretic": (10, 20),
    "Antibiotic":            (6, 21),
    "Antacid/PPI":           (10, 30),
    "Antidiabetic":          (30, 90),
    "Antihypertensive":      (30, 90),
    "Antihistamine/Cold":    (10, 20),
    "Vitamins/Supplements":  (10, 60),
    "Antiparasitic":         (6, 12),
}

skus = []
for drug_class, generics in DRUG_CLASS_GENERICS.items():
    for generic in generics:
        matches = catalog[catalog["genericName"].str.contains(generic, case=False, na=False)]
        if matches.empty:
            continue
        # Prefer well-known local manufacturers, cap at a handful of real
        # brands per generic so the assortment stays a realistic shop size.
        det_seed = SEED + zlib.crc32(generic.encode("utf-8")) % 1000
        picked = matches.sample(n=min(4, len(matches)), random_state=det_seed)
        for _, row in picked.iterrows():
            skus.append({
                "Product_Name": row["brandName"],
                "Generic_Name": row["genericName"],
                "Dosage_Form": row["dosageType"],
                "Manufacturer": row["manufacturer"],
                "Drug_Class": drug_class,
            })

sku_df = pd.DataFrame(skus).drop_duplicates(subset="Product_Name").reset_index(drop=True)
print(f"    {len(sku_df)} real medicine SKUs selected across {len(DRUG_CLASS_GENERICS)} drug classes")

lo, hi = zip(*[PRICE_BAND_BDT[c] for c in sku_df["Drug_Class"]])
sku_df["Unit_Price_BDT"] = rng.uniform(lo, hi).round(2)

# ---- Layer-6 product constraints -------------------------------------------
# Cold chain and prescription status are REAL pharmacy domain facts, not
# invented flags: insulin must be kept at 2-8 degC, and antibiotics /
# chronic-disease medicines are prescription-only in Bangladesh (DGDA
# schedule). They drive genuine constraints -- a cold-chain SKU cannot be
# ordered beyond refrigerated capacity, and a prescription-only SKU may not
# be promoted to a customer.
COLD_CHAIN_GENERICS = ("Insulin",)
PRESCRIPTION_ONLY_CLASSES = {"Antibiotic", "Antidiabetic", "Antihypertensive"}
sku_df["Cold_Chain_Required"] = sku_df["Generic_Name"].str.contains(
    "|".join(COLD_CHAIN_GENERICS), case=False, na=False)
sku_df["Prescription_Only"] = sku_df["Drug_Class"].isin(PRESCRIPTION_ONLY_CLASSES)
# Declared assumption: suppliers ship in carton multiples, so MOQ is a
# multiple of the pack size and larger for cheap fast-movers.
sku_df["MOQ_Units"] = np.where(sku_df["Unit_Price_BDT"] < 10, 100, 50)
print(f"    {int(sku_df['Cold_Chain_Required'].sum())} cold-chain SKUs, "
      f"{int(sku_df['Prescription_Only'].sum())} prescription-only SKUs")

# ============================================================ 2. REAL DEMAND SHAPE
print("[2] Fitting demand shape from the real BD retailer-demand series ...")
demand = pd.read_excel("data/real_public/bd_retailer_demand.xlsx")
demand["dow"] = demand["date"].dt.dayofweek
demand["month"] = demand["date"].dt.month
demand["year"] = demand["date"].dt.year
overall_mean = demand["sales"].mean()
DOW_MULT = (demand.groupby("dow")["sales"].mean() / overall_mean).to_dict()
MONTH_MULT = (demand.groupby("month")["sales"].mean() / overall_mean).to_dict()
yearly = demand.groupby("year")["sales"].mean()
CAGR = (yearly.iloc[-1] / yearly.iloc[0]) ** (1 / (yearly.index[-1] - yearly.index[0])) - 1
NOISE_CV = demand["sales"].std() / overall_mean
print(f"    day-of-week mult: {[round(v,2) for v in DOW_MULT.values()]}")
print(f"    month mult range: {min(MONTH_MULT.values()):.2f}-{max(MONTH_MULT.values()):.2f}, "
      f"YoY growth: {CAGR*100:.1f}%, noise CV: {NOISE_CV:.2f}")

# ============================================================ 3. GEOGRAPHY (real)
DIVISIONS = {
    "Dhaka": ["Dhaka", "Gazipur", "Narayanganj"],
    "Chattogram": ["Chattogram", "Cox's Bazar", "Cumilla"],
    "Rajshahi": ["Rajshahi", "Bogura"],
    "Khulna": ["Khulna", "Jessore"],
    "Barishal": ["Barishal"],
    "Sylhet": ["Sylhet"],
    "Rangpur": ["Rangpur"],
    "Mymensingh": ["Mymensingh"],
}
DIV_LIST = list(DIVISIONS.keys())

# ============================================================ 4. CUSTOMERS (synthetic)
print("[3] Generating customers (synthetic, labeled) ...")
N_CUSTOMERS = 5000
FIRST_NAMES = ["Rahim", "Karim", "Jasim", "Fatema", "Ayesha", "Nusrat", "Sultana", "Kabir",
               "Shakil", "Mahmud", "Rubel", "Shirin", "Tania", "Rezwan", "Hasina", "Anwar",
               "Salma", "Mizan", "Farhana", "Imran"]
LAST_NAMES = ["Islam", "Ahmed", "Hossain", "Rahman", "Khan", "Chowdhury", "Uddin", "Akter",
              "Begum", "Alam", "Hasan", "Miah"]

cust_division = rng.choice(DIV_LIST, size=N_CUSTOMERS)
customers = pd.DataFrame({
    "Customer_ID": [f"CUST-BD-{i+1:05d}" for i in range(N_CUSTOMERS)],
    "Customer_Name": [f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}" for _ in range(N_CUSTOMERS)],
    "Customer_Age": rng.integers(18, 75, N_CUSTOMERS),
    "Customer_Gender": rng.choice(["Male", "Female"], N_CUSTOMERS, p=[0.52, 0.48]),
    "Customer_Type": rng.choice(["Walk-in", "Regular", "Prescription-Repeat"], N_CUSTOMERS, p=[0.45, 0.35, 0.20]),
    "Division": cust_division,
    "District": [rng.choice(DIVISIONS[d]) for d in cust_division],
    # Declared assumption: real-world retail SMS/call marketing opt-in rates
    # are typically 40-70%; 55% used here, sampled per customer.
    "Marketing_Consent": rng.choice([True, False], N_CUSTOMERS, p=[0.55, 0.45]),
})
# Latent activity tier drives how often a customer transacts. It is NOT the
# label: Customer_Segment below is the shop's own manually-maintained CRM tier,
# which correlates with spend but is noisy -- exactly like a real pharmacy's
# hand-tagged customer list. Without that noise the label would be a
# deterministic function of the same variable that drives the features, and
# every classifier would score ~100% for a reason that has nothing to do with
# the modelling being good.
activity = rng.choice(["low", "mid", "high", "vip"], N_CUSTOMERS, p=[0.40, 0.35, 0.18, 0.07])
customers["_activity"] = activity

ACTIVITY_RANK = {"low": 0, "mid": 1, "high": 2, "vip": 3}
SEGMENTS = ["Low-Engagement", "Moderate-Spender", "High-Value", "VIP-Platinum"]
base_rank = customers["_activity"].map(ACTIVITY_RANK).to_numpy()
# Owner's perceived value: true tier plus substantial perception noise, so
# adjacent tiers overlap heavily rather than separating cleanly.
perceived = base_rank + rng.normal(0, 0.85, N_CUSTOMERS)
seg_rank = np.clip(np.rint(perceived), 0, 3).astype(int)
# Manual tagging drift: ~18% of records are stale/mis-tagged by one tier.
drift = rng.random(N_CUSTOMERS) < 0.18
seg_rank = np.clip(seg_rank + rng.choice([-1, 1], N_CUSTOMERS) * drift, 0, 3).astype(int)
customers["Customer_Segment"] = [SEGMENTS[r] for r in seg_rank]

# Frequency and CLV are recorded shop-side estimates. They track the latent
# tier but with wide, overlapping lognormal spread -- not a clean giveaway.
FREQ_BY_ACTIVITY = {"low": 0.7, "mid": 1.6, "high": 3.2, "vip": 6.0}
freq_base = customers["_activity"].map(FREQ_BY_ACTIVITY).to_numpy(dtype=float)
customers["Purchase_Frequency_Monthly"] = np.round(
    np.clip(freq_base * rng.lognormal(0, 0.55, N_CUSTOMERS), 0.2, 12.0), 2)
CLV_BY_ACTIVITY = {"low": 2500, "mid": 11000, "high": 35000, "vip": 95000}
clv_base = customers["_activity"].map(CLV_BY_ACTIVITY).to_numpy(dtype=float)
customers["Customer_Lifetime_Value_BDT"] = np.round(
    clv_base * rng.lognormal(0, 0.6, N_CUSTOMERS), 2)

# ============================================================ 5. TRANSACTIONS
print("[4] Generating transactions calibrated to the real demand shape ...")
N_TRANSACTIONS = 30000
DATE_START, DATE_END = pd.Timestamp("2021-01-01"), pd.Timestamp("2024-12-31")
all_days = pd.date_range(DATE_START, DATE_END, freq="D")

day_weight = np.array([
    DOW_MULT[d.dayofweek] * MONTH_MULT[d.month] * ((1 + CAGR) ** ((d.year - DATE_START.year)))
    for d in all_days
])
day_weight = day_weight / day_weight.sum()

# Customers with higher activity transact more often (Zipf-ish via activity weight)
cust_weight = customers["_activity"].map({"low": 1, "mid": 3, "high": 7, "vip": 15}).to_numpy(dtype=float)
cust_weight = cust_weight / cust_weight.sum()

# Idiosyncratic lapse: ~28% of customers stop coming at some point for reasons
# the data cannot see (moved away, switched pharmacy, patient recovered or
# died). Without this, recency is a pure function of visit frequency and the
# churn label becomes almost trivially predictable -- real churn is not.
lapses = rng.random(N_CUSTOMERS) < 0.28
lapse_offset = rng.beta(2.2, 1.4, N_CUSTOMERS)  # skewed toward later in the window
window_days = (DATE_END - DATE_START).days
lapse_date = pd.Series(
    [DATE_START + pd.Timedelta(days=int(o * window_days)) if lapsed else DATE_END
     for o, lapsed in zip(lapse_offset, lapses)],
    index=customers["Customer_ID"].to_numpy(),
)

# Product popularity: chronic-disease meds (antidiabetic/antihypertensive) and
# analgesics sell far more often than occasional-use antibiotics -- Zipf-like.
class_popularity = {
    "Analgesic/Antipyretic": 5, "Antibiotic": 2, "Antacid/PPI": 3, "Antidiabetic": 4,
    "Antihypertensive": 4, "Antihistamine/Cold": 2, "Vitamins/Supplements": 3, "Antiparasitic": 1,
}
prod_weight = sku_df["Drug_Class"].map(class_popularity).to_numpy(dtype=float)
prod_weight = prod_weight / prod_weight.sum()

# Oversample, drop post-lapse transactions, then trim back to N_TRANSACTIONS.
oversample = int(N_TRANSACTIONS * 1.6)
cand_dates = pd.to_datetime(rng.choice(all_days.to_numpy(), size=oversample, p=day_weight))
cand_customers = rng.choice(customers["Customer_ID"].to_numpy(), size=oversample, p=cust_weight)
cand_products = rng.choice(sku_df["Product_Name"].to_numpy(), size=oversample, p=prod_weight)
keep = cand_dates <= lapse_date.loc[cand_customers].to_numpy()
txn_dates = cand_dates[keep][:N_TRANSACTIONS]
txn_customers = cand_customers[keep][:N_TRANSACTIONS]
txn_products = cand_products[keep][:N_TRANSACTIONS]
N_TRANSACTIONS = len(txn_dates)
print(f"    {lapses.sum():,} of {N_CUSTOMERS:,} customers lapse mid-window (unobservable cause)")

# Synthetic branch profiles; Business_Category is real-constant "Pharmacy".
# Storage_Capacity_Units is shelf space, Cold_Chain_Capacity_Units is
# refrigerated space -- a small independent shop has one domestic fridge, a
# hospital pharmacy has a proper cold room. Both are Layer-6 constraints:
# an order that does not fit cannot be recommended regardless of its utility.
BRANCHES = [
    # (sub_category, type, employees, annual_revenue, storage_units, cold_chain_units)
    ("Independent Pharmacy", "Retail", 3, 4_500_000, 3_000, 120),
    ("Chain Pharmacy",       "Retail", 8, 12_000_000, 9_000, 400),
    ("Chain Pharmacy",       "Retail", 12, 18_000_000, 14_000, 700),
    ("Hospital Pharmacy",    "Retail+Wholesale", 15, 25_000_000, 25_000, 2_000),
]
branch_idx = rng.integers(0, len(BRANCHES), N_TRANSACTIONS)

fact = pd.DataFrame({
    "Transaction_ID": [f"TXN-BD-{i+1:06d}" for i in range(N_TRANSACTIONS)],
    "Customer_ID": txn_customers,
    "Transaction_Date": txn_dates,
    "Product_Name": txn_products,
})
fact = fact.merge(sku_df, on="Product_Name", how="left")
fact = fact.merge(customers[["Customer_ID", "Division"]], on="Customer_ID", how="left")

qty_lo = fact["Drug_Class"].map(lambda c: QTY_RANGE[c][0]).to_numpy()
qty_hi = fact["Drug_Class"].map(lambda c: QTY_RANGE[c][1]).to_numpy()
fact["Quantity"] = rng.integers(qty_lo, qty_hi + 1)
fact["Unit_Price_BDT"] = fact["Unit_Price_BDT"] * rng.uniform(0.95, 1.05, N_TRANSACTIONS)
fact["Unit_Price_BDT"] = fact["Unit_Price_BDT"].round(2)
fact["Gross_Amount_BDT"] = (fact["Quantity"] * fact["Unit_Price_BDT"]).round(2)
fact["Discount_Percent"] = rng.choice([0, 0, 0, 5, 10, 15], N_TRANSACTIONS).astype(float)
fact["Discount_Amount_BDT"] = (fact["Gross_Amount_BDT"] * fact["Discount_Percent"] / 100).round(2)
fact["Net_Amount_BDT"] = (fact["Gross_Amount_BDT"] - fact["Discount_Amount_BDT"]).round(2)
fact["Profit_Margin_Percent"] = rng.uniform(12, 28, N_TRANSACTIONS).round(2)
fact["Profit_Amount_BDT"] = (fact["Net_Amount_BDT"] * fact["Profit_Margin_Percent"] / 100).round(2)

order_channel = rng.choice(["In-Store", "Home Delivery"], N_TRANSACTIONS, p=[0.8, 0.2])
fact["Order_Channel"] = order_channel
fact["Delivery_Days"] = np.where(order_channel == "In-Store", 0, rng.integers(1, 4, N_TRANSACTIONS))
fact["Payment_Method"] = rng.choice(["Cash", "bKash", "Nagad", "Card"], N_TRANSACTIONS, p=[0.5, 0.28, 0.17, 0.05])
fact["Delivery_Status"] = np.where(order_channel == "In-Store", "Completed",
                                    rng.choice(["Delivered", "Delivered", "Delivered", "Cancelled"], N_TRANSACTIONS))

is_returned = rng.choice(["Yes", "No"], N_TRANSACTIONS, p=[0.05, 0.95])
fact["Is_Returned"] = is_returned
return_reasons = ["Wrong Item Dispensed", "Damaged Packaging", "Customer Changed Mind", "Adverse Reaction"]
fact["Return_Reason"] = [rng.choice(return_reasons) if r == "Yes" else np.nan for r in is_returned]

fact["Stock_Level"] = rng.choice(["Out-of-Stock", "Low", "Medium", "High"], N_TRANSACTIONS, p=[0.05, 0.15, 0.45, 0.35])

# ---- Layer-6 inventory constraints (declared assumptions) -------------------
# Inventory position at the time of the sale: what is already on order from the
# supplier, and what is owed to customers. Both change the reorder arithmetic:
# IP = on-hand + on-order - backorder, so ignoring them over-orders.
# Out-of-stock lines are the ones most likely to have a replenishment already
# in flight and customers waiting, so both are conditioned on stock status.
_oos = (fact["Stock_Level"] == "Out-of-Stock").to_numpy()
_low = (fact["Stock_Level"] == "Low").to_numpy()
fact["Incoming_Stock_Units"] = np.where(
    _oos, rng.integers(0, 120, N_TRANSACTIONS),
    np.where(_low, rng.integers(0, 60, N_TRANSACTIONS), rng.integers(0, 20, N_TRANSACTIONS)))
fact["Backorder_Units"] = np.where(
    _oos, rng.integers(0, 40, N_TRANSACTIONS),
    np.where(_low, rng.integers(0, 12, N_TRANSACTIONS), 0))
fact["Customer_Satisfaction_Score"] = np.clip(rng.normal(4.1, 0.6, N_TRANSACTIONS), 1, 5).round(1)

# Declared assumption: 12-36 month shelf life at time of sale, typical for
# tablets/capsules/syrups; no real batch/expiry source exists for this dataset.
shelf_months = rng.integers(12, 37, N_TRANSACTIONS)
fact["Batch_No"] = [f"B{rng.integers(1000,9999)}-{d.strftime('%y%m')}" for d in fact["Transaction_Date"]]
fact["Expiry_Date"] = fact["Transaction_Date"] + pd.to_timedelta(shelf_months * 30, unit="D")

channel_options = np.array(["SMS Campaign", "In-Store Signage", "Facebook Ad", np.nan], dtype=object)
fact["Marketing_Channel"] = rng.choice(channel_options, N_TRANSACTIONS, p=[0.25, 0.35, 0.15, 0.25])
campaign_options = ["Loyalty Discount", "Seasonal Offer", "New Customer"]
fact["Campaign_Type"] = [
    rng.choice(campaign_options) if pd.notna(m) else np.nan
    for m in fact["Marketing_Channel"]
]

branch_choice = [BRANCHES[i] for i in branch_idx]
fact["Business_Category"] = "Pharmacy"
fact["Business_Sub_Category"] = [b[0] for b in branch_choice]
fact["Business_Type"] = [b[1] for b in branch_choice]
fact["Employee_Count"] = [b[2] + rng.integers(-1, 2) for b in branch_choice]
fact["Annual_Revenue_BDT"] = [b[3] * rng.uniform(0.9, 1.1) for b in branch_choice]
fact["Storage_Capacity_Units"] = [b[4] for b in branch_choice]
fact["Cold_Chain_Capacity_Units"] = [b[5] for b in branch_choice]

# Days_Since_Last_Purchase: real gap to this customer's previous transaction
# in the generated data (first purchase gets a plausible acquisition-age proxy).
fact = fact.sort_values(["Customer_ID", "Transaction_Date"]).reset_index(drop=True)
prev_date = fact.groupby("Customer_ID")["Transaction_Date"].shift(1)
gap_days = (fact["Transaction_Date"] - prev_date).dt.days
filler = rng.integers(30, 400, len(fact))
fact["Days_Since_Last_Purchase"] = np.where(gap_days.isna(), filler, gap_days).astype(int)

# Date-derived dim_date columns
fact["Year"] = fact["Transaction_Date"].dt.year
fact["Month"] = fact["Transaction_Date"].dt.month
fact["Month_Name"] = fact["Transaction_Date"].dt.month_name()
fact["Quarter"] = fact["Transaction_Date"].dt.quarter
fact["Week_Number"] = fact["Transaction_Date"].dt.isocalendar().week.astype(int)
fact["Day_of_Week"] = fact["Transaction_Date"].dt.day_name()


def season_of(d):
    if d.month == 4:
        return "Pohela Boishakh"
    if d.month == 12:
        return "Year-End Sale"
    if d.month in (6, 7):
        return "Eid Season"
    if d.month in (3,):
        return "Ramadan"
    if d.month in (6, 7, 8, 9):
        return "Monsoon"
    if d.month in (11, 12, 1):
        return "Winter"
    return "Regular"


fact["Season"] = fact["Transaction_Date"].apply(season_of)

flat = fact.drop(columns=["Division"]).merge(
    customers.drop(columns=["_activity"]), on="Customer_ID", how="left"
)
flat = flat.drop(columns=["Generic_Name", "Dosage_Form", "Manufacturer", "Drug_Class"])

print(f"    {len(flat):,} transactions x {flat.shape[1]} columns generated")

# ============================================================ 6. WRITE OUTPUT
Path("normalized_data").mkdir(exist_ok=True)
flat.to_csv("BD_Pharmacy_Dataset.csv", index=False, encoding="utf-8-sig")
print("    -> saved BD_Pharmacy_Dataset.csv")

sku_df.to_csv("data/real_public/bd_pharmacy_sku_catalog.csv", index=False, encoding="utf-8-sig")

manifest = f"""# Dataset manifest: Bangladesh-pharmacy dataset

Generated by `00a_generate_pharmacy_dataset.py`. Replaces the legacy 32k-row
multi-sector Faker dataset. Same tiering discipline as `docs/REAL_DATA_SOURCES.md`.

## Real-sourced columns

| Column(s) | Source |
|---|---|
| Product_Name (brand), Generic_Name, Dosage_Form, Manufacturer (see `data/real_public/bd_pharmacy_sku_catalog.csv`) | Mendeley "Medicinal Products in Bangladesh" (DOI 10.17632/zhtvkny53n.1, CC BY 4.0) -- {len(sku_df)} real BD medicine SKUs |
| Division, District | Real Bangladesh administrative geography |
| Day-of-week / month-of-year / year-over-year transaction-volume shape | Fitted from `data/real_public/bd_retailer_demand.xlsx` (Mendeley DOI 10.17632/xwmbk7n3c8.1, real BD daily demand, 2013-2017). Only the SHAPE (seasonality/trend/noise) is reused -- its own quantity and customer numbers belong to a different retailer and are not mixed in. |

## Synthetic, explicitly labeled (no real public source exists -- see docs/REAL_DATA_SOURCES.md)

| Column(s) | Why synthetic |
|---|---|
| Unit_Price_BDT | No dataset anywhere publishes real per-SKU Bangladeshi pharmacy retail prices; assigned from typical price BANDS per drug class (declared assumption, see `PRICE_BAND_BDT` in the generator script), not scraped per-SKU. |
| Customer_ID, Customer_Name, Customer_Age, Customer_Gender, Customer_Type, Purchase_Frequency_Monthly, Customer_Lifetime_Value_BDT | No public Bangladeshi dataset combines customer identity with pharmacy purchase history (structural gap, not a search failure -- confirmed in `docs/REAL_DATA_SOURCES.md`). |
| Customer_Segment | Modelled as the shop's **manually maintained CRM tier**: it tracks the customer's latent value but carries perception noise (sigma 0.85 tier units) plus ~18% stale/mis-tagged records. This is deliberate -- if the label were a clean function of the latent tier that also drives the features, every classifier would score ~100% for reasons unrelated to modelling quality. |
| Customer lapse (drives Recency, and therefore the churn label) | ~28% of customers stop purchasing at a random point in the window for causes the data cannot observe (moved, switched pharmacy, treatment ended). Without this, recency is a pure function of visit frequency and churn becomes trivially predictable. |
| Marketing_Consent | Sampled at a declared assumed opt-in rate (55%); real Tier-1 pharmacy partner data will carry an actual consent field once collected (`docs/REAL_DATA_PROTOCOL.md`). |
| Transaction linkage (which customer bought which SKU when), Quantity, Batch_No, Expiry_Date, Business branch profile, discounts, returns, satisfaction score | Generated; quantities/timing follow the REAL demand shape above, but the linkage itself is synthetic. |

## Scale

{N_CUSTOMERS:,} customers generated ({flat['Customer_ID'].nunique():,} with at least one
transaction), {N_TRANSACTIONS:,} transactions, {len(sku_df)} real medicine SKUs across
{len(DRUG_CLASS_GENERICS)} drug classes, {DATE_START.date()} to {DATE_END.date()}.
{lapses.sum():,} customers ({lapses.mean()*100:.0f}%) lapse mid-window.
"""
Path("normalized_data/DATASET_MANIFEST.md").write_text(manifest, encoding="utf-8")
print("    -> saved normalized_data/DATASET_MANIFEST.md")
print("\nDone. Next: run 00_normalize_dataset.py")
