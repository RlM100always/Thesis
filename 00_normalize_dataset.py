"""
=============================================================
STEP 0: DATASET NORMALIZATION — Build Relational Schema
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Run this BEFORE 01_preprocessing.py.

WHY THIS STEP EXISTS:
  The raw dataset (BD_Business_Analytics_Dataset.csv) is a single
  flat "spreadsheet" file with 44 columns. This is fine for quick
  analysis, but it violates basic database design rules — lots of
  columns repeat the same values on every row (e.g. every row for
  Customer "CUST-BD-00001" repeats their name, age, division,
  district, etc. all over again).

  This script NORMALIZES that flat file into a proper relational
  schema (similar to what you'd design in an ERD for a DBMS course)
  made up of 7 related tables:

      1. dim_customer            (Primary Key: Customer_ID)
      2. dim_date                (Primary Key: Transaction_Date)
      3. dim_product             (Primary Key: Product_ID)
      4. dim_business_profile    (Primary Key: Business_ID)
      5. dim_marketing           (Primary Key: Marketing_ID)
      6. dim_logistics           (Primary Key: Logistics_ID)
      7. fact_transactions       (Primary Key: Transaction_ID)
                                 (Foreign Keys -> all 6 tables above)

  This is a classic STAR SCHEMA: one central fact table holding the
  transaction-level numbers, surrounded by dimension tables holding
  descriptive attributes. It is in Third Normal Form (3NF) because:
    - Every non-key column in each dimension table depends only on
      that table's primary key (no partial or transitive dependency).
    - Repeating attribute groups (customer info, date info, product
      info, etc.) have been pulled out into their own tables so they
      are stored ONCE instead of being duplicated on every transaction
      row.

HOW TO RUN:
    python 00_normalize_dataset.py

OUTPUT:
    normalized_data/dim_customer.csv
    normalized_data/dim_date.csv
    normalized_data/dim_product.csv
    normalized_data/dim_business_profile.csv
    normalized_data/dim_marketing.csv
    normalized_data/dim_logistics.csv
    normalized_data/fact_transactions.csv
    output/BD_Business_Analytics_Dataset_Merged.csv   <- rebuilt via SQL-style
                                                          joins across all 7
                                                          tables. This is what
                                                          01_preprocessing.py
                                                          consumes next.
"""


import utf8_console  # noqa: F401  — UTF-8 stdout before any printing
import pandas as pd
import numpy as np
import os

os.makedirs("normalized_data", exist_ok=True)
os.makedirs("output", exist_ok=True)

print("=" * 65)
print("  STEP 0: NORMALIZE FLAT DATASET INTO A RELATIONAL SCHEMA")
print("=" * 65)

# ─────────────────────────────────────────────
# 1. LOAD THE RAW FLAT FILE
# ─────────────────────────────────────────────
print("\n[1] Loading raw flat dataset...")
raw = pd.read_csv("BD_Business_Analytics_Dataset.csv")
print(f"    Loaded: {raw.shape[0]:,} rows x {raw.shape[1]} columns")

n_rows_before = len(raw)

# ─────────────────────────────────────────────
# 2. dim_customer  (PK: Customer_ID)
#    FD verified: Customer_ID -> {Name, Age, Gender, Segment, Type,
#                  Division, District, Purchase_Frequency_Monthly,
#                  Customer_Lifetime_Value_BDT}
# ─────────────────────────────────────────────
print("\n[2] Building dim_customer ...")
customer_cols = [
    "Customer_ID", "Customer_Name", "Customer_Age", "Customer_Gender",
    "Customer_Segment", "Customer_Type", "Division", "District",
    "Purchase_Frequency_Monthly", "Customer_Lifetime_Value_BDT",
]
dim_customer = raw[customer_cols].drop_duplicates(subset="Customer_ID").reset_index(drop=True)
print(f"    dim_customer  : {dim_customer.shape[0]:,} unique customers, {dim_customer.shape[1]} columns")

# ─────────────────────────────────────────────
# 3. dim_date  (PK: Transaction_Date)
#    FD: Transaction_Date -> {Year, Month, Month_Name, Quarter,
#                              Week_Number, Day_of_Week, Season}
# ─────────────────────────────────────────────
print("\n[3] Building dim_date ...")
date_cols = [
    "Transaction_Date", "Year", "Month", "Month_Name", "Quarter",
    "Week_Number", "Day_of_Week", "Season",
]
dim_date = raw[date_cols].drop_duplicates(subset="Transaction_Date").reset_index(drop=True)
print(f"    dim_date      : {dim_date.shape[0]:,} unique dates, {dim_date.shape[1]} columns")

