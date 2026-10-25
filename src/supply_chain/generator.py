"""Deterministic synthetic data generator.

Seeded randomness only: the same seed always produces the same network,
demand, inventory, shipments, and lead times. Patterns are realistic on
purpose — weekly seasonality, promotions, and occasional disruptions —
but every value is invented; nothing here comes from a real operation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from supply_chain.models import (
    DemandSignal,
    InventorySnapshot,
    Lane,
    LeadTimeRecord,
    Node,
    ShipmentEvent,
)

SKUS = ["SKU-001", "SKU-002", "SKU-003"]
BASE_DEMAND = {"SKU-001": 120.0, "SKU-002": 60.0, "SKU-003": 30.0}


@dataclass
class SyntheticDataset:
    nodes: list[Node] = field(default_factory=list)
    lanes: list[Lane] = field(default_factory=list)
    demand: list[DemandSignal] = field(default_factory=list)
    inventory: list[InventorySnapshot] = field(default_factory=list)
    shipments: list[ShipmentEvent] = field(default_factory=list)
    lead_times: list[LeadTimeRecord] = field(default_factory=list)


def build_network(rng: random.Random) -> tuple[list[Node], list[Lane]]:
    nodes = [
        Node("SUP-1", "supplier", "north"),
        Node("SUP-2", "supplier", "south"),
        Node("PLT-1", "plant", "north"),
        Node("WH-1", "warehouse", "central"),
        Node("WH-2", "warehouse", "south"),
        Node("STO-1", "store", "central"),
        Node("STO-2", "store", "south"),
    ]
    specs = [
        ("L-01", "SUP-1", "PLT-1", 5.0, 400.0, 5000.0),
        ("L-02", "SUP-2", "PLT-1", 8.0, 300.0, 4000.0),
        ("L-03", "PLT-1", "WH-1", 2.0, 150.0, 6000.0),
        ("L-04", "PLT-1", "WH-2", 3.0, 180.0, 5000.0),
        ("L-05", "WH-1", "STO-1", 1.0, 50.0, 3000.0),
        ("L-06", "WH-2", "STO-2", 1.0, 55.0, 3000.0),
        ("L-07", "WH-1", "STO-2", 2.0, 90.0, 2000.0),  # cross-dock alternate
    ]
    lanes = [
        Lane(lid, s, t, lt, cost, cap, disrupted=(rng.random() < 0.0))
        for lid, s, t, lt, cost, cap in specs
    ]
    return nodes, lanes


def generate(seed: int = 42, days: int = 90) -> SyntheticDataset:
    """Generate a full synthetic dataset starting 2026-01-01."""
    rng = random.Random(seed)
    nodes, lanes = build_network(rng)
    start = date(2026, 1, 1)
    stores = ["STO-1", "STO-2"]
    ds = SyntheticDataset(nodes=nodes, lanes=lanes)
    for i in range(days):
        day = start + timedelta(days=i)
        weekly = 1.0 + 0.25 * math.sin(2 * math.pi * (i % 7) / 7.0)
        trend = 1.0 + 0.001 * i
        for sku in SKUS:
            for store in stores:
                promo = (i % 21 == 10)  # a promotion roughly every 3 weeks
                disrupted = (i % 37 == 20)  # an occasional disruption day
                noise = rng.uniform(0.85, 1.15)
                mult = weekly * trend * noise
                if promo:
                    mult *= 1.6
                if disrupted:
                    mult *= 0.55
                units = round(BASE_DEMAND[sku] * mult, 1)
                ds.demand.append(
                    DemandSignal(sku, store, day, units, promotion=promo)
                )
                # Inventory drifts around ~10 days of demand, with noise.
                on_hand = round(BASE_DEMAND[sku] * rng.uniform(7.0, 13.0), 1)
                ds.inventory.append(
                    InventorySnapshot(
                        sku, store, day, on_hand,
                        on_order=round(BASE_DEMAND[sku] * rng.uniform(0, 3), 1),
                    )
                )
    # Shipments and lead times: one per lane per week-ish, deterministic.
    for j, lane in enumerate(lanes):
        for k in range(max(1, days // 14)):
            promised = start + timedelta(days=14 * k + j)
            delay = rng.choice([0, 0, 0, 1, 3])  # mostly on time
            actual = promised + timedelta(days=delay)
            ds.shipments.append(
                ShipmentEvent(
                    f"SH-{lane.lane_id}-{k}", SKUS[j % len(SKUS)],
                    lane.lane_id, promised, actual, 500.0,
                )
            )
    for sup in ("SUP-1", "SUP-2"):
        for k in range(max(1, days // 10)):
            planned = 6.0 if sup == "SUP-1" else 9.0
            blowout = rng.random() < 0.15
            actual = planned * (2.0 if blowout else rng.uniform(0.9, 1.1))
            ds.lead_times.append(
                LeadTimeRecord(sup, "SKU-001", planned, round(actual, 1),
                               start + timedelta(days=10 * k))
            )
    return ds
