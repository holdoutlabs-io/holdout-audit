"""Positive controls: does the audit discriminate between planted real edges and noise?

Synthetic strategy/benchmark pairs with a KNOWN planted edge are run through the full audit under
the sealed rubric (v1.2), many times each (Monte Carlo). The protocol, including this file's SHA-256,
was sealed before the first run: docs/positive-controls/PROTOCOL.md.

    uv run python samples/controls/positive_controls.py            # full run (200 replicates per cell)
    uv run python samples/controls/positive_controls.py --reps 4   # smoke test

No market data are used.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
T = 5040  # 20 years of business days
PPY = 252
MU_B, SIG_B = 0.07, 0.16  # benchmark: 7% a year, 16% volatility
TE = 0.06  # tracking error of the excess stream (objective a)
TURNOVER, COST_BPS = 0.04, 2.0  # about 10 units a year at 2 bps
SEED0 = 20260925

# cell: (id, objective, scenario, grid, planted edge)
CELLS = (
    [(f"a-clean-plateau-{s}", "a", "clean", "plateau", s) for s in (0.0, 0.25, 0.5, 0.75, 1.0)]
    + [(f"a-heavy-plateau-{s}", "a", "heavy", "plateau", s) for s in (0.0, 0.25, 0.5, 0.75, 1.0)]
    + [(f"a-clean-isolated-{s}", "a", "clean", "isolated", s) for s in (0.0, 0.5, 1.0)]
    + [("a-clean-overfit-0.0", "a", "clean", "overfit", 0.0)]
    + [(f"c-clean-plateau-{s}", "c", "clean", "plateau", s) for s in (0.0, 0.25, 0.5)]
)


def garch_t(n: int, rng, annual_vol: float, alpha: float = 0.08, beta: float = 0.90, dof: int = 4) -> np.ndarray:
    """Zero-mean GARCH(1,1) with Student-t(dof) shocks scaled to unit variance, unconditional vol `annual_vol`."""
    var_u = (annual_vol ** 2) / PPY
    omega = var_u * (1 - alpha - beta)
    z = rng.standard_t(dof, n) / math.sqrt(dof / (dof - 2))
    out = np.empty(n)
    h = var_u
    for i in range(n):
        out[i] = math.sqrt(h) * z[i]
        h = omega + alpha * out[i] ** 2 + beta * h
    return out


def noise(n, rng, annual_vol, scenario):
    return garch_t(n, rng, annual_vol) if scenario == "heavy" else rng.normal(0.0, annual_vol / math.sqrt(PPY), n)


def generate(objective: str, scenario: str, grid: str, edge: float, seed: int):
    """Return (returns DataFrame [return, turnover, market], variants DataFrame, chosen column)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2004-01-02", periods=T)
    b = MU_B / PPY + noise(T, rng, SIG_B, scenario)
    cost = TURNOVER * COST_BPS / 1e4  # added back to gross so the planted edge is net of costs
    if objective == "a":
        lam, te = 1.0, TE
        mu_e = edge * TE / PPY
    else:  # objective (c): r = 0.6 b + e; choose mu_e so that the true SR(r) - SR(b) equals `edge`
        lam, te = 0.6, 0.04
        sig_r = math.sqrt((lam * SIG_B) ** 2 + te ** 2)
        mu_e = ((MU_B / SIG_B + edge) * sig_r - lam * MU_B) / PPY
    n_var = 50 if grid == "overfit" else 10
    base = [noise(T, rng, te, scenario) for _ in range(n_var)]
    cols = {}
    if grid == "plateau":  # neighbours share the edge: rho = 0.9 ** distance, means scale with rho
        e5 = base[4]
        for k in range(n_var):
            rho = 0.9 ** abs(k - 4)
            e = rho * e5 + math.sqrt(1 - rho * rho) * base[k] if k != 4 else e5
            cols[f"p={k + 1}"] = lam * b + e + rho * mu_e + cost
        chosen = "p=5"
    elif grid == "isolated":  # only the chosen variant has the edge
        for k in range(n_var):
            cols[f"p={k + 1}"] = lam * b + base[k] + (mu_e if k == 4 else 0.0) + cost
        chosen = "p=5"
    else:  # overfit: 50 zero-edge variants; the chosen one is the best in-sample (first 70%) by excess Sharpe
        for k in range(n_var):
            cols[f"p={k + 1}"] = lam * b + base[k] + cost
        cut = int(T * 0.7)
        ex = {c: (v[:cut] - b[:cut]) for c, v in cols.items()}
        chosen = max(ex, key=lambda c: ex[c].mean() / ex[c].std(ddof=1))
    gross = pd.DataFrame(cols, index=idx)
    net = gross - cost
    ret = pd.DataFrame({"return": gross[chosen], "turnover": TURNOVER, "market": b}, index=idx)
    return ret, net, chosen


_DECL = None


def _declaration() -> str:
    global _DECL
    if _DECL is None:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump({"objective": "improve_sharpe", "declared_at_utc": "2026-01-01T00:00:00Z",
                       "declared_by": "positive-control"}, f)
        _DECL = path
    return _DECL


def run_one(args):
    cell, objective, scenario, grid, edge, rep = args
    from holdout_audit import AuditConfig, run_audit

    seed = SEED0 + 1000 * CELLS.index(next(c for c in CELLS if c[0] == cell)) + rep
    ret, variants, chosen = generate(objective, scenario, grid, edge, seed)
    cfg = AuditConfig(name=cell, returns=ret, variants=variants, chosen_variant=chosen, n_trials=variants.shape[1],
                      base_cost_bps=COST_BPS, periods_per_year=PPY, seed=seed, rubric_version="1.2",
                      declaration_file=_declaration() if objective == "c" else None)
    res = run_audit(cfg)
    return {"cell": cell, "rep": rep, "grade": res.grade.letter, "score": res.grade.score,
            "checks": {c.key: c.status for c in res.grade.checks}}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default=str(HERE / "results.json"))
    a = ap.parse_args(argv)
    jobs = [(c[0], c[1], c[2], c[3], c[4], r) for c in CELLS for r in range(a.reps)]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(run_one, jobs, chunksize=4))
    summary = []
    for cid, objective, scenario, grid, edge in CELLS:
        g = [r["grade"] for r in rows if r["cell"] == cid]
        n, k = len(g), sum(x in "AB" for x in g)
        lo, hi = wilson(k, n)
        summary.append({"cell": cid, "objective": objective, "scenario": scenario, "grid": grid, "edge": edge,
                        "n": n, "pass_AB": k / n, "pass_AB_ci95": [lo, hi],
                        "grades": {L: g.count(L) / n for L in "ABCDF"}})
    Path(a.out).write_bytes((json.dumps({"reps": a.reps, "cells": summary, "runs": rows}, indent=1) + "\n").encode("utf-8"))
    for s in summary:
        print(f"{s['cell']:24s} pass(A/B) {100 * s['pass_AB']:5.1f}%  " + " ".join(f"{L}:{100 * v:4.0f}%" for L, v in s["grades"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
