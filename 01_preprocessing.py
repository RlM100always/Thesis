"""
=============================================================
STEP 1: DATA LOADING & PREPROCESSING
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Run this FIRST before any other script.
Output: preprocessed dataset saved as CSV + encoded arrays

HOW TO RUN:
    python 01_preprocessing.py

WHAT THIS DOES:
  - Loads the 32,000-record Bangladeshi business dataset
  - Handles missing/null values
  - Encodes categorical columns
  - Creates new ML features (RFM, Seasonal flags, CLV Tier)
  - Normalizes numerical columns
  - Splits into Train / Validation / Test sets
  - Saves all processed data for the next steps
"""

import pandas as pd
import numpy as np
import os
import pickle
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.model_selection import train_test_split

# ── Output folder for all processed files
os.makedirs("output", exist_ok=True)

print("=" * 60)
print("  STEP 1: DATA PREPROCESSING")
print("=" * 60)

# ─────────────────────────────────────────────
# 1. LOAD DATASET
# ─────────────────────────────────────────────
print("\n[1] Loading dataset...")
merged_path = os.path.join("output", "BD_Business_Analytics_Dataset_Merged.csv")
if os.path.exists(merged_path):
    df = pd.read_csv(merged_path)
    print(f"    Loaded NORMALIZED + REJOINED dataset from: {merged_path}")
    print("    (produced by 00_normalize_dataset.py from the 7 relational tables)")
else:
    df = pd.read_csv("BD_Business_Analytics_Dataset.csv")
    print("    ⚠ Normalized dataset not found — loaded raw flat CSV instead.")
    print("    ⚠ Run 00_normalize_dataset.py first for the relational pipeline.")
print(f"    Loaded: {df.shape[0]:,} rows × {df.shape[1]} columns")
print(f"    Columns: {list(df.columns)}")

# ─────────────────────────────────────────────
# 2. MISSING VALUE ANALYSIS
# ─────────────────────────────────────────────
print("\n[2] Missing Value Analysis:")
missing = df.isnull().sum()
missing_pct = (missing / len(df) * 100).round(2)
for col in df.columns:
    if missing[col] > 0:
        print(f"    ⚠ {col}: {missing[col]} missing ({missing_pct[col]}%)")
    
# Return_Reason is empty for non-returned items — this is by design, fill with 'No Return'
df["Return_Reason"] = df["Return_Reason"].fillna("No Return").replace("", "No Return")
print("    ✓ Return_Reason: filled empty values with 'No Return'")
print("    ✓ No other critical missing values found")

# ─────────────────────────────────────────────
# 3. FEATURE ENGINEERING
# ─────────────────────────────────────────────
print("\n[3] Feature Engineering...")

# 3a. RFM Score (Recency, Frequency, Monetary)
# Recency: lower days_since_last = better = lower score
df["Recency_Score"]   = pd.qcut(df["Days_Since_Last_Purchase"], q=4, labels=[4, 3, 2, 1]).astype(int)
df["Frequency_Score"] = pd.qcut(df["Purchase_Frequency_Monthly"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
df["Monetary_Score"]  = pd.qcut(df["Net_Amount_BDT"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
df["RFM_Score"]       = df["Recency_Score"] + df["Frequency_Score"] + df["Monetary_Score"]
print("    ✓ RFM Score created (Recency + Frequency + Monetary)")

# 3b. CLV Tier (4 bins)
df["CLV_Tier"] = pd.qcut(df["Customer_Lifetime_Value_BDT"], q=4, labels=["Bronze", "Silver", "Gold", "Platinum"])
print("    ✓ CLV_Tier created: Bronze / Silver / Gold / Platinum")

# 3c. Seasonal Flags (binary)
df["Is_Eid_Season"]       = df["Season"].str.contains("Eid").astype(int)
df["Is_Ramadan"]          = df["Season"].str.contains("Ramadan").astype(int)
df["Is_Pohela_Boishakh"]  = df["Season"].str.contains("Pohela").astype(int)
df["Is_YearEnd_Sale"]     = df["Season"].str.contains("Year-End").astype(int)
print("    ✓ Seasonal binary flags created (Eid, Ramadan, Pohela Boishakh, Year-End)")

# 3d. Is_Weekend flag
df["Is_Weekend"] = df["Day_of_Week"].isin(["Friday", "Saturday"]).astype(int)
print("    ✓ Is_Weekend flag created")

# 3e. Revenue per Employee (business efficiency proxy)
df["Revenue_Per_Employee"] = df["Annual_Revenue_BDT"] / df["Employee_Count"].replace(0, 1)
print("    ✓ Revenue_Per_Employee computed")

# 3f. Discount Impact Flag
df["High_Discount_Flag"] = (df["Discount_Percent"] > 20).astype(int)
print("    ✓ High_Discount_Flag created (>20%)")

# 3g. Net Profit Ratio
df["Net_Profit_Ratio"] = df["Profit_Amount_BDT"] / df["Net_Amount_BDT"].replace(0, 1)
print("    ✓ Net_Profit_Ratio computed")

# 3h. Target variable for classification: Customer_Segment → numeric
SEGMENT_MAP = {
    "Low-Engagement": 0,
    "Moderate-Spender": 1,
    "High-Value": 2,
    "VIP-Platinum": 3,
}
df["Segment_Label"] = df["Customer_Segment"].map(SEGMENT_MAP)
print("    ✓ Target: Segment_Label created (0=Low, 1=Moderate, 2=High, 3=VIP)")

# 3i. Return target (binary classification)
df["Return_Binary"] = (df["Is_Returned"] == "Yes").astype(int)
print("    ✓ Return_Binary target created")

# ─────────────────────────────────────────────
# 4. ENCODING CATEGORICAL COLUMNS
# ─────────────────────────────────────────────
print("\n[4] Encoding Categorical Variables...")

LABEL_ENCODE_COLS = [
    "Business_Category", "Business_Type", "Payment_Method",
    "Order_Channel", "Marketing_Channel", "Campaign_Type",
    "Division", "Delivery_Status", "Season", "CLV_Tier",
    "Customer_Gender", "Customer_Type", "Stock_Level", "Day_of_Week",
]

label_encoders = {}
for col in LABEL_ENCODE_COLS:
    le = LabelEncoder()
    df[col + "_Enc"] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le
    print(f"    ✓ Label-Encoded: {col} ({len(le.classes_)} classes)")

# Save encoders
with open("output/label_encoders.pkl", "wb") as f:
    pickle.dump(label_encoders, f)
print("    → Saved: output/label_encoders.pkl")

# ─────────────────────────────────────────────
# 5. SELECT FEATURES FOR ML
# ─────────────────────────────────────────────
print("\n[5] Selecting ML Feature Set...")

NUMERIC_FEATURES = [
    "Customer_Age", "Employee_Count", "Annual_Revenue_BDT",
    "Quantity", "Unit_Price_BDT", "Gross_Amount_BDT",
    "Discount_Percent", "Discount_Amount_BDT", "Net_Amount_BDT",
    "Profit_Margin_Percent", "Profit_Amount_BDT",
    "Delivery_Days", "Purchase_Frequency_Monthly",
    "Days_Since_Last_Purchase", "Customer_Lifetime_Value_BDT",
    "Customer_Satisfaction_Score", "RFM_Score",
    "Recency_Score", "Frequency_Score", "Monetary_Score",
    "Is_Eid_Season", "Is_Ramadan", "Is_Pohela_Boishakh",
    "Is_YearEnd_Sale", "Is_Weekend", "High_Discount_Flag",
    "Revenue_Per_Employee", "Net_Profit_Ratio",
]

ENCODED_FEATURES = [col + "_Enc" for col in LABEL_ENCODE_COLS]

ALL_FEATURES = NUMERIC_FEATURES + ENCODED_FEATURES
TARGET_SEGMENT = "Segment_Label"
TARGET_RETURN  = "Return_Binary"

print(f"    → Total features selected: {len(ALL_FEATURES)}")

# ─────────────────────────────────────────────
# 6. NORMALIZATION
# ─────────────────────────────────────────────
print("\n[6] Normalizing Numeric Features (MinMaxScaler)...")

scaler = MinMaxScaler()
df_ml = df[ALL_FEATURES].copy()
df_ml[NUMERIC_FEATURES] = scaler.fit_transform(df[NUMERIC_FEATURES])

with open("output/scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)
print("    → Saved: output/scaler.pkl")

# ─────────────────────────────────────────────
# 7. TRAIN / VALIDATION / TEST SPLIT
# ─────────────────────────────────────────────
print("\n[7] Splitting Dataset (70% Train / 15% Val / 15% Test)...")

X = df_ml[ALL_FEATURES].values
y_seg = df[TARGET_SEGMENT].values
y_ret = df[TARGET_RETURN].values

# First split: 70% train, 30% temp
X_train, X_temp, y_seg_train, y_seg_temp, y_ret_train, y_ret_temp = train_test_split(
    X, y_seg, y_ret, test_size=0.30, random_state=42, stratify=y_seg
)
# Second split: 15% val, 15% test from the 30% temp
X_val, X_test, y_seg_val, y_seg_test, y_ret_val, y_ret_test = train_test_split(
    X_temp, y_seg_temp, y_ret_temp, test_size=0.50, random_state=42, stratify=y_seg_temp
)

print(f"    Train set : {X_train.shape[0]:,} records ({X_train.shape[0]/len(X)*100:.0f}%)")
print(f"    Val set   : {X_val.shape[0]:,} records ({X_val.shape[0]/len(X)*100:.0f}%)")
print(f"    Test set  : {X_test.shape[0]:,} records ({X_test.shape[0]/len(X)*100:.0f}%)")

# Save splits
splits = {
    "X_train": X_train, "X_val": X_val, "X_test": X_test,
    "y_seg_train": y_seg_train, "y_seg_val": y_seg_val, "y_seg_test": y_seg_test,
    "y_ret_train": y_ret_train, "y_ret_val": y_ret_val, "y_ret_test": y_ret_test,
    "feature_names": ALL_FEATURES,
}
with open("output/data_splits.pkl", "wb") as f:
    pickle.dump(splits, f)
print("    → Saved: output/data_splits.pkl")

# Save processed full df for clustering
df.to_csv("output/processed_dataset.csv", index=False)
print("    → Saved: output/processed_dataset.csv")

print("\n" + "=" * 60)
print("  ✅ PREPROCESSING COMPLETE")
print("  Next: Run  python 02_classification.py")
print("=" * 60)
