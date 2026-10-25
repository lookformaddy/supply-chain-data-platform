"""Graph tests: shortest path, disruption fallback, impact queries."""

import pytest

from supply_chain.errors import NoPathError, UnknownNodeError
from supply_chain.models import Lane, Node


def test_shortest_path_by_lead_time(graph):
    lanes, total = graph.shortest_path("SUP-1", "STO-1")
    assert [l.lane_id for l in lanes] == ["L-01", "L-03", "L-05"]
    assert total == pytest.approx(5.0 + 2.0 + 1.0)


def test_shortest_path_by_cost_prefers_cheaper_route(graph):
    # By cost, SUP-2->PLT-1->WH-2->STO-2 is cheaper than via WH-1 cross-dock.
    lanes, total = graph.shortest_path("SUP-2", "STO-2", weight="cost")
    assert total == pytest.approx(300.0 + 180.0 + 55.0)
    assert [l.lane_id for l in lanes] == ["L-02", "L-04", "L-06"]


def test_alternate_lane_with_no_fallback_raises(graph):
    # STO-1 is only reachable via WH-1, so avoiding L-03 leaves no route.
    with pytest.raises(NoPathError):
        graph.alternate_lane("SUP-1", "STO-1", "L-03")


def test_alternate_lane_cross_dock(graph):
    # STO-2 has two routes: WH-2 direct and WH-1 cross-dock.
    lanes, _ = graph.alternate_lane("PLT-1", "STO-2", "L-04")
    assert [l.lane_id for l in lanes] == ["L-03", "L-07"]


def test_disrupted_lane_is_excluded(graph):
    graph.disrupt("L-05")
    with pytest.raises(NoPathError):
        graph.shortest_path("WH-1", "STO-1")


def test_no_path_and_unknown_node(graph):
    with pytest.raises(NoPathError):
        graph.shortest_path("STO-1", "SUP-1")
    with pytest.raises(UnknownNodeError):
        graph.shortest_path("NOPE", "STO-1")


def test_upstream_downstream_impact(graph):
    assert "SUP-1" in graph.upstream("STO-1")
    assert "PLT-1" in graph.upstream("STO-1")
    assert "STO-1" in graph.downstream("WH-1")
    assert "SUP-1" not in graph.downstream("WH-1")


def test_lane_with_unknown_node_rejected(graph):
    with pytest.raises(UnknownNodeError):
        graph.add_lane(Lane("L-X", "NOPE", "STO-1", 1.0, 10.0, 100.0))
