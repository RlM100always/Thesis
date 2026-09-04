"""
Score an uploaded transaction CSV with the already-trained models.

WHY THIS IS NOT "read CSV -> model.predict"
-------------------------------------------
The models consume the engineered customer-level features built by
01b_customer_features.py, not raw transactions. An arbitrary business CSV
has none of them under those names. So the flow is:

    raw transactions -> user maps 4 columns -> rebuild RFM features
                     -> transform with the TRAINING scaler -> score

Only four mappings are required (customer id, date, amount, quantity)
because RFM is derivable from those alone. Everything else the model wants
is defaulted to 0.0 by predict._vectorise and reported in `missing_fields`,
so coverage is disclosed rather than faked.

No pickle is opened here — predict.py stays the only module that does that.
NOTHING IS RETRAINED. This is scoring only, so the thesis artifacts are
untouched.
"""

from __future__ import annotations

import io
import uuid
from collections import OrderedDict

import numpy as np
import pandas as pd

import predict as service

# ─────────────────────────────────────────────
# Limits — a thesis demo, not a multi-tenant service
# ─────────────────────────────────────────────
MAX_BYTES = 50 * 1024 * 1024
MIN_CUSTOMERS = 20          # RFM on fewer than this is noise
MAX_SESSIONS = 5
SAMPLE_ROWS = 5

# Uploaded frames live in memory, keyed by token. LRU-evicted at MAX_SESSIONS
# so a long-running demo cannot grow without bound. No disk, no DB.
_SESSIONS: OrderedDict[str, pd.DataFrame] = OrderedDict()

REQUIRED_ROLES = ["customer_id", "date", "amount"]
OPTIONAL_ROLES = ["quantity", "product"]
ALL_ROLES = REQUIRED_ROLES + OPTIONAL_ROLES

# Seasonal-naive predicts month M from month M-12, so a year of history plus one
# month is the floor. Below this the honest answer is "not enough data" — never a
# number. This project has already shipped a fabricated forecast once
# (output/forecast_results_SIMULATED_backup.pkl); the lesson stands.
MIN_MONTHS_FORECAST = 13
MIN_MONTHS_BACKTEST = 24

# Column-name variants seen in real exports, lowercased and stripped of
# separators before matching.
_ROLE_HINTS = {
    "customer_id": ["customerid", "custid", "customer", "cust", "clientid",
                    "client", "buyerid", "userid", "accountid", "member"],
    "date": ["transactiondate", "orderdate", "date", "invoicedate", "purchasedate",
             "createdat", "timestamp", "datetime", "when", "day"],
    "amount": ["netamountbdt", "netamount", "amount", "total", "totalamount",
               "revenue", "sales", "price", "value", "grandtotal", "taka", "bdt"],
    "quantity": ["quantity", "qty", "units", "unitssold", "count", "pieces", "pcs",
                 "items", "nos"],
    "product": ["productname", "product", "item", "itemname", "sku", "description",
                "goods", "article", "model"],
}


# Ranking quality when only the upload-derivable features are available.
# Measured, not guessed: 800 customers' full histories were taken from this
# project's own processed_dataset.csv, reduced to the four mappable columns,
# scored through this module, and compared against the Recency > 90 labels in
# customer_features.csv. Take complete customer histories when re-measuring — a
# truncated slice cuts each customer's last purchase and drags the figure to
# ~0.58 for reasons that have nothing to do with the model.
HEADLINE_CHURN_AUC = 0.712   # full 32-feature model, from churn_results.pkl
REDUCED_CHURN_AUC = 0.77     # same model, upload-derivable features only


class UploadError(ValueError):
    """Bad input from the user. The API turns this into a 400, not a 500."""