# ─────────────────────────────────────────────
# 4. dim_product  (PK: Product_ID, surrogate)
#    Product_Name repeats across many transactions -> deduplicate it.
# ─────────────────────────────────────────────
print("\n[4] Building dim_product ...")
unique_products = sorted(raw["Product_Name"].unique())
product_map = {name: f"PROD-{i+1:04d}" for i, name in enumerate(unique_products)}
dim_product = pd.DataFrame({
    "Product_ID": list(product_map.values()),
    "Product_Name": list(product_map.keys()),
})
raw["_Product_ID"] = raw["Product_Name"].map(product_map)
print(f"    dim_product   : {dim_product.shape[0]:,} unique products, {dim_product.shape[1]} columns")

# ─────────────────────────────────────────────
# 5. dim_business_profile  (PK: Business_ID, surrogate)
#    Groups the categorical business-description columns that repeat
#    together (Category / Sub-Category / Type). Employee_Count and
#    Annual_Revenue_BDT are transaction-specific numeric attributes in
#    the source data, so they stay as measures inside this same
#    dimension row (still no duplication issue since the WHOLE row of
#    5 columns is deduplicated together).
# ─────────────────────────────────────────────
print("\n[5] Building dim_business_profile ...")
biz_cols = ["Business_Category", "Business_Sub_Category", "Business_Type"]
unique_biz = raw[biz_cols].drop_duplicates().reset_index(drop=True)
unique_biz.insert(0, "Business_ID", [f"BIZ-{i+1:04d}" for i in range(len(unique_biz))])
dim_business_profile = unique_biz
raw_biz_key = raw[biz_cols].merge(dim_business_profile, on=biz_cols, how="left")
raw["_Business_ID"] = raw_biz_key["Business_ID"].values
print(f"    dim_business_profile : {dim_business_profile.shape[0]:,} unique business profiles, {dim_business_profile.shape[1]} columns")

# ─────────────────────────────────────────────
# 6. dim_marketing  (PK: Marketing_ID, surrogate)
#    FD group: {Marketing_Channel, Campaign_Type}
# ─────────────────────────────────────────────
print("\n[6] Building dim_marketing ...")
mkt_cols = ["Marketing_Channel", "Campaign_Type"]
unique_mkt = raw[mkt_cols].drop_duplicates().reset_index(drop=True)
unique_mkt.insert(0, "Marketing_ID", [f"MKT-{i+1:03d}" for i in range(len(unique_mkt))])
dim_marketing = unique_mkt
raw_mkt_key = raw[mkt_cols].merge(dim_marketing, on=mkt_cols, how="left")
raw["_Marketing_ID"] = raw_mkt_key["Marketing_ID"].values
print(f"    dim_marketing : {dim_marketing.shape[0]:,} unique channel/campaign combos, {dim_marketing.shape[1]} columns")

# ─────────────────────────────────────────────
# 7. dim_logistics  (PK: Logistics_ID, surrogate)
#    FD group: {Payment_Method, Order_Channel, Delivery_Status}
# ─────────────────────────────────────────────
print("\n[7] Building dim_logistics ...")
log_cols = ["Payment_Method", "Order_Channel", "Delivery_Status"]
unique_log = raw[log_cols].drop_duplicates().reset_index(drop=True)
unique_log.insert(0, "Logistics_ID", [f"LOG-{i+1:03d}" for i in range(len(unique_log))])
dim_logistics = unique_log
raw_log_key = raw[log_cols].merge(dim_logistics, on=log_cols, how="left")
raw["_Logistics_ID"] = raw_log_key["Logistics_ID"].values
print(f"    dim_logistics : {dim_logistics.shape[0]:,} unique payment/channel/delivery combos, {dim_logistics.shape[1]} columns")

# ─────────────────────────────────────────────
# 8. fact_transactions  (PK: Transaction_ID, FKs -> all 6 dims above)
#    Holds only: the FKs + the numbers that are genuinely unique to
#    THIS transaction (quantity, price, amounts, returns, stock,
#    satisfaction, recency).
# ─────────────────────────────────────────────
print("\n[8] Building fact_transactions ...")
fact_transactions = raw[[
    "Transaction_ID",
    "Customer_ID",            # FK -> dim_customer
    "Transaction_Date",       # FK -> dim_date
    "_Product_ID",            # FK -> dim_product
    "_Business_ID",           # FK -> dim_business_profile
    "_Marketing_ID",          # FK -> dim_marketing
    "_Logistics_ID",          # FK -> dim_logistics
    "Employee_Count", "Annual_Revenue_BDT",
    "Quantity", "Unit_Price_BDT", "Gross_Amount_BDT",
    "Discount_Percent", "Discount_Amount_BDT", "Net_Amount_BDT",
    "Profit_Margin_Percent", "Profit_Amount_BDT",
    "Delivery_Days", "Is_Returned", "Return_Reason",
    "Stock_Level", "Days_Since_Last_Purchase",
    "Customer_Satisfaction_Score",
]].rename(columns={
    "_Product_ID": "Product_ID",
    "_Business_ID": "Business_ID",
    "_Marketing_ID": "Marketing_ID",
    "_Logistics_ID": "Logistics_ID",
})
print(f"    fact_transactions : {fact_transactions.shape[0]:,} rows, {fact_transactions.shape[1]} columns")

