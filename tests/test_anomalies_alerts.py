"""Anomaly + alert lifecycle tests."""

from datetime import date, timedelta

import pytest

from supply_chain.alerts import AlertStore
from supply_chain.anomalies import (
    demand_anomaly,
    lead_time_anomaly,
    shipment_delay,
    stockout_risk,
)
from supply_chain.errors import InvalidAlertTransitionError
from supply_chain.models import (
    InventorySnapshot,
    LeadTimeRecord,
    ShipmentEvent,
)
from tests.conftest import demand_series


def test_demand_spike_and_drop():
    from dataclasses import replace
    history = demand_series([100] * 10)
    spike = demand_series([300], sku="SKU-001", location="STO-1")
    current = replace(spike[0], day=date(2026, 1, 11))
    alert = demand_anomaly(history, current)
    assert alert is not None and alert.kind == "demand_spike"
    assert alert.severity in ("medium", "high")
    drop = replace(current, units=10.0)
    alert2 = demand_anomaly(history, drop)
    assert alert2 is not None and alert2.kind == "demand_drop"


def test_demand_anomaly_needs_history_and_ignores_noise():
    assert demand_anomaly(demand_series([100] * 3),
                          demand_series([300])[0]) is None
    history = demand_series([100] * 10)
    from dataclasses import replace
    current = replace(demand_series([105])[0], day=date(2026, 1, 11))
    assert demand_anomaly(history, current) is None


def test_lead_time_blowout_and_shipment_delay():
    rec = LeadTimeRecord("SUP-1", "SKU-001", 5.0, 12.0, date(2026, 1, 5))
    alert = lead_time_anomaly(rec)
    assert alert is not None and alert.kind == "lead_time_blowout"
    assert lead_time_anomaly(
        LeadTimeRecord("SUP-1", "SKU-001", 5.0, 6.0, date(2026, 1, 5))
    ) is None
    ship = ShipmentEvent("SH-1", "SKU-001", "L-01", date(2026, 1, 1),
                         date(2026, 1, 4), 100.0)
    assert shipment_delay(ship) is not None
    on_time = ShipmentEvent("SH-2", "SKU-001", "L-01", date(2026, 1, 1),
                            date(2026, 1, 1), 100.0)
    assert shipment_delay(on_time) is None
    in_transit = ShipmentEvent("SH-3", "SKU-001", "L-01", date(2026, 1, 1),
                               None, 100.0)
    assert shipment_delay(in_transit) is None


def test_stockout_risk_cover_vs_lead_time():
    snap = InventorySnapshot("SKU-001", "STO-1", date(2026, 1, 5), 100.0)
    assert stockout_risk(snap, 100.0, 5.0) is not None  # 1d cover < 5d
    assert stockout_risk(snap, 10.0, 5.0) is None  # 10d cover >= 5d


def test_alert_dedup_and_lifecycle():
    store = AlertStore()
    history = demand_series([100] * 10)
    from dataclasses import replace
    current = replace(demand_series([300])[0], day=date(2026, 1, 11))
    alert = demand_anomaly(history, current)
    assert alert is not None
    first = store.ingest(alert)
    second = store.ingest(alert)
    assert first is second
    assert first.occurrences == 2
    assert len(store.open_alerts()) == 1
    store.ack(alert.fingerprint)
    assert store.by_status("acked")[0].status == "acked"
    store.resolve(alert.fingerprint)
    assert store.by_status("resolved")[0].status == "resolved"
    with pytest.raises(InvalidAlertTransitionError):
        store.ack(alert.fingerprint)  # resolved is terminal
    # A fresh detection with the same fingerprint after resolution is new.
    fresh_detection = demand_anomaly(history, current)
    assert fresh_detection is not None
    fresh = store.ingest(fresh_detection)
    assert fresh is not alert
    assert fresh.occurrences == 1
    assert fresh.status == "open"
