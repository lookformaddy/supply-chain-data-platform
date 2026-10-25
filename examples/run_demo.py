"""End-to-end demo: generate, ingest, run one day, print the summary."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supply_chain.cli import run_demo  # noqa: E402
from supply_chain.config import Settings  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_demo(Settings()))
