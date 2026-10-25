"""Metrics rollup + platform daily-run tests."""

from datetime import date

from supply_chain.generator import generate
from supply_chain.metrics import daily_rollup
from supply_chain.models import DemandSignal, InventorySnapshot, ShipmentEvent


def test_daily_rollup_ratios():
    day = date(2026, 1, 5)
    demand = [DemandSignal("SKU-001", "STO-1", day, 100.0)]
    inventory = [InventorySnapshot("SKU-001", "STO-1", day, 100.0)]
    shipments = [
        ShipmentEvent("SH-1", "SKU-001", "L-01", day, day, 10.0),
        ShipmentEvent("SH-2", "SKU-001", "L-01", day, date(2026, 1, 7), 10.0),
    ]
    m = daily_rollup(day, demand, inventory, shipments,
                     [100.0], [90.0], 90.0, 100.0)
    assert m.fill_rate == 0.9
    assert m.stockout_rate == 0.0
    assert m.forecast_accuracy == 0.9  # 1 - WAPE(10/100)
    assert m.on_time_shipment_rate == 0.5
    assert m.sku_locations == 1


def test_daily_rollup_empty_day_is_safe():
    day = date(2026, 1, 5)
    m = daily_rollup(day, [], [], [], [], [], 0.0, 0.0)
    assert m.fill_rate == 0.0
    assert m.on_time_shipment_rate == 0.0
    assert m.forecast_accuracy == 1.0  # no forecast error recorded


def test_generator_is_deterministic():
    a = generate(seed=7, days=10)
    b = generate(seed=7, days=10)
    assert [d.units for d in a.demand] == [d.units for d in b.demand]
    c = generate(seed=8, days=10)
    assert [d.units for d in a.demand] != [d.units for d in c.demand]
    assert a.nodes and a.lanes and a.shipments and a.lead_times


def test_platform_run_day(platform, dataset):
    last = dataset.demand[-1].day
    result = platform.run_day(last)
    assert result["metrics"].day == last
    assert len(result["forecasts"]) == 6  # 3 SKUs x 2 stores
    assert len(result["recommendations"]) == 6
    assert 0.0 <= result["metrics"].fill_rate <= 1.0
    assert 0.0 <= result["metrics"].forecast_accuracy <= 1.0
    # Inventory status returns the latest snapshot per SKU at a store.
    status = platform.inventory_status("STO-1")
    assert {s.sku for s in status} == {"SKU-001", "SKU-002", "SKU-003"}


def test_platform_ingest_counts(platform):
    assert platform.ingest_demand(
        [DemandSignal("SKU-001", "STO-1", date(2026, 2, 1), 10.0)]) == 1
