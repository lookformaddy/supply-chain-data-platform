# Architecture

## Components

```
synthetic generator ──▶ ingestion (append-only, in-memory lists)
                              │
                    ┌─────────▼──────────┐
                    │ SupplyChainPlatform │
                    │  run_day(day):      │
                    │  1. forecast per SKU-location (moving average)
                    │  2. policy: safety stock, ROP, EOQ, recommendation
                    │  3. detectors: demand / lead time / cover / delay
                    │  4. AlertStore: dedup + lifecycle
                    │  5. daily SLI rollup
                    └─────────┬──────────┘
                              ├──▶ SupplyGraph (Dijkstra, impact queries)
                              └──▶ FastAPI service (optional, /inventory,
                                     /alerts, /graph/shortest-path)
```

| Module | Responsibility |
| --- | --- |
| `generator.py` | Deterministic synthetic data: network, demand (seasonality, promotions, disruptions), inventory, shipments, lead times. |
| `graph.py` | Nodes/lanes, Dijkstra by lead time or cost, alternate-lane fallback, upstream/downstream reachability. |
| `forecasting.py` | Series prep per SKU-location, moving-average and seasonal-naive baselines, MAPE/WAPE. |
| `policy.py` | Service-level z-values, safety stock, reorder point, EOQ, replenishment recommendations with reasons. |
| `anomalies.py` | Pure detectors: demand spike/drop, lead-time blowout, stockout risk, shipment delay — each scored 0–100. |
| `alerts.py` | Dedup by (kind, sku, location); lifecycle open → acked → resolved (open → resolved allowed; resolved terminal). |
| `metrics.py` | One definition per SLI: fill rate, stockout rate, inventory turns, forecast accuracy (1 − WAPE), on-time shipment rate. |
| `platform.py` | Orchestrator: ingestion + `run_day`. |
| `service.py` | Optional FastAPI surface; the core never imports FastAPI. |

## Data flow

Ingestion is append-only: nothing mutates a previously ingested record,
so a daily run is reproducible from the same inputs. `run_day` reads only
records up to and including the target day for history, and the target
day itself for actuals, inventory, and shipments.

## Design decisions and trade-offs

- **Baselines before models.** Moving average and seasonal naive are the
  honest floor: any ML forecaster must beat them on MAPE/WAPE, and their
  failure modes (lag on shifts, promotion blindness) are visible in the
  accuracy metric rather than hidden in a model.
- **Safety stock assumes independent daily demand** (z · σ · √L). Real
  demand is autocorrelated, so this understates risk for spiky SKUs —
  the anomaly detectors, not the policy formula, are the backstop.
- **EOQ is capped by the shortfall logic**: an order never exceeds one
  EOQ and is zero above the reorder point, so the policy cannot
  over-order on every cycle. EOQ also ignores capacity and MOQs; a
  lane-capacity constraint belongs in the next iteration.
- **Graph weights are single-objective** (lead time *or* cost). A real
  planner trades both off; Dijkstra over one weight keeps the fallback
  semantics auditable, and the alternate-lane query is the operator's
  disruption tool.
- **Alert dedup is by problem, not by event.** One open row per
  (kind, sku, location) with an occurrence counter prevents alert storms
  from daily detection runs; resolved alerts do not suppress new ones.
- **In-memory stores are the seam.** `SupplyChainPlatform`'s lists and
  `AlertStore` are where Postgres/Delta would slot in; no module above
  them assumes persistence.
- **Fill rate's fulfilment input is explicit.** The platform does not
  invent orders: `run_day` covers demand with on-hand inventory as a
  proxy, and `daily_rollup` takes fulfilled/ordered units as arguments
  so a real order feed can replace the proxy without changing the ratio.
- **FastAPI is optional.** The service module imports FastAPI lazily so
  the core library, CLI demo, and most tests run with only the standard
  library + pytest.
