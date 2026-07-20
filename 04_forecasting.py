"""
=============================================================
STEP 4: SALES FORECASTING — LSTM vs ARIMA
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
TASK: Forecast monthly sales using LSTM and compare with ARIMA

HOW TO RUN (after step 1):
    python 04_forecasting.py

WHAT THIS GENERATES (output/figures/):
  - monthly_sales_trend.png       → raw sales trend 2021-2024
  - lstm_vs_arima_forecast.png    → comparison forecast chart
  - forecast_error_comparison.png → RMSE / MAE bar chart
  - lstm_training_loss.png        → training vs validation loss
"""


import utf8_console  # noqa: F401  — UTF-8 stdout before any printing
import pandas as pd
import numpy as np
import pickle
import os
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error

warnings.filterwarnings("ignore")
os.makedirs("output/figures", exist_ok=True)
os.makedirs("output/models", exist_ok=True)

# TensorFlow / Keras
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    tf.random.set_seed(42)
    print("[INFO] TensorFlow found — training real LSTM model")
except ImportError as e:
    # Previously this fell back to fabricating forecasts as
    # `actual + random noise`, which silently produced impossible metrics
    # (MAPE 0.74%) that looked like real results. Failing loudly is the only
    # safe behaviour: a missing dependency must never look like a finding.
    raise SystemExit(
        "\nERROR: TensorFlow is required for the LSTM model but is not installed.\n"
        "  TensorFlow has no build for Python 3.14, so use the 3.12 venv:\n"
        "    python 04_forecasting.py\n"
        "  To build that venv, see README section 5.\n"
        f"  (original import error: {e})"
    )

# ARIMA
try:
    from statsmodels.tsa.arima.model import ARIMA
except ImportError as e:
    raise SystemExit(
        "\nERROR: statsmodels is required for the ARIMA baseline but is not installed.\n"
        "  Install with: pip install statsmodels\n"
        f"  (original import error: {e})"
    )

print("=" * 60)
print("  STEP 4: SALES FORECASTING (LSTM vs ARIMA)")
print("=" * 60)

# ─────────────────────────────────────────────
# 1. PREPARE MONTHLY TIME SERIES
# ─────────────────────────────────────────────
print("\n[1] Loading dataset and building monthly time series...")
df = pd.read_csv("output/processed_dataset.csv")
df["Transaction_Date"] = pd.to_datetime(df["Transaction_Date"])
df["Year_Month"] = df["Transaction_Date"].dt.to_period("M")

monthly_sales = df.groupby("Year_Month").agg(
    Total_Sales = ("Net_Amount_BDT", "sum"),
    Txn_Count   = ("Transaction_ID", "count"),
    Avg_Order   = ("Net_Amount_BDT", "mean"),
).reset_index()
monthly_sales["Year_Month"] = monthly_sales["Year_Month"].astype(str)
monthly_sales = monthly_sales.sort_values("Year_Month")

print(f"    Monthly periods: {len(monthly_sales)}")
print(f"    Sales range: BDT {monthly_sales['Total_Sales'].min():,.0f} → {monthly_sales['Total_Sales'].max():,.0f}")

# Plot raw trend
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(monthly_sales["Year_Month"], monthly_sales["Total_Sales"] / 1e6, "b-o", markersize=4, linewidth=1.8, label="Monthly Net Sales")
ax.fill_between(range(len(monthly_sales)), monthly_sales["Total_Sales"] / 1e6, alpha=0.1, color="blue")
ax.set_title("Monthly Sales Trend — 2021 to 2024 (Bangladeshi Business)", fontsize=13, fontweight="bold")
ax.set_ylabel("Total Net Sales (BDT Million)", fontsize=11)
ax.set_xlabel("Month", fontsize=11)
ax.set_xticks(range(0, len(monthly_sales), 3))
ax.set_xticklabels(monthly_sales["Year_Month"].iloc[::3], rotation=45, ha="right", fontsize=8)
ax.grid(alpha=0.3)
ax.spines[["top","right"]].set_visible(False)
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig("output/figures/monthly_sales_trend.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/monthly_sales_trend.png")

