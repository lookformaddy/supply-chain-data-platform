"""Anomaly detection: scored, explainable detectors over demand,
lead times, inventory cover, and shipments.

Every detector returns an Alert (or None). Scoring is magnitude-based
and capped at 100; severity bands are fixed (high >= 70, medium >= 40)
so an operator can sort a queue without reading thresholds. Detectors
are pure functions — the alert store owns dedup and lifecycle.
"""

from __future__ import annotations

from supply_chain.forecasting import mean, stdev
from supply_chain.models import (
    Alert,
    DemandSignal,
    InventorySnapshot,
    LeadTimeRecord,
    ShipmentEvent,
)


def _severity(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _alert(kind: str, sku: str, location: str, score: float,
           message: str) -> Alert:
    score = max(0.0, min(100.0, score))
    return Alert(
        alert_id=f"{kind}:{sku}:{location}", kind=kind, sku=sku,
        location=location, score=round(score, 1),
        severity=_severity(score), message=message,
    )


def demand_anomaly(history: list[DemandSignal],
                   current: DemandSignal) -> Alert | None:
    """Spike/drop vs a rolling baseline. Needs >= 7 history points."""
    baseline = [d.units for d in history if d.day < current.day]
    if len(baseline) < 7 or current.units < 0:
        return None
    m, sd = mean(baseline), stdev(baseline)
    if m <= 0:
        return None
    ratio = current.units / m
    # A zero-variance baseline makes any deviation infinitely surprising;
    # without this, a perfectly flat history could never trigger.
    if sd > 0:
        z = (current.units - m) / sd
    elif current.units > m:
        z = 999.0
    elif current.units < m:
        z = -999.0
    else:
        z = 0.0
    if ratio >= 1.5 and z >= 2.0:
        return _alert("demand_spike", current.sku, current.location,
                      min(100.0, 40 + 30 * (ratio - 1.5) + 5 * z),
                      f"demand {current.units:.0f} vs baseline {m:.0f} "
                      f"(x{ratio:.2f}, z={z:.1f})")
    if ratio <= 0.5 and z <= -2.0:
        return _alert("demand_drop", current.sku, current.location,
                      min(100.0, 40 + 30 * (1 - ratio) + 5 * abs(z)),
                      f"demand {current.units:.0f} vs baseline {m:.0f} "
                      f"(x{ratio:.2f}, z={z:.1f})")
    return None


def lead_time_anomaly(record: LeadTimeRecord) -> Alert | None:
    """Blowout: actual far above plan in both relative and absolute terms."""
    if record.planned_days <= 0:
        return None
    ratio = record.actual_days / record.planned_days
    excess = record.actual_days - record.planned_days
    if ratio >= 1.5 and excess >= 3.0:
        return _alert("lead_time_blowout", record.sku, record.supplier,
                      min(100.0, 40 + 20 * (ratio - 1.5) + 5 * excess),
                      f"lead time {record.actual_days:.1f}d vs planned "
                      f"{record.planned_days:.1f}d (x{ratio:.2f})")
    return None


def stockout_risk(snapshot: InventorySnapshot, avg_daily_demand: float,
                  lead_time_days: float) -> Alert | None:
    """Days of cover below the replenishment lead time."""
    if avg_daily_demand <= 0 or lead_time_days < 0:
        return None
    cover = snapshot.on_hand / avg_daily_demand
    if cover < lead_time_days:
        shortfall = lead_time_days - cover
        return _alert("stockout_risk", snapshot.sku, snapshot.location,
                      min(100.0, 50 + 10 * shortfall),
                      f"cover {cover:.1f}d below lead time "
                      f"{lead_time_days:.1f}d (on hand {snapshot.on_hand:.0f})")
    return None


def shipment_delay(shipment: ShipmentEvent) -> Alert | None:
    """Late arrival: >= 2 days past promise."""
    if shipment.actual_day is None:
        return None
    delay = (shipment.actual_day - shipment.promised_day).days
    if delay >= 2:
        return _alert("shipment_delay", shipment.sku, shipment.lane_id,
                      min(100.0, 40 + 10 * delay),
                      f"shipment {shipment.shipment_id} {delay}d late")
    return None
