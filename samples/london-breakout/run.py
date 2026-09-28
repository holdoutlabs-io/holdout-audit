"""London Breakout audit pipeline (PREREG.md §6). SKELETON: runs end to end on SYNTHETIC data only.

    uv run python samples/london-breakout/run.py --synthetic [--out DIR]   # seeded random walk, no real data
    uv run python samples/london-breakout/run.py --stage A                 # after sealing only (lock-checked)
    uv run python samples/london-breakout/run.py --stage B                 # after HOLDOUT-UNLOCK.json only

Stage A: in-sample, first available bar (2000) ..2023-12-31. 15-variant grid, rubric v1.2 on the default, P1 = 1 - DSR
at N = 15, the in-sample-best variant, and the declared sensitivities. Results are written to
stageA/results.json, committed, hashed into HOLDOUT-UNLOCK.json, and only then may holdout files be
placed in raw/.
Stage B: holdout 2024-01-01..2026-09-25. P2 on the default, Holm over {P1, P2}, the fixed verdict
wording, and the full-sample rubric run with the holdout split at 2024-01-01.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import lb_data  # noqa: E402
import lb_port  # noqa: E402
from holdout_audit.audit import AuditConfig, run_audit  # noqa: E402

PPY = 260  # weekdays a year (FX)
COST_BASE, COST_LOW, COST_HIGH = 1.0, 0.5, 2.0  # pips per side (PREREG §4.3): 2.0 / 1.0 / 4.0 round trip
ALPHA = 0.05
SEED = 20260925
PUBLICATION_DATE = pd.Timestamp("2018-04-17")  # first commit of the script under its current name
BENCHMARK_REASON = ("the strategy is flat overnight and long or short intraday, so a spot position is "
                    "self-financing and earns no carry; the natural null is zero excess return (PREREG §4.4)")


# --------------------------------------------------------------------------------- building blocks

def variant_returns(df: pd.DataFrame, p: lb_port.Params, cost_pips: float = COST_BASE, fill_lag: int = 0,
                    clock: str = "fixed") -> pd.DataFrame:
    """Daily gross/net/turnover/trades of one configuration on a (date, price) minute frame."""
    t = pd.to_datetime(df["date"])
    if clock == "london":
        t = lb_port.to_london_clock(t)
        p = lb_port.Params(risky_stop=p.risky_stop, open_minutes=p.open_minutes, **lb_port.LONDON_CLOCK)
    out = lb_port.generate_signals(t.dt.hour.to_numpy(), t.dt.minute.to_numpy(), df["price"].to_numpy(), p)
    return lb_port.daily_returns(t, df["price"].to_numpy(), out["signals"], cost_pips, fill_lag)


def market_returns(df: pd.DataFrame) -> pd.Series:
    """GBP/USD close-to-close daily return (last bar of each data-clock day). Regime splits only."""
    t = pd.to_datetime(df["date"])
    last = df.assign(day=t.dt.normalize().to_numpy()).groupby("day")["price"].last()
    r = last.pct_change()
    r.index = pd.DatetimeIndex(r.index, name="date")
    return r[r.index.dayofweek < 5]


def variant_matrix(df: pd.DataFrame, cost_pips: float = COST_BASE) -> pd.DataFrame:
    cols = {p.label: variant_returns(df, p, cost_pips)["net"] for p in lb_port.GRID}
    return pd.DataFrame(cols).fillna(0.0)


def one_sided_p(r: pd.Series) -> dict:
    """P(Z >= annualised Sharpe x sqrt(years)): the rubric's haircut statistic at N = 1."""
    r = pd.Series(r).dropna()
    sd = r.std(ddof=1)
    sr_d = r.mean() / sd if sd > 0 else 0.0
    years = len(r) / PPY
    t = sr_d * math.sqrt(PPY) * math.sqrt(years)
    return {"sr_annual": sr_d * math.sqrt(PPY), "years": years, "t": t, "p": float(norm.sf(t)),
            "mean_annual": float(r.mean() * PPY), "n_days": int(len(r))}


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, run, out = len(items), 0.0, {}
    for k, (name, p) in enumerate(items):
        run = max(run, min(1.0, (m - k) * p))
        out[name] = run
    return out


