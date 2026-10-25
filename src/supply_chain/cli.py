"""CLI: `demo` runs the end-to-end synthetic pipeline; `serve`
starts the optional FastAPI service."""

from __future__ import annotations

import argparse
import sys

from supply_chain.config import Settings
from supply_chain.generator import generate
from supply_chain.graph import SupplyGraph
from supply_chain.platform import SupplyChainPlatform


def run_demo(settings: Settings) -> int:
    ds = generate(seed=settings.seed, days=settings.days)
    graph = SupplyGraph()
    for node in ds.nodes:
        graph.add_node(node)
    for lane in ds.lanes:
        graph.add_lane(lane)
    plat = SupplyChainPlatform(
        graph=graph, service_level=settings.service_level,
        ordering_cost=settings.ordering_cost,
        holding_cost=settings.holding_cost,
        forecast_window=settings.forecast_window,
        season_days=settings.season_days,
    )
    plat.ingest_demand(ds.demand)
    plat.ingest_inventory(ds.inventory)
    plat.ingest_shipments(ds.shipments)
    plat.ingest_lead_times(ds.lead_times)
    last = ds.demand[-1].day
    result = plat.run_day(last)
    metrics = result["metrics"]
    print(f"day: {result['day']}")
    print(f"forecasts: {len(result['forecasts'])} "
          f"recommendations: {len(result['recommendations'])} "
          f"open alerts: {len(result['open_alerts'])}")
    print(f"fill_rate={metrics.fill_rate} stockout_rate={metrics.stockout_rate} "
          f"turns={metrics.inventory_turns} "
          f"forecast_accuracy={metrics.forecast_accuracy} "
          f"on_time={metrics.on_time_shipment_rate}")
    lanes, total = graph.shortest_path("SUP-1", "STO-1")
    print(f"route SUP-1 -> STO-1: {[l.lane_id for l in lanes]} "
          f"({total} days)")
    alt, alt_total = graph.alternate_lane("PLT-1", "STO-2", "L-04")
    print(f"alternate PLT-1 -> STO-2 avoiding L-04: "
          f"{[l.lane_id for l in alt]} ({alt_total} days)")
    print(f"downstream of WH-1: {sorted(graph.downstream('WH-1'))}")
    for rec in result["recommendations"][:3]:
        print(f"  {rec.sku}@{rec.location}: order {rec.order_quantity} "
              f"(ROP {rec.reorder_point}) — {'; '.join(rec.reasons)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="supply-chain")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    sub.add_parser("serve")
    args = parser.parse_args(argv)
    settings = Settings()
    if args.command == "demo":
        return run_demo(settings)
    if args.command == "serve":
        from supply_chain.service import create_app
        import uvicorn
        uvicorn.run(create_app(), host=settings.host, port=settings.port)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
