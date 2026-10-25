"""Platform orchestrator: wires ingestion, graph, forecasting, policy,
anomalies, alerts, and metrics into one daily run.

Ingestion is append-only in memory (the seam where a real store slots
in). `run_day` is the unit of work: forecast each SKU-location,
recommend replenishment, detect anomalies, and roll up that day's SLIs.
"""

from __future__ import annotations

from datetime import date

from supply_chain.alerts import AlertStore
from supply_chain.anomalies import (
    demand_anomaly,
    lead_time_anomaly,
    shipment_delay,
    stockout_risk,
)
from supply_chain.forecasting import (
    mean,
    moving_average_forecast,
    seasonal_naive_forecast,
    series_for,
    stdev,
)
from supply_chain.graph import SupplyGraph
from supply_chain.metrics import daily_rollup
from supply_chain.models import (
    DailyMetrics,
    DemandSignal,
    Forecast,
    InventorySnapshot,
    LeadTimeRecord,
    Recommendation,
    ShipmentEvent,
)
from supply_chain.policy import recommend


class SupplyChainPlatform:
    def __init__(self, graph: SupplyGraph | None = None,
                 service_level: float = 0.95,
                 ordering_cost: float = 250.0,
                 holding_cost: float = 2.0,
                 forecast_window: int = 7,
                 season_days: int = 7) -> None:
        self.graph = graph or SupplyGraph()
        self.alerts = AlertStore()
        self.demand: list[DemandSignal] = []
        self.inventory: list[InventorySnapshot] = []
        self.shipments: list[ShipmentEvent] = []
        self.lead_times: list[LeadTimeRecord] = []
        self.service_level = service_level
        self.ordering_cost = ordering_cost
        self.holding_cost = holding_cost
        self.forecast_window = forecast_window
        self.season_days = season_days

    # -- ingestion (append-only) -------------------------------------
    def ingest_demand(self, rows: list[DemandSignal]) -> int:
        self.demand.extend(rows)
        return len(rows)

    def ingest_inventory(self, rows: list[InventorySnapshot]) -> int:
        self.inventory.extend(rows)
        return len(rows)

    def ingest_shipments(self, rows: list[ShipmentEvent]) -> int:
        self.shipments.extend(rows)
        return len(rows)

    def ingest_lead_times(self, rows: list[LeadTimeRecord]) -> int:
        self.lead_times.extend(rows)
        return len(rows)

    # -- daily run ----------------------------------------------------
    def run_day(self, day: date) -> dict:
        forecasts: list[Forecast] = []
        recommendations: list[Recommendation] = []
        actuals: list[float] = []
        predicted: list[float] = []
        keys = {(d.sku, d.location) for d in self.demand}
        for sku, location in sorted(keys):
            series = series_for(self.demand, sku, location)
            prior = [d for d in series if d.day < day]
            if len(prior) >= self.forecast_window:
                fc = moving_average_forecast(prior, self.forecast_window, day)
                forecasts.append(fc)
                actual = next((d.units for d in series if d.day == day), None)
                if actual is not None:
                    actuals.append(actual)
                    predicted.append(fc.value)
            if prior:
                units = [d.units for d in prior]
                snap = next(
                    (s for s in self.inventory
                     if s.sku == sku and s.location == location
                     and s.day == day),
                    None,
                )
                if snap is not None:
                    recommendations.append(recommend(
                        sku, location, mean(units), stdev(units), 5.0,
                        self.service_level, self.ordering_cost,
                        self.holding_cost, snap.on_hand, snap.on_order,
                    ))
                    risk = stockout_risk(snap, mean(units), 5.0)
                    if risk is not None:
                        self.alerts.ingest(risk)
            today = next((d for d in series if d.day == day), None)
            if today is not None:
                alert = demand_anomaly(series, today)
                if alert is not None:
                    self.alerts.ingest(alert)
        for record in self.lead_times:
            if record.day == day:
                alert = lead_time_anomaly(record)
                if alert is not None:
                    self.alerts.ingest(alert)
        for ship in self.shipments:
            if ship.promised_day == day:
                alert = shipment_delay(ship)
                if alert is not None:
                    self.alerts.ingest(alert)
        day_demand = [d for d in self.demand if d.day == day]
        ordered = sum(d.units for d in day_demand)
        # Fulfilment proxy: demand covered by on-hand inventory that day.
        fulfilled = 0.0
        for snap in self.inventory:
            if snap.day == day:
                dem = next(
                    (d.units for d in day_demand
                     if d.sku == snap.sku and d.location == snap.location),
                    0.0,
                )
                fulfilled += min(dem, snap.on_hand)
        metrics: DailyMetrics = daily_rollup(
            day, self.demand, self.inventory, self.shipments,
            actuals, predicted, fulfilled, ordered,
        )
        seasonal = [
            seasonal_naive_forecast(
                [d for d in series_for(self.demand, sku, loc) if d.day < day],
                self.season_days, day,
            )
            for sku, loc in sorted(keys)
            if len([d for d in series_for(self.demand, sku, loc)
                    if d.day < day]) >= 1
        ]
        return {
            "day": day.isoformat(),
            "forecasts": forecasts,
            "seasonal_forecasts": seasonal,
            "recommendations": recommendations,
            "open_alerts": self.alerts.open_alerts(),
            "metrics": metrics,
        }

    def inventory_status(self, location: str) -> list[InventorySnapshot]:
        """Latest snapshot per SKU at a location."""
        latest: dict[str, InventorySnapshot] = {}
        for snap in self.inventory:
            if snap.location != location:
                continue
            cur = latest.get(snap.sku)
            if cur is None or snap.day > cur.day:
                latest[snap.sku] = snap
        return sorted(latest.values(), key=lambda s: s.sku)
