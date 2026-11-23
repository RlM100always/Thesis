import pandas as pd

from research.experiments.rq2_customer_prediction import (
    CATEGORICAL, FEATURES, choose_f2_threshold, confusion_counts, evaluate, ranking_metrics,
)
from research.experiments.rq3_policy_scenario_audit import cluster_bootstrap
from research.experiments.rq4_explanation_audit import build_explanation, numeric_token_present


def test_rq2_ranking_metrics_and_threshold():
    y = [0, 1, 0, 1, 1, 0, 1, 0, 1, 0]
    score = [0.1, 0.9, 0.2, 0.8, 0.7, 0.3, 0.6, 0.4, 0.5, 0.05]
    metrics = ranking_metrics(y, score)
    assert metrics["precision_at_10pct"] == 1.0
    threshold, f2 = choose_f2_threshold(y, score)
    assert 0 <= threshold <= 1
    assert 0 <= f2 <= 1


def test_rq2_threshold_metrics_and_confusion_counts():
    y = [0, 0, 1, 1]
    probability = [0.1, 0.8, 0.2, 0.9]
    metrics = evaluate(y, probability, threshold=0.5)
    counts = confusion_counts(y, probability, threshold=0.5)
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert counts == {
        "true_negative_active": 1,
        "false_positive_inactive": 1,
        "false_negative_active": 1,
        "true_positive_inactive": 1,
    }


def test_rq2_uses_only_point_in_time_snapshot_features():
    assert "customer_id" not in FEATURES
    assert "customer_name" not in FEATURES
    assert "customer_type" not in FEATURES
    assert "loyalty_member" not in FEATURES
    assert "home_division" not in FEATURES
    assert "home_district" not in FEATURES
    assert CATEGORICAL == ["home_shop_id"]


def test_rq3_shop_cluster_bootstrap_is_reproducible():
    frame = pd.DataFrame({
        "shop_id": ["A", "A", "B", "B"],
        "cost_delta": [-2.0, -1.0, -3.0, -2.0],
        "lost_delta": [0.0, 1.0, 0.0, 0.0],
    })
    first = cluster_bootstrap(frame, ["cost_delta", "lost_delta"], 100, 7)
    second = cluster_bootstrap(frame, ["cost_delta", "lost_delta"], 100, 7)
    pd.testing.assert_frame_equal(first, second)


def test_rq4_reorder_explanation_contains_calculation_and_constraints():
    row = pd.Series({
        "observed_stock_units": 0, "pending_purchase_units": 0,
        "reorder_point_units": 105, "supplier_lead_days_scenario": 10,
        "purchase_cost_bdt": 44.93, "available_budget_bdt_scenario": 44842.20,
        "suggested_order_qty_scenario": 210,
        "constraint_reason": "UNDER_REORDER_POINT_AND_BUDGET_OK",
    })
    english, bangla = build_explanation(row, 6)
    assert "210 units" in english
    assert "35 packs of 6" in english
    assert "10 days" in english
    assert "210 ইউনিট" in bangla


def test_rq4_budget_block_is_explained():
    row = pd.Series({
        "observed_stock_units": 57, "pending_purchase_units": 0,
        "reorder_point_units": 61, "supplier_lead_days_scenario": 10,
        "purchase_cost_bdt": 298.38, "available_budget_bdt_scenario": 3302.33,
        "suggested_order_qty_scenario": 0, "constraint_reason": "BUDGET_INSUFFICIENT",
    })
    english, _ = build_explanation(row, 30)
    assert "above the available budget" in english
    assert "No order is recommended" in english


def test_rq4_numeric_evidence_match_allows_sentence_punctuation():
    assert numeric_token_present("The budget is BDT 3302.33.", 3302.33)
    assert numeric_token_present("Reorder point is 61 units.", 61)
