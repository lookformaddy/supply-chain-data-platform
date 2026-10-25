"""Inventory policy engine: safety stock, reorder points, EOQ, and
replenishment recommendations with human-readable reasons.

Service-level z-values are the standard normal quantiles for common
targets, linearly interpolated between them. Nothing here is a black
box: every recommendation carries the inputs that produced it.
"""

from __future__ import annotations

import math

from supply_chain.models import Recommendation

# service level -> z (standard normal quantile, rounded)
_Z_TABLE = [(0.90, 1.28), (0.95, 1.65), (0.98, 2.05), (0.99, 2.33)]


def z_for_service_level(service_level: float) -> float:
    """Interpolated z-value; clamps outside [0.90, 0.99]."""
    if service_level <= _Z_TABLE[0][0]:
        return _Z_TABLE[0][1]
    if service_level >= _Z_TABLE[-1][0]:
        return _Z_TABLE[-1][1]
    for (s0, z0), (s1, z1) in zip(_Z_TABLE, _Z_TABLE[1:]):
        if s0 <= service_level <= s1:
            frac = (service_level - s0) / (s1 - s0)
            return z0 + frac * (z1 - z0)
    raise AssertionError("unreachable")


def safety_stock(daily_demand_std: float, lead_time_days: float,
                 service_level: float) -> float:
    """z * sigma_daily * sqrt(lead time). Assumes independent daily demand."""
    if daily_demand_std < 0 or lead_time_days < 0:
        raise ValueError("demand std and lead time must be non-negative")
    return z_for_service_level(service_level) * daily_demand_std * math.sqrt(
        lead_time_days
    )


def reorder_point(avg_daily_demand: float, lead_time_days: float,
                  safety: float) -> float:
    return avg_daily_demand * lead_time_days + safety


def eoq(annual_demand: float, ordering_cost: float,
        holding_cost_per_unit_year: float) -> float:
    """Classic EOQ: sqrt(2DS/H)."""
    if annual_demand <= 0 or ordering_cost <= 0 or holding_cost_per_unit_year <= 0:
        raise ValueError("EOQ inputs must be positive")
    return math.sqrt(2 * annual_demand * ordering_cost
                     / holding_cost_per_unit_year)


def recommend(sku: str, location: str, avg_daily_demand: float,
              daily_demand_std: float, lead_time_days: float,
              service_level: float, ordering_cost: float,
              holding_cost: float, on_hand: float,
              on_order: float = 0.0) -> Recommendation:
    """Replenishment recommendation. Order only up to the shortfall vs
    reorder point, capped at one EOQ — never a blind EOQ every cycle."""
    safety = safety_stock(daily_demand_std, lead_time_days, service_level)
    rop = reorder_point(avg_daily_demand, lead_time_days, safety)
    qty = eoq(avg_daily_demand * 365, ordering_cost, holding_cost)
    position = on_hand + on_order
    reasons: list[str] = []
    if position <= rop:
        reasons.append(
            f"inventory position {position:.0f} at/below reorder point {rop:.0f}"
        )
    if safety > 0:
        reasons.append(
            f"safety stock {safety:.0f} at {service_level:.0%} service level"
        )
    if position > rop:
        reasons.append(f"position {position:.0f} above reorder point {rop:.0f}")
        order = 0.0
    else:
        order = min(qty, max(0.0, rop + qty - position))
        reasons.append(f"order up to EOQ {qty:.0f}")
    return Recommendation(sku, location, round(rop, 2), round(safety, 2),
                          round(order, 2), on_hand, tuple(reasons))
