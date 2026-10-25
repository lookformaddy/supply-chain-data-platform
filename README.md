# supply-chain-data-platform

An enterprise supply-chain data platform: synthetic ingestion of demand,
inventory, shipment, and lead-time signals; an inventory graph with
disruption-aware routing; demand-forecasting baselines with accuracy
metrics; a service-level inventory policy engine; scored anomaly
detection with a deduplicated alert lifecycle; and daily SLI rollups —
built as production-grade Python with synthetic data only.

**Track:** Data Engineering

## The enterprise problem

A supply chain is only as good as the answers it gives under pressure:

- **"What breaks if this lane goes down?"** — and what is the alternate
  route, in days and in cost?
- **"How much should we order, and why?"** — a reorder point an operator
  can audit, not a number from a black box.
- **"Is demand really spiking, or is this Tuesday?"** — seasonality and
  promotions make naive thresholds useless.
- **"Which alerts are new problems and which are yesterday's noise?"** —
  without dedup and lifecycle, an alert queue is a spam folder.
- **"Are we actually getting better?"** — fill rate, stockout rate,
  turns, forecast accuracy, and on-time rate, defined once and rolled
  up daily.

This repo implements all of it, clean-room, with synthetic data only.

## Architecture overview

```
synthetic generator ──▶ ingestion (append-only)
                              │
                    ┌─────────▼──────────┐
                    │ SupplyChainPlatform │
                    │ 1. forecast per SKU-location
                    │ 2. policy: safety stock, ROP, EOQ
                    │ 3. anomaly detectors (scored)
                    │ 4. AlertStore: dedup + lifecycle
                    │ 5. daily SLI rollup
                    └─────────┬──────────┘
                              ├──▶ SupplyGraph (Dijkstra, impact)
                              └──▶ FastAPI service (optional)
```

See [docs/architecture.md](docs/architecture.md) for the full component
map, data flow, and design trade-offs.

## How to run it

```bash
python -m venv /tmp/venv && source /tmp/venv/bin/activate
pip install -r requirements.txt
pip install -e .

# run the tests (API tests auto-skip without FastAPI)
pytest -q

# end-to-end demo: generate, ingest, run one day, print SLIs + routes
python -m supply_chain demo
# or: make demo / python examples/run_demo.py

# serve the HTTP API
python -m supply_chain serve            # -> http://127.0.0.1:8000
# GET  /inventory/{location}
# GET  /alerts?status=open
# POST /alerts/{kind}/{sku}/{location}/ack
# POST /alerts/{kind}/{sku}/{location}/resolve
# GET  /graph/shortest-path?source=SUP-1&target=STO-1
```

Docker:

```bash
docker build -t supply-chain-data-platform .
docker run -p 8000:8000 supply-chain-data-platform
```

Configuration is environment-driven; copy `.env.example` to `.env` to
override the seed, horizon, forecast window, service level, and costs.

## Key design decisions and trade-offs

- **Baselines before models.** Moving average and seasonal naive are the
  honest floor every fancier forecaster must beat on MAPE/WAPE; their
  failure modes (lag on shifts, promotion blindness) stay visible.
- **Safety stock is z · σ · √L, stated openly.** It assumes independent
  daily demand and therefore understates risk for spiky SKUs — the
  anomaly detectors, not the formula, are the backstop.
- **Orders are capped at one EOQ and zero above the reorder point**, so
  the policy cannot over-order every cycle. EOQ ignores lane capacity
  and minimum order quantities; those constraints are the next iteration.
- **Graph routing is single-objective** (lead time *or* cost) so the
  disruption fallback stays auditable; the alternate-lane query is the
  operator's tool, not a hidden optimizer.
- **Alerts dedup by problem, not by event.** One open row per
  (kind, sku, location) with an occurrence counter stops daily detection
  runs from flooding the queue; resolved alerts never suppress new ones.
- **Resolved is terminal, open → resolved is allowed.** The lifecycle
  is small on purpose: anything richer (reopen, snooze) is policy, and
  policy belongs above the store, not inside it.
- **Fill rate's fulfilment input is explicit.** The demo covers demand
  with on-hand inventory as a proxy; `daily_rollup` takes
  fulfilled/ordered units as arguments so a real order feed can replace
  the proxy without changing the ratio.
- **In-memory stores are the seam.** Lists and the alert store are where
  Postgres/Delta slot in; no logic above them assumes persistence.
- **FastAPI is optional.** The core library, CLI, and most tests run on
  the standard library + pytest; the API suite skips cleanly without it.

## What it demonstrates

For a Director-level interview, this repo is evidence of: designing a
supply-chain data platform end to end (ingestion → graph → forecast →
policy → detection → metrics); graph reasoning for disruption response
(shortest path, alternate lane, upstream/downstream impact); forecasting
discipline (baselines first, MAPE/WAPE as the scoreboard); inventory
theory made auditable (service-level safety stock, reorder points, EOQ
with reasons); operable alerting (scored, deduplicated, lifecycle
managed); and SLI definition as a single source of truth.

## CI

The CI definition ships at [docs/github-actions-ci.yml](docs/github-actions-ci.yml).
It activates by moving it to `.github/workflows/ci.yml` (kept out of
`.github/workflows/` here because the GitHub App used for publishing lacks
the Workflows permission).

## Clean-room note

All code is original and all data is synthetic (invented SKUs, nodes,
and demand patterns). No employer code, data, or internal designs are
included.