def verdict(p1_adj: float, p2_adj: float, full_mean_net: float) -> str:
    """The fixed wording of PREREG §7.2 (the first rule that applies)."""
    if p1_adj <= ALPHA and p2_adj <= ALPHA:
        return "SUPPORTED: as coded, positive risk-adjusted return net of costs, in-sample and in the locked holdout"
    if full_mean_net <= 0:
        return "WENT THE OTHER WAY: as coded, it lost money net of costs over the full sample"
    if p1_adj <= ALPHA:
        return "IN-SAMPLE ONLY: significant in 2000-2023 but not confirmed in the locked holdout"
    if p2_adj <= ALPHA:
        return "HOLDOUT ONLY: significant in the holdout but not shown over 2000-2023 at N = 15"
    return "NOT SHOWN: a positive net return was not shown (the point estimate is positive)"


def rubric(name: str, mat: pd.DataFrame, base: pd.DataFrame, market: pd.Series, holdout_split: str | None,
           declaration: str | None) -> dict:
    ret = pd.DataFrame({"return": mat[lb_port.DEFAULT.label], "turnover": base["turnover"].reindex(mat.index).fillna(0.0),
                        "market": market.reindex(mat.index)})
    cfg = AuditConfig(name=name, returns=ret, variants=mat, chosen_variant=lb_port.DEFAULT.label,
                      n_trials=lb_port.N_VARIANTS, periods_per_year=PPY, holdout_split=holdout_split,
                      base_cost_bps=0.0, benchmark="zero", benchmark_reason=BENCHMARK_REASON, seed=SEED,
                      rubric_version="1.2", declaration_file=declaration)
    res = run_audit(cfg)
    return {"headline": res.headline(), "dsr": float(res.dsr), "n_trials": res.n_trials,
            "checks": [{"key": c.key, "status": c.status, "value": c.value} for c in res.grade.checks]}


def sensitivities(df: pd.DataFrame, split: pd.Timestamp | None = None) -> dict:
    """Declared DESCRIPTIVE sensitivities of the default configuration (PREREG §6.4)."""
    d = lb_port.DEFAULT
    base = variant_returns(df, d)
    out = {
        "cost_low_0.5pip_side": one_sided_p(variant_returns(df, d, COST_LOW)["net"]),
        "cost_high_2.0pip_side": one_sided_p(variant_returns(df, d, COST_HIGH)["net"]),
        "gross": one_sided_p(base["gross"]),
        "next_bar_fill": one_sided_p(variant_returns(df, d, fill_lag=1)["net"]),
        "london_dst_clock": one_sided_p(variant_returns(df, d, clock="london")["net"]),
    }
    idx = base.index
    months = idx.month
    out["months_bst_approx_apr_oct"] = one_sided_p(base["net"][(months >= 4) & (months <= 10)])
    out["months_gmt_approx_nov_mar"] = one_sided_p(base["net"][(months <= 3) | (months >= 11)])
    if split is not None:
        out["before_publication"] = one_sided_p(base["net"][idx < split])
        out["after_publication"] = one_sided_p(base["net"][idx >= split])
    t = pd.to_datetime(df["date"])
    sig = lb_port.generate_signals(t.dt.hour.to_numpy(), t.dt.minute.to_numpy(), df["price"].to_numpy(), d)["signals"]
    trades = lb_port.trade_list(t, df["price"].to_numpy(), sig)
    # gross pips per round trip / 2 = the one-way cost (pips per side) at which the gross edge is zero
    out["breakeven_pips_per_side"] = float(trades["pips"].mean() / 2) if len(trades) else None
    out["mean_gross_pips_per_trade"] = float(trades["pips"].mean()) if len(trades) else None
    out["hit_rate"] = float((trades["pips"] > 0).mean()) if len(trades) else None
    out["exit_reasons"] = trades["exit_reason"].value_counts().to_dict()
    out["trades"] = int(base["trades"].sum())
    return out


