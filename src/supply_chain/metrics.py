"""Daily SLI rollup: fill rate, stockout rate, inventory turns,
forecast accuracy, and on-time shipment rate.

Each metric is defined in one place so the API, the demo, and the
tests can never disagree about what "fill rate" means.
"""

from __future__ import annotations

from datetime import date

from supply_chain.forecasting import wape
from supply_chain.models import (
    DailyMetrics,
    DemandSignal,
    InventorySnapshot,
    ShipmentEvent,
)


def daily_rollup(day: date, demand: list[DemandSignal],
                 inventory: list[InventorySnapshot],
                 shipments: list[ShipmentEvent],
                 actuals: list[float], forecasts: list[float],
                 fulfilled_units: float, ordered_units: float) -> DailyMetrics:
    """Roll up one day's SLIs.

    `fulfilled_units`/`ordered_units` are supplied by the caller because
    fulfilment lives in an order system outside this platform; the
    platform's job is to compute the ratio honestly, not invent orders.
    """
    day_inv = [s for s in inventory if s.day == day]
    day_dem = [d for d in demand if d.day == day]
    fill = fulfilled_units / ordered_units if ordered_units > 0 else 0.0
    # A SKU-location is stocked out if it has demand but zero on hand.
    stocked_out = sum(
        1 for s in day_inv
        if s.on_hand <= 0 and any(
            d.sku == s.sku and d.location == s.location for d in day_dem
        )
    )
    stockout_rate = stocked_out / len(day_inv) if day_inv else 0.0
    avg_inv = (sum(s.on_hand for s in day_inv) / len(day_inv)) if day_inv else 0.0
    cogs_proxy = sum(d.units for d in day_dem)
    turns = (cogs_proxy * 365 / avg_inv) if avg_inv > 0 else 0.0
    accuracy = max(0.0, min(1.0, 1.0 - wape(actuals, forecasts)))
    day_ship = [s for s in shipments if s.promised_day == day]
    on_time = sum(
        1 for s in day_ship
        if s.actual_day is not None and s.actual_day <= s.promised_day
    )
    on_time_rate = on_time / len(day_ship) if day_ship else 0.0
    return DailyMetrics(
        day=day, fill_rate=round(fill, 4), stockout_rate=round(stockout_rate, 4),
        inventory_turns=round(turns, 2),
        forecast_accuracy=round(accuracy, 4),
        on_time_shipment_rate=round(on_time_rate, 4),
        sku_locations=len(day_inv),
    )