# ─────────────────────────────────────────────
# 2. PREPARE SEQUENCES FOR LSTM
# ─────────────────────────────────────────────
sales_values = monthly_sales["Total_Sales"].values.reshape(-1, 1)

LOOK_BACK = 6  # use last 6 months to predict next month
TEST_MONTHS = 6

# Normalize — the scaler is fit on TRAINING MONTHS ONLY.
# Fitting on the whole series (as this script previously did) leaks the
# test period's min/max into training: the model would implicitly know the
# highest sales month before ever forecasting it.
n_train_months = len(sales_values) - TEST_MONTHS
ts_scaler = MinMaxScaler()
ts_scaler.fit(sales_values[:n_train_months])
sales_scaled = ts_scaler.transform(sales_values)
print(f"    Scaler fit on first {n_train_months} months only "
      f"(last {TEST_MONTHS} held out)")

def create_sequences(data, look_back):
    X, y = [], []
    for i in range(look_back, len(data)):
        X.append(data[i - look_back:i, 0])
        y.append(data[i, 0])
    return np.array(X), np.array(y)

X_seq, y_seq = create_sequences(sales_scaled, LOOK_BACK)
X_seq = X_seq.reshape((X_seq.shape[0], X_seq.shape[1], 1))

split_idx = len(X_seq) - TEST_MONTHS
X_tr, X_te = X_seq[:split_idx], X_seq[split_idx:]
y_tr, y_te = y_seq[:split_idx], y_seq[split_idx:]

print(f"\n[2] LSTM sequences prepared:")
print(f"    Look-back window: {LOOK_BACK} months")
print(f"    Training sequences: {len(X_tr)}")
print(f"    Test sequences (forecast): {len(X_te)}")

# ─────────────────────────────────────────────
# 3. LSTM MODEL
# ─────────────────────────────────────────────
print("\n[3] LSTM Model...")

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(LOOK_BACK, 1)),
    Dropout(0.2),
    LSTM(32, return_sequences=False),
    Dropout(0.2),
    Dense(16, activation="relu"),
    Dense(1),
])
model.compile(optimizer="adam", loss="mse")
model.summary()

es = EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)
history = model.fit(
    X_tr, y_tr,
    epochs=100, batch_size=4,
    validation_split=0.2,
    callbacks=[es],
    verbose=0,
)
print(f"    Training complete — epochs ran: {len(history.history['loss'])}")

# Training loss plot
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(history.history["loss"], label="Training Loss", color="#0D1B2A", linewidth=2)
ax.plot(history.history["val_loss"], label="Validation Loss", color="#0A8754", linewidth=2, linestyle="--")
ax.set_title("LSTM Training & Validation Loss", fontsize=13, fontweight="bold")
ax.set_xlabel("Epoch", fontsize=11)
ax.set_ylabel("MSE Loss", fontsize=11)
ax.legend(fontsize=10)
ax.grid(alpha=0.3)
ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig("output/figures/lstm_training_loss.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/lstm_training_loss.png")

lstm_pred_scaled = model.predict(X_te, verbose=0)
lstm_pred = ts_scaler.inverse_transform(lstm_pred_scaled).flatten()
model.save("output/models/lstm_model.h5")
print("    → Saved: output/models/lstm_model.h5")

# ─────────────────────────────────────────────
# 4. ARIMA MODEL
# ─────────────────────────────────────────────
print("\n[4] ARIMA Model...")
actual_test = ts_scaler.inverse_transform(y_te.reshape(-1, 1)).flatten()
train_series = ts_scaler.inverse_transform(y_tr.reshape(-1, 1)).flatten()

arima_model = ARIMA(train_series, order=(2, 1, 2))
arima_result = arima_model.fit()
arima_pred = arima_result.forecast(steps=TEST_MONTHS)
print(f"    ARIMA(2,1,2) fitted. AIC: {arima_result.aic:.2f}")

