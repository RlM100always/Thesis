"""
=============================================================
STEP 1b: CUSTOMER-LEVEL FEATURES & LEAK-FREE SPLIT
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Run this AFTER 01_preprocessing.py.

WHY THIS SCRIPT EXISTS
----------------------
01_preprocessing.py splits at the TRANSACTION level (32,000 rows), but
Segment_Label is a CUSTOMER-level attribute — every one of a customer's
~6.4 transactions carries the same label. A plain train_test_split
therefore puts the same customer in train AND test:

    98.8% of test customers were also in the training set.

The model does not learn to generalise; it memorises a customer it has
already seen and recalls the label. This script fixes that by making the
CUSTOMER the unit of prediction: one row per customer, so a customer is
in exactly one split. Group leakage becomes impossible by construction.

It also fixes two other leaks:
  - Scaler is fit on TRAIN ONLY (01_preprocessing fits on the full data).
  - Customer_Lifetime_Value_BDT is EXCLUDED by default, because the
    segments sit in near-disjoint CLV bands (a depth-3 tree on CLV alone
    scores 91%). Set INCLUDE_CLV = True to reproduce the leaky variant
    for the comparison table in the thesis.

HOW TO RUN:
    PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 01b_customer_features.py

OUTPUT:
    output/customer_features.csv   — one row per customer
    output/customer_splits.pkl     — leak-free train/val/test arrays
"""

import os
import pickle

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

# ─────────────────────────────────────────────
# CONFIG — flip this to produce the leaky variant for comparison
# ─────────────────────────────────────────────
INCLUDE_CLV = os.environ.get("INCLUDE_CLV", "0") == "1"
# False = honest model | True = reproduces the CLV leak, for the ablation table.
# Override without editing:  INCLUDE_CLV=1 python 01b_customer_features.py

os.makedirs("output", exist_ok=True)

print("=" * 60)
print("  STEP 1b: CUSTOMER-LEVEL FEATURES (LEAK-FREE)")
print("=" * 60)
print(f"    INCLUDE_CLV = {INCLUDE_CLV}"
      f"{'  ← leaky variant, for comparison only' if INCLUDE_CLV else '  ← honest variant'}")

# ─────────────────────────────────────────────
# 1. LOAD TRANSACTION-LEVEL DATA
# ─────────────────────────────────────────────
print("\n[1] Loading processed transaction data...")
df = pd.read_csv("output/processed_dataset.csv")
df["Transaction_Date"] = pd.to_datetime(df["Transaction_Date"])
print(f"    Transactions : {len(df):,}")
print(f"    Customers    : {df['Customer_ID'].nunique():,}")
print(f"    Rows/customer: {len(df) / df['Customer_ID'].nunique():.2f}")

# Sanity check: the target must be constant within a customer, otherwise
# aggregating to customer level would be ill-defined.
per_cust_labels = df.groupby("Customer_ID")["Segment_Label"].nunique()
assert per_cust_labels.max() == 1, (
    "Segment_Label varies within a customer — customer-level aggregation invalid"
)
print("    ✓ Segment_Label is constant within each customer")

# ─────────────────────────────────────────────
# 2. AGGREGATE TO CUSTOMER LEVEL
# ─────────────────────────────────────────────
# Same groupby pattern as 03_clustering.py, extended with behavioural,
# seasonal and channel-diversity features.
print("\n[2] Aggregating transactions to one row per customer...")