def stage_a(df: pd.DataFrame, declaration: str | None, holdout_split: str | None = None,
            publication: pd.Timestamp | None = PUBLICATION_DATE) -> dict:
    mat = variant_matrix(df)
    base = variant_returns(df, lb_port.DEFAULT)
    mkt = market_returns(df)
    rub = rubric("London Breakout (as coded), GBP/USD, Stage A", mat, base, mkt, holdout_split, declaration)
    is_sr = {c: one_sided_p(mat[c])["sr_annual"] for c in mat}
    best = max(is_sr, key=is_sr.get)
    return {"stage": "A", "P1": {"statistic": "1 - DSR at N = 15 (rubric v1.2 'dsr' check), default config",
                                 "dsr": rub["dsr"], "p": 1.0 - rub["dsr"]},
            "default": one_sided_p(mat[lb_port.DEFAULT.label]), "rubric": rub,
            "variant_sr_annual": is_sr, "in_sample_best": best,
            "sensitivities": sensitivities(df, publication)}


def stage_b(df_full: pd.DataFrame, a: dict, holdout_start: pd.Timestamp, declaration: str | None) -> dict:
    mat = variant_matrix(df_full)
    base = variant_returns(df_full, lb_port.DEFAULT)
    mkt = market_returns(df_full)
    ho = mat[mat.index >= holdout_start]
    p2 = one_sided_p(ho[lb_port.DEFAULT.label])
    adj = holm({"P1": a["P1"]["p"], "P2": p2["p"]})
    full = one_sided_p(mat[lb_port.DEFAULT.label])
    rub = rubric("London Breakout (as coded), GBP/USD, full sample", mat, base, mkt,
                 str(holdout_start.date()), declaration)
    return {"stage": "B", "P2": p2, "holm_adjusted": adj, "full_sample_default": full,
            "verdict": verdict(adj["P1"], adj["P2"], full["mean_annual"]),
            "holdout_by_variant": {c: one_sided_p(ho[c])["sr_annual"] for c in ho},
            "in_sample_best_in_holdout": one_sided_p(ho[a["in_sample_best"]]),
            "rubric_full_sample": rub,
            "holdout_sensitivities": sensitivities(df_full[pd.to_datetime(df_full["date"]) >= holdout_start])}


# --------------------------------------------------------------------------------- entry point

def synthetic(out_dir: Path) -> dict:
    """End-to-end dry run on a seeded random walk (about 2.3 years of weekdays, hours 00-13)."""
    df = lb_data.random_walk_minutes(start="2021-01-04", days=600, seed=20260928, sd=2e-4, hours=(0, 14))
    split = pd.Timestamp("2022-09-01")
    a = stage_a(df[pd.to_datetime(df["date"]) < split].reset_index(drop=True), None, publication=None)
    b = stage_b(df, a, split, None)
    res = {"SYNTHETIC": "seeded random walk; NOT a result about any market", "stage_a": a, "stage_b": b}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "synthetic-results.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--stage", choices=["A", "B"])
    ap.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "london-breakout-synthetic")
    a = ap.parse_args(argv)
    if a.synthetic:
        res = synthetic(a.out)
        print("SYNTHETIC dry run:", res["stage_b"]["verdict"], "| written to", a.out)
        return 0
    decl = str(HERE / "declaration.json")
    if a.stage == "A":
        df = lb_data.load_real("A")  # raises LockError unless PREREG.md is sealed
        res = stage_a(df, decl)
        res["panel_sha256"] = lb_data.panel_sha256(df)
        lb_data.STAGE_A_RESULTS.parent.mkdir(exist_ok=True)
        lb_data.STAGE_A_RESULTS.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    else:
        df = lb_data.load_real("B")  # raises LockError unless the holdout was unlocked
        a_res = json.loads(lb_data.STAGE_A_RESULTS.read_text(encoding="utf-8"))
        res = stage_b(df, a_res, lb_data.HOLDOUT_START, decl)
        res["panel_sha256"] = lb_data.panel_sha256(df)
        out = HERE / "stageB" / "results.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
