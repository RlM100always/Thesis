import numpy as np
import pandas as pd

from research.forecasting.context_aware_experiment import FeatureStore


def _store(values):
    rows = []
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    for shop in ("A", "B"):
        for category in ("X", "Y"):
            series = values[(shop, category)]
            for i, date in enumerate(dates):
                rows.append({"shop_id": shop, "category": category, "date": date,
                             "units_sold_observed": float(series[i])})
    pivot = pd.DataFrame(rows).pivot(index=["shop_id", "category"], columns="date",
                                     values="units_sold_observed").sort_index()
    store = FeatureStore(pivot, ["A", "B"], ["X", "Y"])
    store.dates = dates
    return store


def test_context_features_are_invariant_to_future_sales_after_origin():
    rng = np.random.default_rng(7)
    base = {(s, c): rng.poisson(2, 90).astype(float)
            for s in ("A", "B") for c in ("X", "Y")}
    changed = {k: v.copy() for k, v in base.items()}
    origin = 70
    for values in changed.values():
        values[origin:] = values[origin:] + 1000.0
    first = _store(base).snapshot(origin, context=True)
    second = _store(changed).snapshot(origin, context=True)
    pd.testing.assert_frame_equal(first, second)


def test_context_features_are_additive_and_do_not_change_base_schema():
    rng = np.random.default_rng(9)
    values = {(s, c): rng.poisson(1.5, 90).astype(float)
              for s in ("A", "B") for c in ("X", "Y")}
    store = _store(values)
    base = store.snapshot(70, context=False)
    context = store.snapshot(70, context=True)
    assert set(base.columns).issubset(set(context.columns))
    assert len(context.columns) > len(base.columns)
    assert np.isfinite(context.select_dtypes(include=[np.number]).to_numpy()).all()