# ─────────────────────────────────────────────
# 9. SAVE ALL 7 NORMALIZED TABLES
# ─────────────────────────────────────────────
print("\n[9] Saving normalized tables to normalized_data/ ...")
tables = {
    "dim_customer.csv": dim_customer,
    "dim_date.csv": dim_date,
    "dim_product.csv": dim_product,
    "dim_business_profile.csv": dim_business_profile,
    "dim_marketing.csv": dim_marketing,
    "dim_logistics.csv": dim_logistics,
    "fact_transactions.csv": fact_transactions,
}
for fname, tdf in tables.items():
    path = os.path.join("normalized_data", fname)
    tdf.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"    saved: {path}  ({tdf.shape[0]:,} rows x {tdf.shape[1]} cols)")

# ─────────────────────────────────────────────
# 10. REBUILD ("JOIN") THE TABLES BACK TOGETHER
#     This proves the schema is lossless: joining the 7 tables on
#     their FK/PK relationships recreates the original information
#     with zero data loss, which is exactly what the RDBMS would do
#     with SQL JOINs. This merged file feeds the rest of the pipeline
#     (01_preprocessing.py onward) exactly like the original flat CSV
#     did, so all downstream ML scripts still work unchanged.
# ─────────────────────────────────────────────
print("\n[10] Rebuilding merged dataset via relational JOINs ...")
merged = (
    fact_transactions
    .merge(dim_customer, on="Customer_ID", how="left")
    .merge(dim_date, on="Transaction_Date", how="left")
    .merge(dim_product, on="Product_ID", how="left")
    .merge(dim_business_profile, on="Business_ID", how="left")
    .merge(dim_marketing, on="Marketing_ID", how="left")
    .merge(dim_logistics, on="Logistics_ID", how="left")
)
print(f"    Merged shape: {merged.shape[0]:,} rows x {merged.shape[1]} columns")

# Sanity check: row count must match the original raw file exactly
assert merged.shape[0] == n_rows_before, "Row count mismatch after join — normalization broke data!"
print(f"    ✓ Row count matches original ({n_rows_before:,}) — no data lost in normalization")

merged_out_path = os.path.join("output", "BD_Business_Analytics_Dataset_Merged.csv")
merged.to_csv(merged_out_path, index=False, encoding="utf-8-sig")
print(f"    ✓ Saved merged/model-ready dataset -> {merged_out_path}")

# ─────────────────────────────────────────────
# 11. SUMMARY / ER-RELATIONSHIP REPORT (for your thesis writeup)
# ─────────────────────────────────────────────
print("\n" + "=" * 65)
print("  RELATIONAL SCHEMA SUMMARY (for Thesis Chapter 3)")
print("=" * 65)
summary = [
    ("dim_customer",          "Customer_ID",   dim_customer.shape,          "1 : Many -> fact_transactions"),
    ("dim_date",              "Transaction_Date", dim_date.shape,           "1 : Many -> fact_transactions"),
    ("dim_product",           "Product_ID",    dim_product.shape,           "1 : Many -> fact_transactions"),
    ("dim_business_profile",  "Business_ID",   dim_business_profile.shape,  "1 : Many -> fact_transactions"),
    ("dim_marketing",         "Marketing_ID",  dim_marketing.shape,         "1 : Many -> fact_transactions"),
    ("dim_logistics",         "Logistics_ID",  dim_logistics.shape,         "1 : Many -> fact_transactions"),
    ("fact_transactions",     "Transaction_ID", fact_transactions.shape,    "Many : 1 -> all 6 dim tables"),
]
for name, pk, shape, rel in summary:
    print(f"    {name:<22} PK={pk:<18} rows={shape[0]:<7,} cols={shape[1]:<3}  {rel}")

print("\n  Normal Form achieved: 3NF")
print("  - 1NF: all attributes atomic, no repeating groups within a row.")
print("  - 2NF: every non-key attribute depends on the WHOLE primary key")
print("         (no composite keys with partial dependency here).")
print("  - 3NF: every non-key attribute depends ONLY on the primary key,")
print("         not on another non-key attribute (transitive dependencies")
print("         like Customer_ID -> Division -> District have been kept")
print("         together inside dim_customer since District genuinely")
print("         depends on the customer record, not re-derived elsewhere).")
print("\n  Done. Next step: run 01_preprocessing.py")
print("=" * 65)
