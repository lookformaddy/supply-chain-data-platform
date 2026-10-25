"""Demand-forecasting input prep, baselines, and accuracy metrics.

Two baselines only, on purpose: a moving average and a seasonal naive.
They are the honest floor every fancier model must beat, and their
failure modes (lag on trend shifts, blind to promotions) are exactly
what the accuracy metrics below expose.
"""

from __future__ import annotations

import math
from datetime import date

from supply_chain.models import DemandSignal, Forecast


def series_for(demand: list[DemandSignal], sku: str,
               location: str) -> list[DemandSignal]:
    """One SKU-location series, sorted by day. Pure input prep."""
    rows = [d for d in demand if d.sku == sku and d.location == location]
    return sorted(rows, key=lambda d: d.day)


def moving_average_forecast(series: list[DemandSignal], window: int,
                            target_day: date) -> Forecast:
    if not series:
        raise ValueError("empty demand series")
    if window < 1:
        raise ValueError("window must be >= 1")
    recent = series[-window:]
    value = sum(d.units for d in recent) / len(recent)
    return Forecast(series[0].sku, series[0].location, target_day,
                    "moving_average", round(value, 2))


def seasonal_naive_forecast(series: list[DemandSignal], season_days: int,
                            target_day: date) -> Forecast:
    """Value from exactly one season ago; falls back to the last value."""
    if not series:
        raise ValueError("empty demand series")
    if season_days < 1:
        raise ValueError("season_days must be >= 1")
    if len(series) >= season_days:
        value = series[-season_days].units
    else:
        value = series[-1].units
    return Forecast(series[0].sku, series[0].location, target_day,
                    "seasonal_naive", round(value, 2))


def mape(actuals: list[float], forecasts: list[float]) -> float:
    """Mean absolute percentage error; zero actuals are skipped."""
    if len(actuals) != len(forecasts):
        raise ValueError("actuals and forecasts must align")
    errs = [abs(a - f) / abs(a) for a, f in zip(actuals, forecasts) if a != 0]
    if not errs:
        return 0.0
    return sum(errs) / len(errs)


def wape(actuals: list[float], forecasts: list[float]) -> float:
    """Weighted absolute percentage error; robust when some actuals are 0."""
    if len(actuals) != len(forecasts):
        raise ValueError("actuals and forecasts must align")
    denom = sum(abs(a) for a in actuals)
    if denom == 0:
        return 0.0
    return sum(abs(a - f) for a, f in zip(actuals, forecasts)) / denom


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))