cust = df.groupby("Customer_ID").agg(
    # ── RFM core
    Recency          = ("Days_Since_Last_Purchase", "min"),
    Frequency        = ("Purchase_Frequency_Monthly", "mean"),
    Monetary         = ("Net_Amount_BDT", "sum"),
    Txn_Count        = ("Transaction_ID", "count"),
    # ── Spending behaviour
    Avg_Order_Value  = ("Net_Amount_BDT", "mean"),
    Std_Order_Value  = ("Net_Amount_BDT", "std"),
    Max_Order_Value  = ("Net_Amount_BDT", "max"),
    Total_Quantity   = ("Quantity", "sum"),
    Avg_Unit_Price   = ("Unit_Price_BDT", "mean"),
    # ── Profitability
    Total_Profit     = ("Profit_Amount_BDT", "sum"),
    Avg_Margin       = ("Profit_Margin_Percent", "mean"),
    # ── Discount sensitivity
    Avg_Discount     = ("Discount_Percent", "mean"),
    High_Disc_Rate   = ("High_Discount_Flag", "mean"),
    # ── Service experience
    Avg_CSAT         = ("Customer_Satisfaction_Score", "mean"),
    Avg_Delivery_Days= ("Delivery_Days", "mean"),
    Return_Rate      = ("Return_Binary", "mean"),
    # ── Seasonality of this customer's buying
    Eid_Share        = ("Is_Eid_Season", "mean"),
    Ramadan_Share    = ("Is_Ramadan", "mean"),
    Boishakh_Share   = ("Is_Pohela_Boishakh", "mean"),
    YearEnd_Share    = ("Is_YearEnd_Sale", "mean"),
    Weekend_Share    = ("Is_Weekend", "mean"),
    # ── Demographics (constant per customer)
    Customer_Age     = ("Customer_Age", "first"),
    Gender_Enc       = ("Customer_Gender_Enc", "first"),
    Division_Enc     = ("Division_Enc", "first"),
    Cust_Type_Enc    = ("Customer_Type_Enc", "first"),
    # ── Business context
    Employee_Count   = ("Employee_Count", "mean"),
    Revenue_Per_Emp  = ("Revenue_Per_Employee", "mean"),
    # ── Engineered score carried up
    RFM_Score        = ("RFM_Score", "mean"),
    # ── Target
    Segment_Label    = ("Segment_Label", "first"),
    # ── Kept for reference / the leaky variant, never a feature by default
    CLV              = ("Customer_Lifetime_Value_BDT", "first"),
).reset_index()

# Std is NaN for customers with a single transaction — 0 variance is the
# correct reading, not a missing value.
cust["Std_Order_Value"] = cust["Std_Order_Value"].fillna(0.0)

# ── Channel / category diversity: how broad is this customer's basket?
print("    Computing diversity features...")
diversity = df.groupby("Customer_ID").agg(
    N_Categories     = ("Business_Category", "nunique"),
    N_Payment_Methods= ("Payment_Method", "nunique"),
    N_Channels       = ("Order_Channel", "nunique"),
    N_Products       = ("Product_Name", "nunique"),
).reset_index()
cust = cust.merge(diversity, on="Customer_ID", how="left")

# ── Tenure: how long has this customer been active?
print("    Computing tenure features...")
tenure = df.groupby("Customer_ID")["Transaction_Date"].agg(["min", "max"]).reset_index()
tenure["Tenure_Days"] = (tenure["max"] - tenure["min"]).dt.days
cust = cust.merge(tenure[["Customer_ID", "Tenure_Days"]], on="Customer_ID", how="left")
# Purchases per active month — a rate, not a raw count
cust["Purchase_Rate"] = cust["Txn_Count"] / ((cust["Tenure_Days"] / 30.0) + 1.0)

print(f"    ✓ Customer table: {cust.shape[0]:,} rows × {cust.shape[1]} columns")

# ─────────────────────────────────────────────
# 3. FEATURE SELECTION
# ─────────────────────────────────────────────
print("\n[3] Selecting features...")

FEATURES = [
    "Recency", "Frequency", "Monetary", "Txn_Count",
    "Avg_Order_Value", "Std_Order_Value", "Max_Order_Value",
    "Total_Quantity", "Avg_Unit_Price",
    "Total_Profit", "Avg_Margin",
    "Avg_Discount", "High_Disc_Rate",
    "Avg_CSAT", "Avg_Delivery_Days", "Return_Rate",
    "Eid_Share", "Ramadan_Share", "Boishakh_Share",
    "YearEnd_Share", "Weekend_Share",
    "Customer_Age", "Gender_Enc", "Division_Enc", "Cust_Type_Enc",
    "Employee_Count", "Revenue_Per_Emp", "RFM_Score",
    "N_Categories", "N_Payment_Methods", "N_Channels", "N_Products",
    "Tenure_Days", "Purchase_Rate",
]

