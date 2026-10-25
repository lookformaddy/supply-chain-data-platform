"""Forecasting tests: baselines, accuracy metrics, input prep."""

from datetime import date

import pytest

from supply_chain.forecasting import (
    mape,
    moving_average_forecast,
    seasonal_naive_forecast,
    series_for,
    wape,
)
from tests.conftest import demand_series


def test_series_for_filters_and_sorts():
    rows = demand_series([10, 20, 30]) + demand_series(
        [99], sku="SKU-002")
    series = series_for(rows, "SKU-001", "STO-1")
    assert [d.units for d in series] == [10, 20, 30]


def test_moving_average_uses_last_window():
    series = demand_series([10, 20, 30, 40])
    fc = moving_average_forecast(series, 2, date(2026, 1, 5))
    assert fc.value == pytest.approx(35.0)
    assert fc.method == "moving_average"


def test_seasonal_naive_one_season_ago_and_fallback():
    # 8 points, season 7: one season before the last value (80) is 20.
    series = demand_series([10, 20, 30, 40, 50, 60, 70, 80])
    fc = seasonal_naive_forecast(series, 7, date(2026, 1, 9))
    assert fc.value == pytest.approx(20.0)
    short = demand_series([5, 6])
    assert seasonal_naive_forecast(short, 7, date(2026, 1, 3)).value == 6.0


def test_empty_series_raises():
    with pytest.raises(ValueError):
        moving_average_forecast([], 7, date(2026, 1, 1))
    with pytest.raises(ValueError):
        seasonal_naive_forecast([], 7, date(2026, 1, 1))


def test_mape_and_wape():
    assert mape([100, 200], [110, 180]) == pytest.approx(0.10)
    assert wape([100, 200], [110, 180]) == pytest.approx(30 / 300)
    # Zero actuals: MAPE skips them, WAPE stays finite.
    assert mape([0, 100], [5, 110]) == pytest.approx(0.10)
    assert wape([0, 0], [5, 5]) == 0.0


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        mape([1, 2], [1])
    with pytest.raises(ValueError):
        wape([1], [1, 2])