# ─────────────────────────────────────────────
# 4b. SEASONAL-NAIVE BASELINE
# ─────────────────────────────────────────────
# "Next August will look like last August." This is the baseline any
# seasonal forecasting claim must beat. The thesis argues Bangladeshi
# retail is strongly seasonal (Eid, Ramadan, Pohela Boishakh) — if that is
# true, this trivial rule is hard to beat, and beating ARIMA alone proves
# much less than it appears to.
print("\n[4b] Seasonal-naive baseline (value from 12 months earlier)...")

full_sales = monthly_sales["Total_Sales"].values
test_start_abs = len(full_sales) - TEST_MONTHS
snaive_pred = np.array([full_sales[i - 12] for i in range(test_start_abs, len(full_sales))])
print(f"    Forecast for each test month = same month one year earlier")

# ─────────────────────────────────────────────
# 5. CALCULATE METRICS
# ─────────────────────────────────────────────
def rmse(actual, pred):
    return np.sqrt(mean_squared_error(actual, pred))

def mape(actual, pred):
    return np.mean(np.abs((actual - pred) / (actual + 1e-9))) * 100

lstm_rmse = rmse(actual_test, lstm_pred)
lstm_mae  = mean_absolute_error(actual_test, lstm_pred)
lstm_mape = mape(actual_test, lstm_pred)

arima_rmse = rmse(actual_test, arima_pred)
arima_mae  = mean_absolute_error(actual_test, arima_pred)
arima_mape = mape(actual_test, arima_pred)

snaive_rmse = rmse(actual_test, snaive_pred)
snaive_mae  = mean_absolute_error(actual_test, snaive_pred)
snaive_mape = mape(actual_test, snaive_pred)

print(f"\n  FORECASTING RESULTS:")
print(f"  {'Metric':<12} {'LSTM':>16} {'ARIMA':>16} {'Seasonal-Naive':>16}")
print(f"  {'-'*62}")
print(f"  {'RMSE':<12} {lstm_rmse:>16,.0f} {arima_rmse:>16,.0f} {snaive_rmse:>16,.0f}")
print(f"  {'MAE':<12} {lstm_mae:>16,.0f} {arima_mae:>16,.0f} {snaive_mae:>16,.0f}")
print(f"  {'MAPE (%)':<12} {lstm_mape:>15.2f}% {arima_mape:>15.2f}% {snaive_mape:>15.2f}%")

# The honest verdict: deep learning has to beat the trivial rule, not just ARIMA
best_name, best_rmse = min(
    [("LSTM", lstm_rmse), ("ARIMA", arima_rmse), ("Seasonal-Naive", snaive_rmse)],
    key=lambda t: t[1],
)
print(f"\n  Best by RMSE: {best_name}")
if best_name != "LSTM":
    print(f"  ⚠ LSTM does NOT win. {best_name} is better — report this honestly;")
    print(f"    a negative result is still a result, and hiding it is not defensible.")
else:
    print(f"  ✓ LSTM beats both ARIMA and the seasonal-naive baseline")

# ─────────────────────────────────────────────
# 6. FORECAST COMPARISON PLOT
# ─────────────────────────────────────────────
print("\n[5] Generating Forecast Comparison Chart...")
all_actual = ts_scaler.inverse_transform(y_seq.reshape(-1, 1)).flatten()
periods    = list(monthly_sales["Year_Month"].iloc[LOOK_BACK:])
test_start = len(all_actual) - TEST_MONTHS

fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(range(len(all_actual)), all_actual / 1e6, color="#0D1B2A", linewidth=2.2, label="Actual Sales", zorder=3)
ax.axvline(x=test_start, color="gray", linestyle=":", linewidth=1.5, alpha=0.7, label="Train/Test Split")
ax.plot(range(test_start, len(all_actual)), lstm_pred / 1e6, "o--", color="#0A8754", linewidth=2, markersize=6, label=f"LSTM Forecast (RMSE={lstm_rmse/1e6:.2f}M)")
ax.plot(range(test_start, len(all_actual)), arima_pred / 1e6, "s:", color="#E63946", linewidth=2, markersize=6, label=f"ARIMA Forecast (RMSE={arima_rmse/1e6:.2f}M)")
ax.plot(range(test_start, len(all_actual)), snaive_pred / 1e6, "^-.", color="#F5A623", linewidth=2, markersize=6, label=f"Seasonal-Naive (RMSE={snaive_rmse/1e6:.2f}M)")
ax.fill_between(range(test_start, len(all_actual)), lstm_pred / 1e6, actual_test / 1e6, alpha=0.15, color="#0A8754", label="LSTM Error Band")

step = max(1, len(periods) // 12)
ax.set_xticks(range(0, len(periods), step))
ax.set_xticklabels(periods[::step], rotation=45, ha="right", fontsize=8)
ax.set_title("Sales Forecasting: LSTM vs ARIMA — Bangladeshi Business Dataset", fontsize=13, fontweight="bold")
ax.set_ylabel("Total Net Sales (BDT Million)", fontsize=11)
ax.legend(fontsize=9, loc="upper left")
ax.grid(alpha=0.3)
ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig("output/figures/lstm_vs_arima_forecast.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/lstm_vs_arima_forecast.png")

# ─────────────────────────────────────────────
# 7. ERROR COMPARISON BAR CHART
# ─────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
metrics = ["RMSE (BDT M)", "MAE (BDT M)", "MAPE (%)"]
lstm_v   = [lstm_rmse/1e6, lstm_mae/1e6, lstm_mape]
arima_v  = [arima_rmse/1e6, arima_mae/1e6, arima_mape]
snaive_v = [snaive_rmse/1e6, snaive_mae/1e6, snaive_mape]

labels = ["LSTM", "ARIMA", "Seasonal\nNaive"]
colors = ["#0A8754", "#E63946", "#F5A623"]

for ax, m, lv, av, sv in zip(axes, metrics, lstm_v, arima_v, snaive_v):
    vals = [lv, av, sv]
    bars = ax.bar(labels, vals, color=colors, edgecolor="white", width=0.55)
    ax.set_title(m, fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top","right"]].set_visible(False)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01 * bar.get_height(),
                f"{val:.2f}", ha="center", fontsize=9, fontweight="bold")

plt.suptitle("Forecasting Error Comparison: LSTM vs ARIMA vs Seasonal-Naive",
             fontsize=13, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig("output/figures/forecast_error_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/forecast_error_comparison.png")

# Save results
forecast_results = {
    "lstm": {"rmse": lstm_rmse, "mae": lstm_mae, "mape": lstm_mape},
    "arima": {"rmse": arima_rmse, "mae": arima_mae, "mape": arima_mape},
    "seasonal_naive": {"rmse": snaive_rmse, "mae": snaive_mae, "mape": snaive_mape},
    "actual": actual_test, "lstm_pred": lstm_pred, "arima_pred": arima_pred,
    "snaive_pred": snaive_pred, "best_model": best_name,
}
with open("output/forecast_results.pkl", "wb") as f:
    pickle.dump(forecast_results, f)

print("\n" + "=" * 60)
print("  ✅ FORECASTING COMPLETE")
print(f"  LSTM  RMSE: {lstm_rmse:,.0f}")
print(f"  ARIMA RMSE: {arima_rmse:,.0f}")
print(f"  S-Naive RMSE: {snaive_rmse:,.0f}")
print(f"  vs ARIMA          : LSTM {(arima_rmse - lstm_rmse) / arima_rmse * 100:+.1f}% RMSE")
print(f"  vs Seasonal-Naive : LSTM {(snaive_rmse - lstm_rmse) / snaive_rmse * 100:+.1f}% RMSE")
print(f"  Best: {best_name}")
print("  Next: Run  python 05_shap_analysis.py")
print("=" * 60)