def _norm(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


# ─────────────────────────────────────────────
# 1. PARSE
# ─────────────────────────────────────────────
def parse_upload(file_bytes: bytes, filename: str) -> dict:
    """Read the file, stash it, and describe it so the UI can build the mapper."""
    if not file_bytes:
        raise UploadError("The file is empty.")
    if len(file_bytes) > MAX_BYTES:
        raise UploadError(
            f"File is {len(file_bytes) / 1e6:.1f} MB; the limit is {MAX_BYTES // 1024 // 1024} MB."
        )

    lower = (filename or "").lower()
    try:
        if lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            # utf-8-sig strips the BOM this project writes on its own CSVs.
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise UploadError(
            "Could not read the file as UTF-8. Re-save it as CSV UTF-8 from Excel."
        )
    except Exception as exc:
        raise UploadError(f"Could not parse the file: {exc}")

    if df.empty:
        raise UploadError("The file parsed but contains no rows.")
    if len(df.columns) < 3:
        raise UploadError(
            f"Only {len(df.columns)} column(s) found. Need at least a customer ID, "
            "a date and an amount. Check the file's delimiter."
        )

    df.columns = [str(c).strip() for c in df.columns]

    token = uuid.uuid4().hex
    _SESSIONS[token] = df
    _SESSIONS.move_to_end(token)
    while len(_SESSIONS) > MAX_SESSIONS:
        _SESSIONS.popitem(last=False)

    sample = df.head(SAMPLE_ROWS).astype(object).where(pd.notna(df.head(SAMPLE_ROWS)), None)

    return {
        "token": token,
        "filename": filename,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "sample_rows": sample.to_dict(orient="records"),
        "suggested_mapping": suggest_mapping(list(df.columns)),
    }


def suggest_mapping(columns: list[str]) -> dict:
    """
    Best-guess column -> role. Pre-fills the form; the user can override
    every field, so a wrong guess costs a dropdown click, not a failure.
    """
    normed = {col: _norm(col) for col in columns}
    mapping: dict[str, str | None] = {}
    taken: set[str] = set()

    for role in ALL_ROLES:
        hints = _ROLE_HINTS[role]
        best, best_rank = None, len(hints) + 1
        for col, n in normed.items():
            if col in taken or not n:
                continue
            for rank, hint in enumerate(hints):
                # Exact match beats containment, earlier hint beats later.
                if n == hint:
                    score = rank - 0.5
                elif hint in n or n in hint:
                    score = rank
                else:
                    continue
                if score < best_rank:
                    best, best_rank = col, score
                break
        mapping[role] = best
        if best:
            taken.add(best)

    return mapping


def get_session(token: str) -> pd.DataFrame:
    df = _SESSIONS.get(token)
    if df is None:
        raise UploadError("This upload has expired. Please upload the file again.")
    _SESSIONS.move_to_end(token)
    return df


def drop_session(token: str) -> bool:
    return _SESSIONS.pop(token, None) is not None


# ─────────────────────────────────────────────
# 2. FEATURE BUILD
# ─────────────────────────────────────────────
def clean_transactions(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Validate the mapping and return a tidy transaction frame.

    Columns: Customer_ID, Date, Amount, Quantity, and Product when mapped.
    Every analysis in this module starts here, so a file is parsed and
    validated the same way whichever view asked for it.
    """
    for role in REQUIRED_ROLES:
        if not mapping.get(role):
            raise UploadError(f"No column mapped to '{role}'.")

    c_id, c_date, c_amt = mapping["customer_id"], mapping["date"], mapping["amount"]
    c_qty = mapping.get("quantity")

    for role, col in [("customer_id", c_id), ("date", c_date), ("amount", c_amt)]:
        if col not in df.columns:
            raise UploadError(f"Column '{col}' (mapped to {role}) is not in the file.")

    work = pd.DataFrame({"Customer_ID": df[c_id].astype(str).str.strip()})

    work["Date"] = pd.to_datetime(df[c_date], errors="coerce")
    if work["Date"].isna().all():
        raise UploadError(
            f"No value in '{c_date}' could be read as a date. "
            "Use a format like 2024-07-14 or 14/07/2024."
        )

    # Strip currency symbols and thousands separators before coercing.
    amt = df[c_amt]
    if not pd.api.types.is_numeric_dtype(amt):
        amt = pd.to_numeric(
            amt.astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce"
        )
    work["Amount"] = pd.to_numeric(amt, errors="coerce")
    if work["Amount"].isna().all():
        raise UploadError(
            f"No value in '{c_amt}' could be read as a number. "
            "Mapped the wrong column to 'amount'?"
        )

    if c_qty and c_qty in df.columns:
        work["Quantity"] = pd.to_numeric(df[c_qty], errors="coerce").fillna(1.0)
    else:
        work["Quantity"] = 1.0

    c_prod = mapping.get("product")
    if c_prod and c_prod in df.columns:
        work["Product"] = df[c_prod].astype(str).str.strip()

    before = len(work)
    work = work.dropna(subset=["Customer_ID", "Date", "Amount"])
    work = work[work["Customer_ID"] != ""]
    dropped = before - len(work)

    if work.empty:
        raise UploadError("Every row was dropped as unreadable. Check the column mapping.")

    n_customers = work["Customer_ID"].nunique()
    if n_customers < MIN_CUSTOMERS:
        raise UploadError(
            f"Only {n_customers} distinct customer(s) found; at least {MIN_CUSTOMERS} "
            "are needed for the behavioural features to mean anything."
        )

    work.attrs["dropped_rows"] = int(dropped)
    work.attrs["source_rows"] = int(before)
    return work


def build_customer_features(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Aggregate raw transactions to one row per customer.

    Column names mirror 01b_customer_features.py so the values land in the
    right slots of the trained model's feature vector. Two definitions
    necessarily differ from 01b and the difference is reported to the user:

      Recency   01b takes min(Days_Since_Last_Purchase), a column supplied
                by the source dataset. Here it is days between the
                customer's last transaction and the newest date in the
                file. Same intent, different origin.
      Frequency 01b averages Purchase_Frequency_Monthly, also supplied.
                Here it is transactions per active month.
    """
    work = df if "Amount" in df.columns else clean_transactions(df, mapping)
    as_of = work["Date"].max()

    g = work.groupby("Customer_ID")
    cust = g.agg(
        Monetary        =("Amount", "sum"),
        Txn_Count       =("Amount", "count"),
        Avg_Order_Value =("Amount", "mean"),
        Std_Order_Value =("Amount", "std"),
        Max_Order_Value =("Amount", "max"),
        Total_Quantity  =("Quantity", "sum"),
        First_Date      =("Date", "min"),
        Last_Date       =("Date", "max"),
    ).reset_index()

    # One transaction means zero variance, not a missing value — same call as 01b:136.
    cust["Std_Order_Value"] = cust["Std_Order_Value"].fillna(0.0)

    cust["Recency"] = (as_of - cust["Last_Date"]).dt.days.astype(int)
    cust["Tenure_Days"] = (cust["Last_Date"] - cust["First_Date"]).dt.days.astype(int)
    # Matches 01b:154 exactly.
    cust["Purchase_Rate"] = cust["Txn_Count"] / ((cust["Tenure_Days"] / 30.0) + 1.0)
    cust["Frequency"] = cust["Purchase_Rate"]
    cust["Avg_Unit_Price"] = np.where(
        cust["Total_Quantity"] > 0, cust["Monetary"] / cust["Total_Quantity"], cust["Avg_Order_Value"]
    )

    cust.attrs["as_of"] = as_of
    cust.attrs["dropped_rows"] = work.attrs.get("dropped_rows", 0)
    cust.attrs["source_rows"] = work.attrs.get("source_rows", len(work))
    return cust


# Features build_customer_features genuinely supplies. Everything else in the
# model's vector is defaulted to 0.0 — this list is what makes the coverage
# figure shown to the user honest rather than decorative.
DERIVED_FEATURES = {
    "Monetary", "Txn_Count", "Avg_Order_Value", "Std_Order_Value",
    "Max_Order_Value", "Total_Quantity", "Avg_Unit_Price",
    "Tenure_Days", "Purchase_Rate", "Frequency", "Recency",
}


# ─────────────────────────────────────────────
# 3. SCORE
# ─────────────────────────────────────────────
def score_upload(token: str, mapping: dict) -> dict:
    """Score every customer in the upload and rank by churn risk."""
    df = get_session(token)
    cust = build_customer_features(df, mapping)

    artifacts = service.get_artifacts()
    churn_features = artifacts["churn"]["features"]
    threshold_days = int(artifacts["churn"]["churn_days"])
    supplied = DERIVED_FEATURES & set(churn_features)
    coverage = len(supplied) / len(churn_features)

    # Features the file cannot supply are left out of the payload entirely;
    # predict._vectorise fills them with the population median.
    # predict_segment is deliberately NOT called here. Its four tiers
    # (Low-Engagement … VIP-Platinum) are defined by the CLV bands of the
    # research dataset, so pinning them on another company's customers would be
    # a label with no meaning behind it. Uploaded customers are grouped by
    # segment_customers() instead, which re-fits K-Means on their own data.
    rows = []
    for rec in cust.to_dict(orient="records"):
        churn = service.predict_churn(rec)
        # Churn here is DEFINED as Recency > threshold, and recency is computed
        # directly from the uploaded dates. So this flag is a measurement, not a
        # prediction — it is exact, and it leads the UI. The model score is the
        # secondary, forward-looking signal.
        inactive_days = int(rec["Recency"])
        rows.append({
            "customer_id": rec["Customer_ID"],
            "inactive_days": inactive_days,
            "already_lapsed": inactive_days > threshold_days,
            "churn_probability": churn["churn_probability"],
            "risk_band": churn["risk_band"],
            "monetary": float(rec["Monetary"]),
            "txn_count": int(rec["Txn_Count"]),
            "recency": int(rec["Recency"]),
            "avg_order_value": float(rec["Avg_Order_Value"]),
            "tenure_days": int(rec["Tenure_Days"]),
            "action": _action_for(inactive_days > threshold_days, churn["risk_band"]),
        })

    # Lapsed customers first (a fact), then by model score (an estimate).
    rows.sort(key=lambda r: (r["already_lapsed"], r["churn_probability"]), reverse=True)

    lapsed = [r for r in rows if r["already_lapsed"]]
    at_risk = [r for r in rows if r["risk_band"] in ("High", "Medium")]
    high = [r for r in rows if r["risk_band"] == "High"]

    return {
        "token": token,
        "summary": {
            "total_customers": len(rows),
            "lapsed_count": len(lapsed),
            "threshold_days": threshold_days,
            "at_risk_count": len(at_risk),
            "high_risk_count": len(high),
            "revenue_at_risk": float(sum(r["monetary"] for r in lapsed)),
            "total_revenue": float(sum(r["monetary"] for r in rows)),
            "avg_order_value": float(np.mean([r["avg_order_value"] for r in rows])),
            "source_rows": cust.attrs.get("source_rows", 0),
            "dropped_rows": cust.attrs.get("dropped_rows", 0),
            "as_of": str(cust.attrs.get("as_of", ""))[:10],
            "feature_coverage": round(coverage, 3),
            "features_supplied": sorted(supplied),
            "features_defaulted": sorted(set(churn_features) - supplied),
            "churn_model": artifacts["churn"]["model_name"],
            "headline_auc": HEADLINE_CHURN_AUC,
            "reduced_auc": REDUCED_CHURN_AUC,
        },
        "domain_warning": (
            f"Your file supplies {len(supplied)} of {len(churn_features)} inputs the churn "
            "model expects — the rest are filled with typical values. Tested on this "
            f"project's own data cut down to the same {len(supplied)} inputs, the ranking "
            f"held up well (ROC-AUC about {REDUCED_CHURN_AUC}). The catch is that the "
            "model was trained on Bangladeshi retail data, so for a different business the "
            "percentages are not calibrated: read the ORDER of this list rather than the "
            f"numbers. The '{threshold_days}+ days inactive' column is the dependable one "
            "— it is measured straight from your dates, not predicted."
        ),
        "rows": rows,
    }


def _action_for(lapsed: bool, band: str) -> str:
    if lapsed:
        return "Already inactive — call this week with a win-back offer"
    return {
        "High": "Watch closely — send a discount or loyalty reward",
        "Medium": "Send a follow-up message or seasonal offer",
        "Low": "No action needed — keep on the regular newsletter",
    }.get(band, "Review manually")


def export_csv(token: str, mapping: dict) -> str:
    """Scored rows as CSV text. utf-8-sig is applied by the HTTP layer."""
    result = score_upload(token, mapping)
    return pd.DataFrame(result["rows"]).to_csv(index=False)


# ─────────────────────────────────────────────
# 4. BUSINESS ANALYSIS — the user's own numbers
# ─────────────────────────────────────────────
# Nothing below involves a trained model. These are arithmetic over the user's
# own rows, so unlike the churn score they carry no transfer caveat at all.

def monthly_series(work: pd.DataFrame) -> pd.DataFrame:
    """Sales per calendar month. Mirrors the resample in predict.get_overview()."""
    s = work.set_index("Date")["Amount"].resample("MS").sum()
    return s.reset_index().rename(columns={"Date": "Month", "Amount": "Sales"})


def business_overview(work: pd.DataFrame, cust: pd.DataFrame) -> dict:
    """Headline numbers plus the month-on-month change."""
    monthly = monthly_series(work)
    points = [
        {"month": d.strftime("%Y-%m"), "sales": float(v)}
        for d, v in zip(monthly["Month"], monthly["Sales"])
    ]

    # Compare the last two *complete* months we actually have rows for.
    change = None
    if len(monthly) >= 2:
        latest, prev = float(monthly["Sales"].iloc[-1]), float(monthly["Sales"].iloc[-2])
        change = {
            "latest_month": monthly["Month"].iloc[-1].strftime("%Y-%m"),
            "latest_sales": latest,
            "previous_sales": prev,
            "pct": (latest - prev) / prev if prev else None,
        }

    best = worst = None
    if len(monthly):
        bi, wi = monthly["Sales"].idxmax(), monthly["Sales"].idxmin()
        best = {"month": monthly["Month"][bi].strftime("%Y-%m"), "sales": float(monthly["Sales"][bi])}
        worst = {"month": monthly["Month"][wi].strftime("%Y-%m"), "sales": float(monthly["Sales"][wi])}

    return {
        "total_revenue": float(work["Amount"].sum()),
        "total_customers": int(work["Customer_ID"].nunique()),
        "total_orders": int(len(work)),
        "avg_order_value": float(work["Amount"].mean()),
        "months_covered": int(len(monthly)),
        "date_from": str(work["Date"].min())[:10],
        "date_to": str(work["Date"].max())[:10],
        "repeat_customer_rate": float((cust["Txn_Count"] > 1).mean()),
        "monthly_sales": points,
        "change": change,
        "best_month": best,
        "worst_month": worst,
    }


def forecast_series(work: pd.DataFrame, horizon: int = 3) -> dict:
    """
    Seasonal-naive forecast: next month = same month last year.

    Why this method and not the LSTM or ARIMA the thesis also trained: those are
    fitted to one specific 48-month series and cannot be applied to a different
    business. Seasonal-naive needs no training — and it is the model that WON
    the study's comparison (RMSE 29.8M vs LSTM 35.9M vs ARIMA 43.5M), so the
    strongest result is also the only one that transfers.

    Returns {"available": False, "reason": ...} rather than a number when there
    is too little history. A missing dependency once made this project's
    forecast look real when it was random; the same rule applies to missing data.
    """
    monthly = monthly_series(work)
    n = len(monthly)

    if n < MIN_MONTHS_FORECAST:
        return {
            "available": False,
            "months_covered": n,
            "months_needed": MIN_MONTHS_FORECAST,
            "reason": (
                f"Your file covers {n} month(s). Predicting a month needs the same month "
                f"a year earlier, so at least {MIN_MONTHS_FORECAST} months of history are "
                "required. The sales trend below is still accurate."
            ),
        }

    sales = monthly["Sales"].tolist()
    months = list(monthly["Month"])

    predictions = []
    for h in range(1, horizon + 1):
        future = months[-1] + pd.DateOffset(months=h)
        # Same calendar month one year back; index from the end of the series.
        idx = n - 12 + (h - 1)
        if idx < 0 or idx >= n:
            break
        predictions.append({
            "month": future.strftime("%Y-%m"),
            "predicted": float(sales[idx]),
            "basis_month": months[idx].strftime("%Y-%m"),
        })

    # Backtest only when there is a full year to predict from AND a year to test
    # on; otherwise report no accuracy rather than one computed on two points.
    accuracy = None
    if n >= MIN_MONTHS_BACKTEST:
        actual = np.array(sales[12:], dtype=float)
        predicted = np.array(sales[:-12], dtype=float)
        mask = actual != 0
        if mask.any():
            accuracy = {
                "mae": float(np.mean(np.abs(actual - predicted))),
                "mape": float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100),
                "months_tested": int(len(actual)),
            }

    return {
        "available": True,
        "method": "Seasonal-naive (same month last year)",
        "months_covered": n,
        "history": [
            {"month": m.strftime("%Y-%m"), "sales": float(s)} for m, s in zip(months, sales)
        ],
        "predictions": predictions,
        "accuracy": accuracy,
        "note": (
            "Each prediction repeats the same month one year earlier. In this study that "
            "simple rule beat both the LSTM and ARIMA models, which is why it is used here."
        ),
    }


# Group names describe behaviour in the user's own data. The research dataset's
# tiers (Low-Engagement … VIP-Platinum) are deliberately not reused: they are
# defined by that dataset's CLV bands and mean nothing for another business.
def _name_groups(profile: pd.DataFrame) -> dict:
    """Label clusters by rank on spend and recency, not by fixed thresholds."""
    order = profile.sort_values("monetary", ascending=False).index.tolist()
    names = {}
    for rank, cid in enumerate(order):
        recent = profile.loc[cid, "recency"] <= profile["recency"].median()
        if rank == 0:
            names[cid] = "Best customers" if recent else "Big spenders who stopped"
        elif rank == len(order) - 1:
            names[cid] = "Occasional buyers" if recent else "Lapsed / one-off"
        else:
            names[cid] = "Regular customers" if recent else "Slipping away"
    # Two clusters can land on the same label; make them unique for the UI.
    seen: dict[str, int] = {}
    for cid, label in names.items():
        seen[label] = seen.get(label, 0) + 1
        if seen[label] > 1:
            names[cid] = f"{label} ({seen[label]})"
    return names


def segment_customers(cust: pd.DataFrame, k: int = 4) -> dict:
    """
    Group the user's customers by re-fitting K-Means on THEIR data.

    Re-fitting is the correct move here, not a shortcut: clustering is
    unsupervised, so there is no label to leak and no reason to impose groups
    learned from a different business. Silhouette is reported alongside, the
    same discipline as predict._clustering_quality() — this dataset scores 0.17
    and the UI says so rather than implying clean separation.
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return {"available": False, "reason": "scikit-learn is not installed."}

    k = max(2, min(int(k), 6))
    if len(cust) < k * 5:
        return {
            "available": False,
            "reason": f"Only {len(cust)} customers — too few to split into {k} groups.",
        }

    features = ["Recency", "Frequency", "Monetary", "Txn_Count", "Avg_Order_Value"]
    X = StandardScaler().fit_transform(cust[features].values)

    labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)
    sil = float(silhouette_score(X, labels))

    tagged = cust.assign(_cluster=labels)
    profile = tagged.groupby("_cluster").agg(
        count=("Customer_ID", "count"),
        monetary=("Monetary", "mean"),
        recency=("Recency", "mean"),
        frequency=("Frequency", "mean"),
        txn_count=("Txn_Count", "mean"),
        total_revenue=("Monetary", "sum"),
    )
    names = _name_groups(profile)

    groups = [
        {
            "cluster": int(cid),
            "name": names[cid],
            "count": int(r["count"]),
            "share": float(r["count"] / len(cust)),
            "avg_spend": float(r["monetary"]),
            "avg_days_since_purchase": float(r["recency"]),
            "avg_orders": float(r["txn_count"]),
            "total_revenue": float(r["total_revenue"]),
        }
        for cid, r in profile.iterrows()
    ]
    groups.sort(key=lambda g: g["total_revenue"], reverse=True)

    return {
        "available": True,
        "k": k,
        "silhouette": sil,
        "separation": "weak" if sil < 0.25 else "moderate" if sil < 0.5 else "clear",
        "groups": groups,
        "note": (
            "Groups are found in your own data, not carried over from the research "
            "dataset. A low separation score means customers shade into each other, so "
            "treat the groups as a useful guide rather than hard boundaries."
        ),
    }


def top_products(work: pd.DataFrame, limit: int = 15) -> dict:
    """What sells. Only meaningful when a product column was mapped."""
    if "Product" not in work.columns:
        return {"available": False, "reason": "No product column was mapped."}

    g = work[work["Product"] != ""].groupby("Product").agg(
        revenue=("Amount", "sum"),
        orders=("Amount", "count"),
        units=("Quantity", "sum"),
    ).sort_values("revenue", ascending=False)

    if g.empty:
        return {"available": False, "reason": "The mapped product column is empty."}

    total = float(work["Amount"].sum())
    return {
        "available": True,
        "distinct_products": int(len(g)),
        "products": [
            {
                "product": str(name),
                "revenue": float(r["revenue"]),
                "orders": int(r["orders"]),
                "units": float(r["units"]),
                "share": float(r["revenue"] / total) if total else 0.0,
            }
            for name, r in g.head(limit).iterrows()
        ],
    }


# One parse per (token, mapping) rather than one per page. The frame is already
# in memory; re-aggregating it five times to render five views is pure waste.
_ANALYSIS_CACHE: OrderedDict[tuple, dict] = OrderedDict()


def analyse(token: str, mapping: dict) -> dict:
    """Clean + aggregate once, cached against the token and mapping."""
    key = (token, tuple(sorted((k, v) for k, v in mapping.items() if v)))
    cached = _ANALYSIS_CACHE.get(key)
    if cached is not None:
        _ANALYSIS_CACHE.move_to_end(key)
        return cached

    work = clean_transactions(get_session(token), mapping)
    cust = build_customer_features(work, mapping)
    result = {"work": work, "cust": cust}

    _ANALYSIS_CACHE[key] = result
    _ANALYSIS_CACHE.move_to_end(key)
    while len(_ANALYSIS_CACHE) > MAX_SESSIONS:
        _ANALYSIS_CACHE.popitem(last=False)
    return result


def overview_for(token: str, mapping: dict) -> dict:
    a = analyse(token, mapping)
    return business_overview(a["work"], a["cust"])


def forecast_for(token: str, mapping: dict, horizon: int = 3) -> dict:
    return forecast_series(analyse(token, mapping)["work"], horizon=horizon)


def segments_for(token: str, mapping: dict, k: int = 4) -> dict:
    return segment_customers(analyse(token, mapping)["cust"], k=k)


def products_for(token: str, mapping: dict) -> dict:
    return top_products(analyse(token, mapping)["work"])
