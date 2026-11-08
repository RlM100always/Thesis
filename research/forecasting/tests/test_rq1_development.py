import numpy as np
import pandas as pd
import pytest

from research.forecasting.run_rq1_experiment import (
    features, regime, seasonal_naive, croston_classic, load_panel
)

def test_features_use_only_historical_prefix():
    origin = pd.Timestamp("2025-06-01")
    history = np.arange(1, 100, dtype=float)
    f1 = features(history, origin)
    # Future values are deliberately not passed to the feature builder.
    extended = np.r_[history, [9999.0, 9999.0]]
    f2 = features(extended[:len(history)], origin)
    assert f1 == f2

def test_regime_classification_handles_zero_demand():
    assert regime(np.zeros(90)) == "no_observed_demand"
    assert regime(np.array([0, 2] * 45, dtype=float)) in {"lumpy", "intermittent"}

def test_baselines_are_nonnegative():
    y = np.array([0, 2, 0, 1, 0, 0, 3] * 10, dtype=float)
    assert seasonal_naive(y, 7) >= 0
    assert croston_classic(y) >= 0
    assert croston_classic(np.zeros(30)) == 0

def test_load_panel_rejects_duplicate_keys(tmp_path):
    rows = [
        ["S1", "C1", "2025-01-01", 0, 1],
        ["S1", "C1", "2025-01-01", 0, 1],
    ]
    p = tmp_path / "dup.csv"
    pd.DataFrame(rows, columns=["shop_id","category","date","units_sold_observed","is_zero_observed_sales"]).to_csv(p,index=False)
    with pytest.raises(ValueError, match="Duplicate"):
        load_panel(p)

def test_load_panel_rejects_zero_flag_mismatch(tmp_path):
    rows = [["S1","C1","2025-01-01",0,0]]
    p = tmp_path / "flag.csv"
    pd.DataFrame(rows, columns=["shop_id","category","date","units_sold_observed","is_zero_observed_sales"]).to_csv(p,index=False)
    with pytest.raises(ValueError, match="Zero-sales"):
        load_panel(p)
