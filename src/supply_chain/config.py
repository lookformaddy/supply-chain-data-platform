"""Environment-driven configuration. Every knob has a safe default."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    seed: int = _int("SC_SEED", 42)
    days: int = _int("SC_DAYS", 90)
    forecast_window: int = _int("SC_FORECAST_WINDOW", 7)
    season_days: int = _int("SC_SEASON_DAYS", 7)
    service_level: float = _float("SC_SERVICE_LEVEL", 0.95)
    ordering_cost: float = _float("SC_ORDERING_COST", 250.0)
    holding_cost: float = _float("SC_HOLDING_COST", 2.0)
    host: str = os.environ.get("SC_HOST", "127.0.0.1")
    port: int = _int("SC_PORT", 8000)
