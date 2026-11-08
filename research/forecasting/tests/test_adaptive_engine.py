import numpy as np
import pandas as pd
import pytest

from research.forecasting.adaptive_engine import (
    DataContractError, demand_profile, load_daily_panel, croston_forecast,
    make_supervised, rolling_origins, _metric_row, _fit_predict, write_figures,
    select_models_by_regime, _seasonal_naive_forecast
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
    panel = panel_frame(days=180)
    origins = rolling_origins(panel, horizon=7, folds=3, min_history=56)
    assert len(origins) == 3
    assert origins == sorted(origins)


def test_mase_uses_series_specific_scales():
    metrics = _metric_row(np.array([10.0, 10.0]), np.array([12.0, 14.0]), np.array([2.0, 4.0]))
    assert metrics["mase"] == pytest.approx(1.0)


def test_hist_gradient_boosting_candidate_fits_without_leakage_features():
    panel = panel_frame(days=90)
    train = make_supervised(panel, horizon=7, min_history=56)
    origin = pd.Timestamp("2024-03-20")
    current = []
    from research.forecasting.adaptive_engine import _features
    for _, group in panel.groupby(["shop_id", "category_id"]):
        hist = group[group["date"] < origin]
        row = _features(hist, origin)
        current.append(row)
    prediction_rows = pd.DataFrame(current)
    forecasts = _fit_predict("hist_gradient_boosting", train, prediction_rows)
    assert forecasts.shape == (4,)
    assert np.isfinite(forecasts).all()
    assert (forecasts >= 0).all()


def test_validation_figures_are_written_from_supplied_results(tmp_path):
    summary = pd.DataFrame([
        {"horizon": 7, "model": "seasonal_naive_7", "level": "all", "status": "ok", "wape": 0.40},
        {"horizon": 7, "model": "croston", "level": "all", "status": "ok", "wape": 0.55},
    ])
    predictions = pd.DataFrame([
        {"horizon": 7, "origin": "2024-03-01", "shop_id": "A", "category_id": "C1",
         "model": "seasonal_naive_7", "actual": 12.0, "forecast": 10.0, "regime": "smooth"},
        {"horizon": 7, "origin": "2024-03-08", "shop_id": "A", "category_id": "C1",
         "model": "seasonal_naive_7", "actual": 15.0, "forecast": 13.0, "regime": "smooth"},
        {"horizon": 7, "origin": "2024-03-01", "shop_id": "B", "category_id": "C2",
         "model": "seasonal_naive_7", "actual": 5.0, "forecast": 4.0, "regime": "intermittent"},
        {"horizon": 7, "origin": "2024-03-08", "shop_id": "B", "category_id": "C2",
         "model": "seasonal_naive_7", "actual": 0.0, "forecast": 1.0, "regime": "intermittent"},
    ])
    files = write_figures(summary, predictions, tmp_path)
    assert "wape_comparison_h7.png" in files
    assert "actual_vs_forecast_7d.png" in files
    assert "shop_category_wape_heatmap_7d.png" in files


def test_two_stage_hurdle_candidate_returns_expected_nonnegative_demand():
    panel = panel_frame(days=90)
    train = make_supervised(panel, horizon=1, min_history=56)
    origin = pd.Timestamp("2024-03-20")
    current = []
    from research.forecasting.adaptive_engine import _features
    for _, group in panel.groupby(["shop_id", "category_id"]):
        current.append(_features(group[group["date"] < origin], origin))
    forecasts = _fit_predict("two_stage_hist", train, pd.DataFrame(current))
    assert forecasts.shape == (4,)
    assert np.isfinite(forecasts).all()
    assert (forecasts >= 0).all()


def test_regime_selection_uses_only_supported_development_groups():
    rows = []
    for origin in ("2024-03-01", "2024-03-08", "2024-03-15"):
        for model, wape in (("croston", 0.7), ("lightgbm", 0.5)):
            rows.append({"horizon": 7, "origin": origin, "model": model,
                         "level": "demand_regime", "group_value": "erratic",
                         "status": "ok", "wape": wape, "actual_total": 100.0,
                         "n": 20, "series_count": 20})
    selected = select_models_by_regime(pd.DataFrame(rows))
    assert selected.iloc[0]["selected_model"] == "lightgbm"
    assert selected.iloc[0]["status"] == "selected_on_development_cv"


def test_four_intermittent_series_are_not_enough_for_model_switching():
    rows = []
    for origin in ("2024-03-01", "2024-03-08", "2024-03-15"):
        for model, wape in (("croston", 0.3), ("lightgbm", 0.5)):
            rows.append({"horizon": 7, "origin": origin, "model": model,
                         "level": "demand_regime", "group_value": "intermittent",
                         "status": "ok", "wape": wape, "actual_total": 25.0,
                         "n": 4, "series_count": 4})
    selected = select_models_by_regime(pd.DataFrame(rows))
    assert selected.iloc[0]["selected_model"] is None
    assert selected.iloc[0]["status"] == "insufficient_validation_support"


def test_weekly_seasonal_naive_uses_matching_weekdays():
    history = np.arange(1, 22, dtype=float)
    assert _seasonal_naive_forecast(history, 1) == pytest.approx(8.0)
    assert _seasonal_naive_forecast(history, 7) == pytest.approx(77.0)


def test_drive_rq1_column_names_and_excel_serial_dates_are_supported(tmp_path):
    frame = pd.DataFrame({
        "shop_id": ["A"] * 60,
        "category": ["Rice"] * 60,
        "date": np.arange(44927, 44987),
        "units_sold_observed": [0, 1] * 30,
        "is_zero_observed_sales": [1, 0] * 30,
    })
    path = tmp_path / "drive_rq1.csv"
    frame.to_csv(path, index=False)
    loaded = load_daily_panel(path)
    assert loaded.iloc[0]["date"] == pd.Timestamp("2023-01-01")
    assert loaded.iloc[0]["category_id"] == "Rice"
    assert loaded.iloc[1]["demand"] == 1


def test_drive_zero_sales_flag_mismatch_is_rejected(tmp_path):
    frame = pd.DataFrame({
        "shop_id": ["A"] * 60,
        "category": ["Rice"] * 60,
        "date": pd.date_range("2023-01-01", periods=60).astype(str),
        "units_sold_observed": [0, 1] * 30,
        "is_zero_observed_sales": [0, 0] * 30,
    })
    path = tmp_path / "bad_zero_flag.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(DataContractError, match="is_zero_observed_sales"):
        load_daily_panel(path)


def test_rolling_origins_never_cross_exclusive_development_cutoff():
    panel = panel_frame(days=365)
    cutoff = pd.Timestamp("2024-10-01")
    origins = rolling_origins(panel, horizon=28, folds=3, min_history=56,
                              development_end=cutoff)
    assert len(origins) == 3
    assert all(origin + pd.Timedelta(days=28) <= cutoff for origin in origins)
    assert all(origin < cutoff for origin in origins)
