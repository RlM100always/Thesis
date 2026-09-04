"""Rewrite Annual_Revenue_BDT with realistic Bangladeshi values.

The original column was uniform random over [1 lakh, 100 crore] with no
relationship to Employee_Count -- a 21-person SME with 95 crore revenue.
This anchors revenue to headcount via revenue-per-employee figures typical
of Bangladeshi firms, with lognormal spread and a per-sector multiplier.

Annual_Revenue_BDT is a business (Business_Type + Business_Category) attribute,
so every row of the same business gets the same value.

Run from the repo root. Backs up the original CSV first.
"""

import shutil

import numpy as np
import pandas as pd

import utf8_console  # noqa: F401

CSV = "BD_Business_Analytics_Dataset.csv"
BACKUP = "BD_Business_Analytics_Dataset_ORIGINAL_revenue_backup.csv"

# Annual revenue per employee, BDT. Startups and social enterprises run lean;
# MNCs (Grameenghone, Unilever BD) are an order of magnitude more productive.
REV_PER_EMPLOYEE = {
    "Startup": 800_000,
    "Social Enterprise": 1_000_000,
    "SME": 1_500_000,
    "Large Enterprise": 2_500_000,
    "MNC": 4_500_000,
}

# Capital-intensive sectors turn more revenue per head than labour-intensive ones.
CATEGORY_MULTIPLIER = {
    "Real Estate": 2.2,
    "Banking & Finance": 2.0,
    "Telecom": 1.8,
    "Electronics": 1.3,
    "IT Services": 1.2,
    "E-Commerce": 1.1,
    "Healthcare": 1.0,
    "Retail": 1.0,
    "Transportation": 1.0,
    "Food & Beverage": 0.9,
    "Fashion & Apparel": 0.9,
    "Garments & RMG": 0.8,
    "Agriculture": 0.6,
    "Education": 0.6,
}

# Lognormal sigma -- firms of the same size and sector still vary a lot.
SIGMA = 0.35


def main():
    rng = np.random.default_rng(42)

    shutil.copy(CSV, BACKUP)
    print(f"→ backed up original to {BACKUP}")

    df = pd.read_csv(CSV)
    old = df["Annual_Revenue_BDT"].copy()

    rate = df["Business_Type"].map(REV_PER_EMPLOYEE)
    mult = df["Business_Category"].map(CATEGORY_MULTIPLIER)
    if rate.isna().any() or mult.isna().any():
        raise SystemExit("⚠ unmapped Business_Type or Business_Category -- check the dicts")

    base = df["Employee_Count"] * rate * mult

    # One draw per business, not per transaction, so a firm's revenue is stable.
    key = df["Business_Type"] + "|" + df["Business_Category"] + "|" + df["Employee_Count"].astype(str)
    codes = pd.factorize(key)[0]
    noise = rng.lognormal(mean=0.0, sigma=SIGMA, size=codes.max() + 1)[codes]

    df["Annual_Revenue_BDT"] = (base * noise).round(2)

    df.to_csv(CSV, index=False, encoding="utf-8-sig")

    print("\n  Annual_Revenue_BDT by Business_Type (crore BDT, median):")
    cmp = pd.DataFrame({"old": old, "new": df["Annual_Revenue_BDT"], "type": df["Business_Type"]})
    print((cmp.groupby("type")[["old", "new"]].median() / 1e7).round(2).to_string())
    print(f"\n✓ rewrote {CSV}")


if __name__ == "__main__":
    main()
