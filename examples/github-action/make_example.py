"""Generate the synthetic example inputs for the GitHub Action (seeded, reproducible).

Nothing here is market data. The "market" is a seeded random walk and every "strategy" is a
mix of market exposure, a small planted drift and noise, so the audit has something to grade.

    python examples/github-action/make_example.py

writes, next to this file:
    returns.csv   date,return,turnover,market   (the audited variant, fast=20|slow=150)
    variants.csv  date,<9 variants>             (every variant "tried", for PBO and N)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260928
N_DAYS = 252 * 8
FAST = (10, 20, 50)
SLOW = (100, 150, 200)
CHOSEN = "fast=20|slow=150"


def make(out_dir: Path = Path(__file__).parent) -> None:
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range("2016-01-04", periods=N_DAYS)
    market = rng.normal(0.0003, 0.011, N_DAYS)
    common = rng.normal(0.0, 0.004, N_DAYS)  # shared by every variant, so the grid is correlated

    variants = {}
    for f in FAST:
        for s in SLOW:
            # planted excess drift: a broad plateau around fast=20, slow=150 (about 1 excess Sharpe a year)
            drift = 0.00060 - 0.000004 * abs(f - 20) - 0.000002 * abs(s - 150)
            idio = rng.normal(0.0, 0.004, N_DAYS)
            variants[f"fast={f}|slow={s}"] = 0.6 * market + drift + common + idio

    var = pd.DataFrame(variants, index=dates)
    turnover = np.where(rng.random(N_DAYS) < 0.05, 1.0, 0.0)  # a trade about once a month
    ret = pd.DataFrame({"return": var[CHOSEN], "turnover": turnover, "market": market}, index=dates)

    ret.index.name = var.index.name = "date"
    ret.to_csv(out_dir / "returns.csv", float_format="%.8f", date_format="%Y-%m-%d", lineterminator="\n")
    var.to_csv(out_dir / "variants.csv", float_format="%.8f", date_format="%Y-%m-%d", lineterminator="\n")


if __name__ == "__main__":
    make()
