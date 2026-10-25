"""Optional FastAPI surface. FastAPI is an optional dependency: if it
is not installed, `create_app` raises RuntimeError and the API tests
skip. The core platform never imports FastAPI.
"""

from __future__ import annotations

try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # pragma: no cover - exercised by the skip path
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]

from supply_chain.platform import SupplyChainPlatform


def create_app(platform: SupplyChainPlatform | None = None):
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed")
    app = FastAPI(title="supply-chain-data-platform")
    plat = platform or SupplyChainPlatform()

    @app.get("/inventory/{location}")
    def inventory(location: str):
        return [
            {
                "sku": s.sku, "location": s.location,
                "day": s.day.isoformat(), "on_hand": s.on_hand,
                "on_order": s.on_order,
            }
            for s in plat.inventory_status(location)
        ]

    @app.get("/recommendations")
    def recommendations():
        # Recommendations come from the most recent run_day output in a
        # real deployment; here we expose the latest inventory policy
        # inputs directly via the platform's stored state.
        return {"count": len(plat.inventory)}

    @app.get("/alerts")
    def alerts(status: str | None = None):
        rows = plat.alerts.by_status(status) if status else plat.alerts.all()
        return [
            {
                "alert_id": a.alert_id, "kind": a.kind, "sku": a.sku,
                "location": a.location, "score": a.score,
                "severity": a.severity, "message": a.message,
                "status": a.status, "occurrences": a.occurrences,
            }
            for a in rows
        ]

    @app.post("/alerts/{kind}/{sku}/{location}/ack")
    def ack(kind: str, sku: str, location: str):
        try:
            alert = plat.alerts.ack((kind, sku, location))
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"alert_id": alert.alert_id, "status": alert.status}

    @app.post("/alerts/{kind}/{sku}/{location}/resolve")
    def resolve(kind: str, sku: str, location: str):
        try:
            alert = plat.alerts.resolve((kind, sku, location))
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"alert_id": alert.alert_id, "status": alert.status}

    @app.get("/graph/shortest-path")
    def shortest_path(source: str, target: str, weight: str = "lead_time"):
        try:
            lanes, total = plat.graph.shortest_path(source, target, weight)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "lanes": [lane.lane_id for lane in lanes],
            "total": total, "weight": weight,
        }

    return app
