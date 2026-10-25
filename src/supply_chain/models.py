"""Core record types. Plain dataclasses: no framework, no persistence
assumptions, so the logic below stays testable without a database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Node:
    """A supply-chain node: supplier, plant, warehouse, or store."""

    node_id: str
    kind: str  # "supplier" | "plant" | "warehouse" | "store"
    region: str


@dataclass(frozen=True)
class Lane:
    """A directed edge between two nodes."""

    lane_id: str
    source: str
    target: str
    lead_time_days: float
    cost: float
    capacity_units: float
    disrupted: bool = False


@dataclass(frozen=True)
class DemandSignal:
    sku: str
    location: str  # node_id of the consuming node (usually a store)
    day: date
    units: float
    promotion: bool = False


@dataclass(frozen=True)
class InventorySnapshot:
    sku: str
    location: str
    day: date
    on_hand: float
    on_order: float = 0.0


@dataclass(frozen=True)
class ShipmentEvent:
    shipment_id: str
    sku: str
    lane_id: str
    promised_day: date
    actual_day: date | None  # None = still in transit
    units: float


@dataclass(frozen=True)
class LeadTimeRecord:
    supplier: str
    sku: str
    planned_days: float
    actual_days: float
    day: date


@dataclass(frozen=True)
class Forecast:
    sku: str
    location: str
    day: date  # the day being forecast
    method: str
    value: float


@dataclass(frozen=True)
class Recommendation:
    sku: str
    location: str
    reorder_point: float
    safety_stock: float
    order_quantity: float
    on_hand: float
    reasons: tuple[str, ...] = ()


@dataclass
class Alert:
    alert_id: str
    kind: str  # demand_spike | demand_drop | lead_time_blowout |
    # stockout_risk | shipment_delay
    sku: str
    location: str
    score: float  # 0-100
    severity: str  # low | medium | high
    message: str
    status: str = "open"  # open | acked | resolved
    occurrences: int = 1

    @property
    def fingerprint(self) -> tuple[str, str, str]:
        return (self.kind, self.sku, self.location)


@dataclass(frozen=True)
class DailyMetrics:
    day: date
    fill_rate: float
    stockout_rate: float
    inventory_turns: float
    forecast_accuracy: float  # 1 - WAPE, clipped to [0, 1]
    on_time_shipment_rate: float
    sku_locations: int
