"""Shared fixtures: a small deterministic network and dataset."""

from datetime import date, timedelta

import pytest

from supply_chain.generator import generate
from supply_chain.graph import SupplyGraph
from supply_chain.models import DemandSignal
from supply_chain.platform import SupplyChainPlatform


@pytest.fixture
def dataset():
    return generate(seed=42, days=30)


@pytest.fixture
def graph(dataset):
    g = SupplyGraph()
    for node in dataset.nodes:
        g.add_node(node)
    for lane in dataset.lanes:
        g.add_lane(lane)
    return g


@pytest.fixture
def platform(graph, dataset):
    plat = SupplyChainPlatform(graph=graph)
    plat.ingest_demand(dataset.demand)
    plat.ingest_inventory(dataset.inventory)
    plat.ingest_shipments(dataset.shipments)
    plat.ingest_lead_times(dataset.lead_times)
    return plat


def demand_series(units, sku="SKU-001", location="STO-1"):
    start = date(2026, 1, 1)
    return [
        DemandSignal(sku, location, start + timedelta(days=i), float(u))
        for i, u in enumerate(units)
    ]