if INCLUDE_CLV:
    FEATURES = FEATURES + ["CLV"]
    print("    ⚠ CLV INCLUDED — this reproduces the leaked result on purpose")
else:
    print("    ✓ CLV excluded (it nearly determines the label)")

print(f"    Total features: {len(FEATURES)}")

X = cust[FEATURES].values
y = cust["Segment_Label"].values
customer_ids = cust["Customer_ID"].values

# ─────────────────────────────────────────────
# 4. SPLIT — one customer lives in exactly one split
# ─────────────────────────────────────────────
print("\n[4] Splitting 70/15/15 (stratified by segment)...")

idx = np.arange(len(cust))
idx_train, idx_temp = train_test_split(
    idx, test_size=0.30, random_state=42, stratify=y
)
idx_val, idx_test = train_test_split(
    idx_temp, test_size=0.50, random_state=42, stratify=y[idx_temp]
)

print(f"    Train: {len(idx_train):,} customers")
print(f"    Val  : {len(idx_val):,} customers")
print(f"    Test : {len(idx_test):,} customers")

# Prove the leak is gone — this is the whole point of the script
train_ids = set(customer_ids[idx_train])
val_ids   = set(customer_ids[idx_val])
test_ids  = set(customer_ids[idx_test])
overlap_tt = train_ids & test_ids
overlap_tv = train_ids & val_ids
print(f"\n    Customer overlap train∩test: {len(overlap_tt)}")
print(f"    Customer overlap train∩val : {len(overlap_tv)}")
assert not overlap_tt and not overlap_tv, "Group leakage still present"
print("    ✓ NO GROUP LEAKAGE (was 98.8% overlap at transaction level)")

# ─────────────────────────────────────────────
# 5. SCALING — fit on TRAIN ONLY
# ─────────────────────────────────────────────
# 01_preprocessing.py fits the scaler on the whole dataset before splitting,
# which lets test-set min/max bleed into training. Here the scaler never
# sees validation or test rows.
print("\n[5] Scaling (MinMaxScaler fit on TRAIN only)...")

scaler = MinMaxScaler()
X_train = scaler.fit_transform(X[idx_train])
X_val   = scaler.transform(X[idx_val])
X_test  = scaler.transform(X[idx_test])
print("    ✓ Scaler fit on train only, applied to val/test")

# ─────────────────────────────────────────────
# 6. SAVE
# ─────────────────────────────────────────────
print("\n[6] Saving...")

splits = {
    "X_train": X_train, "X_val": X_val, "X_test": X_test,
    "y_train": y[idx_train], "y_val": y[idx_val], "y_test": y[idx_test],
    "ids_train": customer_ids[idx_train],
    "ids_val":   customer_ids[idx_val],
    "ids_test":  customer_ids[idx_test],
    "feature_names": FEATURES,
    "include_clv": INCLUDE_CLV,
    # Unscaled full matrix + labels, so cross-validation can rescale per fold
    "X_all_raw": X, "y_all": y, "ids_all": customer_ids,
    "scaler": scaler,
}
with open("output/customer_splits.pkl", "wb") as f:
    pickle.dump(splits, f)
print("    → Saved: output/customer_splits.pkl")

cust.to_csv("output/customer_features.csv", index=False)
print("    → Saved: output/customer_features.csv")

# ─────────────────────────────────────────────
# 7. CLASS BALANCE
# ─────────────────────────────────────────────
CLASS_NAMES = ["Low-Engagement", "Moderate-Spender", "High-Value", "VIP-Platinum"]
print("\n[7] Class distribution (customer level):")
for split_name, yy in [("Train", y[idx_train]), ("Val", y[idx_val]), ("Test", y[idx_test])]:
    counts = np.bincount(yy, minlength=4)
    parts = " | ".join(
        f"{CLASS_NAMES[i][:12]}: {counts[i]:4d} ({counts[i] / len(yy) * 100:4.1f}%)"
        for i in range(4)
    )
    print(f"    {split_name:5s} {parts}")

print("\n" + "=" * 60)
print("  ✅ CUSTOMER-LEVEL FEATURES COMPLETE")
print("  Next: python 02_classification.py")
print("=" * 60)
