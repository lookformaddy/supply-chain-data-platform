"""Inventory graph: nodes, lanes, and route queries.

The graph is deliberately small and explicit — Dijkstra over a dict
adjacency list — because the point is correct disruption semantics
(exclude disrupted lanes, fall back to an alternate lane), not a graph
library. Upstream/downstream impact is a reachability query, which is
what an operator actually asks during a disruption: "what else breaks?"
"""

from __future__ import annotations

import heapq

from supply_chain.errors import NoPathError, UnknownNodeError
from supply_chain.models import Lane, Node


class SupplyGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.lanes: dict[str, Lane] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def add_lane(self, lane: Lane) -> None:
        if lane.source not in self.nodes or lane.target not in self.nodes:
            raise UnknownNodeError(
                f"lane {lane.lane_id} references unknown node"
            )
        self.lanes[lane.lane_id] = lane

    def disrupt(self, lane_id: str) -> None:
        old = self.lanes[lane_id]
        self.lanes[lane_id] = Lane(
            old.lane_id, old.source, old.target, old.lead_time_days,
            old.cost, old.capacity_units, disrupted=True,
        )

    def _adjacency(self, weight: str, exclude: set[str]) -> dict[str, list]:
        adj: dict[str, list] = {}
        for lane in self.lanes.values():
            if lane.disrupted or lane.lane_id in exclude:
                continue
            w = lane.lead_time_days if weight == "lead_time" else lane.cost
            adj.setdefault(lane.source, []).append((lane.target, w, lane))
        return adj

    def shortest_path(
        self, source: str, target: str, weight: str = "lead_time",
        exclude_lanes: frozenset[str] = frozenset(),
    ) -> tuple[list[Lane], float]:
        """Dijkstra. Returns (lanes, total weight). Raises NoPathError."""
        if source not in self.nodes or target not in self.nodes:
            raise UnknownNodeError(f"unknown node in {source!r} -> {target!r}")
        adj = self._adjacency(weight, set(exclude_lanes))
        dist: dict[str, float] = {source: 0.0}
        prev: dict[str, tuple[str, Lane]] = {}
        heap: list[tuple[float, str]] = [(0.0, source)]
        while heap:
            d, node = heapq.heappop(heap)
            if d > dist.get(node, float("inf")):
                continue
            if node == target:
                break
            for nxt, w, lane in adj.get(node, []):
                nd = d + w
                if nd < dist.get(nxt, float("inf")):
                    dist[nxt] = nd
                    prev[nxt] = (node, lane)
                    heapq.heappush(heap, (nd, nxt))
        if target not in prev and source != target:
            raise NoPathError(f"no path {source} -> {target}")
        if source == target:
            return [], 0.0
        lanes: list[Lane] = []
        node = target
        while node != source:
            node, lane = prev[node]
            lanes.append(lane)
        lanes.reverse()
        return lanes, dist[target]

    def alternate_lane(self, source: str, target: str,
                       failed_lane_id: str) -> tuple[list[Lane], float]:
        """Best route that avoids one failed lane. Raises NoPathError."""
        return self.shortest_path(
            source, target, exclude_lanes=frozenset({failed_lane_id})
        )

    def upstream(self, node_id: str) -> set[str]:
        """Nodes that can reach `node_id` (suppliers of the disruption)."""
        if node_id not in self.nodes:
            raise UnknownNodeError(node_id)
        rev: dict[str, list[str]] = {}
        for lane in self.lanes.values():
            if not lane.disrupted:
                rev.setdefault(lane.target, []).append(lane.source)
        seen, stack = set(), [node_id]
        while stack:
            cur = stack.pop()
            for src in rev.get(cur, []):
                if src not in seen:
                    seen.add(src)
                    stack.append(src)
        return seen

    def downstream(self, node_id: str) -> set[str]:
        """Nodes reachable from `node_id` (everything the disruption hits)."""
        if node_id not in self.nodes:
            raise UnknownNodeError(node_id)
        fwd: dict[str, list[str]] = {}
        for lane in self.lanes.values():
            if not lane.disrupted:
                fwd.setdefault(lane.source, []).append(lane.target)
        seen, stack = set(), [node_id]
        while stack:
            cur = stack.pop()
            for nxt in fwd.get(cur, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen
