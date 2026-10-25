"""API tests. They auto-skip when FastAPI/httpx are not installed."""

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
pytest.importorskip("httpx", reason="httpx not installed")

from fastapi.testclient import TestClient  # noqa: E402

from supply_chain.alerts import AlertStore  # noqa: E402
from supply_chain.models import Alert  # noqa: E402
from supply_chain.platform import SupplyChainPlatform  # noqa: E402
from supply_chain.service import create_app  # noqa: E402


@pytest.fixture
def client(platform):
    alert = Alert(
        alert_id="demand_spike:SKU-001:STO-1", kind="demand_spike",
        sku="SKU-001", location="STO-1", score=80.0, severity="high",
        message="test spike",
    )
    platform.alerts.ingest(alert)
    return TestClient(create_app(platform))


def test_inventory_endpoint(client):
    resp = client.get("/inventory/STO-1")
    assert resp.status_code == 200
    assert {row["sku"] for row in resp.json()} == {
        "SKU-001", "SKU-002", "SKU-003"}


def test_alerts_ack_and_resolve(client):
    assert client.get("/alerts?status=open").json()
    ack = client.post("/alerts/demand_spike/SKU-001/STO-1/ack")
    assert ack.status_code == 200 and ack.json()["status"] == "acked"
    res = client.post("/alerts/demand_spike/SKU-001/STO-1/resolve")
    assert res.status_code == 200 and res.json()["status"] == "resolved"
    # Resolved is terminal: a second ack is a conflict.
    assert client.post("/alerts/demand_spike/SKU-001/STO-1/ack").status_code == 409


def test_shortest_path_endpoint(client):
    resp = client.get(
        "/graph/shortest-path?source=SUP-1&target=STO-1")
    assert resp.status_code == 200
    assert resp.json()["lanes"] == ["L-01", "L-03", "L-05"]
    missing = client.get(
        "/graph/shortest-path?source=STO-1&target=SUP-1")
    assert missing.status_code == 404
