import numpy as np
import pandas as pd

from research.experiments.rq2_customer_prediction_v2 import (
    apply_platt_parameters, choose_threshold, feature_list, prepare_features,
)


def test_rq2_v2_precision_threshold_respects_recall_floor():
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    probability = np.array([0.05, 0.15, 0.25, 0.35, 0.45, 0.60, 0.75, 0.90])
    threshold, result = choose_threshold(
        y, probability, "precision_at_recall_floor", recall_floor=0.75
    )
    assert 0 <= threshold <= 1
    assert result["recall"] >= 0.75
    assert 0 <= result["precision"] <= 1


def test_rq2_v2_f1_threshold_is_valid():
    y = np.array([0, 0, 1, 1, 0, 1])
    probability = np.array([0.1, 0.3, 0.4, 0.8, 0.2, 0.7])
    threshold, result = choose_threshold(y, probability, "f1")
    assert 0 <= threshold <= 1
    assert 0 <= result["f1"] <= 1


def test_rq2_v2_calibration_parameters_return_probabilities():
    raw = np.array([0.05, 0.25, 0.5, 0.75, 0.95])
    calibrated = apply_platt_parameters(raw, coefficient=0.9, intercept=-0.1)
    assert np.all((calibrated > 0) & (calibrated < 1))
    assert np.all(np.diff(calibrated) > 0)


def test_rq2_v2_trajectory_features_are_past_only_and_customer_ids_are_excluded():
    frame = pd.DataFrame({
        "customer_id": ["A", "A", "B", "B"],
        "snapshot_date": pd.to_datetime(["2024-03-31", "2024-06-30", "2024-03-31", "2024-06-30"]),
        "recency_days": [10, 20, 5, 8],
        "orders_last_30d": [2, 1, 3, 2],
        "orders_last_90d": [5, 4, 6, 5],
        "orders_last_180d": [8, 7, 9, 8],
        "sales_last_90d_bdt": [500.0, 400.0, 600.0, 550.0],
        "lifetime_orders_so_far": [10, 12, 15, 18],
        "tenure_days": [300, 390, 400, 490],
    })
    prepared = prepare_features(frame)
    a_latest = prepared[(prepared.customer_id == "A") & (prepared.snapshot_date == pd.Timestamp("2024-06-30"))].iloc[0]
    assert a_latest["prev_recency_days"] == 10
    assert a_latest["delta_orders_last_90d"] == -1
    assert "customer_id" not in feature_list("trajectory")
    assert "target" not in feature_list("trajectory")
