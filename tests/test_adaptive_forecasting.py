import numpy as np
import pandas as pd
import pytest

from research.forecasting.adaptive_engine import (
    DataContractError, demand_profile, load_daily_panel, croston_forecast,
    make_supervised, rolling_origins, _metric_row
)


def panel_frame(days=90):
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    rows = []
    for shop in ("A", "B"):
        for category in ("C1", "C2"):
            for i, date in enumerate(dates):
                value = 0.0 if (i + (0 if shop == "A" else 1)) % 4 else float(2 + i % 5)
                rows.append({"date": date, "shop_id": shop, "category_id": category, "demand": value})
    return pd.DataFrame(rows)


def test_panel_loads_and_keeps_explicit_zero_sales(tmp_path):
    path = tmp_path / "panel.csv"
    panel_frame().to_csv(path, index=False)
    loaded = load_daily_panel(path)
    assert len(loaded) == 90 * 4
    assert (loaded.demand == 0).any()


def test_duplicate_daily_keys_are_rejected(tmp_path):
    frame = panel_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(DataContractError, match="Duplicate"):
        load_daily_panel(path)


def test_missing_dates_are_not_silently_zero_filled(tmp_path):
    frame = panel_frame()
    frame = frame.drop(frame.index[10])
    path = tmp_path / "gap.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(DataContractError, match="Missing dates"):
        load_daily_panel(path)


def test_demand_profile_classifies_no_demand():
    profile = demand_profile(np.zeros(30))
    assert profile.regime == "no_observed_demand"
    assert profile.positive_days == 0


def test_croston_family_returns_nonnegative_forecasts():
    y = np.array([0, 0, 4, 0, 0, 3, 0, 0, 0, 5], dtype=float)
    for method in ("croston", "sba", "tsb"):
        assert croston_forecast(y, 7, method) >= 0


def test_wape_is_null_when_actual_total_is_zero():
    metrics = _metric_row(np.zeros(3), np.ones(3), 1.0)
    assert metrics["wape"] is None


def test_direct_horizon_targets_are_future_sums_only():
    panel = panel_frame(days=90)
    samples = make_supervised(panel, horizon=7, min_history=56)
    assert not samples.empty
    first = samples.iloc[0]
    assert first["target"] >= 0
    assert first["origin"] >= pd.Timestamp("2024-02-26")


def test_rolling_origins_are_time_ordered():
    panel = panel_frame(days=120)
    origins = rolling_origins(panel, horizon=7, folds=3, min_history=56)
    assert len(origins) == 3
    assert origins == sorted(origins)


def test_mase_uses_series_specific_scales():
    metrics = _metric_row(np.array([10.0, 10.0]), np.array([12.0, 14.0]), np.array([2.0, 4.0]))
    assert metrics["mase"] == pytest.approx(1.0)
