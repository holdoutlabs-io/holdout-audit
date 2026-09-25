"""Holdout degradation, period and regime stability, cost sensitivity and parameter surfaces.

These are descriptive robustness diagnostics rather than single published tests. The ideas
follow standard practice described in:
- Lopez de Prado, M. (2018). Advances in Financial Machine Learning, ch. 11-12 (Wiley).
- Bailey, Borwein, Lopez de Prado & Zhu (2014). "Pseudo-Mathematics and Financial
  Charlatanism." Notices of the AMS 61(5), 458-471 (holdout discipline).
- Pardo, R. (2008). The Evaluation and Optimization of Trading Strategies, 2nd ed. (Wiley)
  (parameter plateaus versus isolated peaks).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from holdout_audit.stats.sharpe import se_sharpe_nonnormal, moments


def _sr(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if x.size < 3:
        return float("nan")
    sd = x.std(ddof=1)
    return float(x.mean() / sd) if sd > 0 else 0.0


# ------------------------------------------------------------------ holdout


@dataclass(frozen=True)
class HoldoutResult:
    split_date: pd.Timestamp
    n_is: int
    n_oos: int
    sr_is_annual: float
    sr_oos_annual: float
    ratio: float  # OOS / IS annualised SR (nan when IS <= 0)
    p_oos_consistent: float  # two-sided p that the OOS SR comes from the IS SR's sampling distribution


def holdout_degradation(returns: pd.Series, periods_per_year: int, split_date=None, holdout_frac: float = 0.3) -> HoldoutResult:
    """Compare in-sample and holdout Sharpe ratios.

    The consistency p-value treats the IS SR as the truth and asks how surprising the OOS SR
    is given the OOS sample's sampling error (non-normal SE, Mertens 2002).
    """
    r = returns.dropna()
    if split_date is None:
        split_date = r.index[int(len(r) * (1 - holdout_frac))]
    split_date = pd.Timestamp(split_date)
    is_r = r[r.index < split_date].to_numpy()
    oos_r = r[r.index >= split_date].to_numpy()
    q = math.sqrt(periods_per_year)
    sr_is, sr_oos = _sr(is_r), _sr(oos_r)
    sk, ku = moments(oos_r) if oos_r.size >= 3 else (0.0, 3.0)
    se = se_sharpe_nonnormal(sr_is, max(oos_r.size, 3), sk, ku)
    p = float(2 * stats.norm.sf(abs(sr_oos - sr_is) / se)) if se > 0 else float("nan")
    ratio = sr_oos / sr_is if sr_is > 0 else float("nan")
    return HoldoutResult(split_date, is_r.size, oos_r.size, sr_is * q, sr_oos * q, ratio, p)


# ------------------------------------------------------------------ periods / regimes


def yearly_table(returns: pd.Series, periods_per_year: int) -> pd.DataFrame:
    r = returns.dropna()
    rows = []
    for year, g in r.groupby(r.index.year):
        x = g.to_numpy()
        rows.append({
            "year": int(year),
            "n": x.size,
            "return": float(np.prod(1 + x) - 1),
            "sr_annual": _sr(x) * math.sqrt(periods_per_year) if x.size >= 3 else float("nan"),
            "exposure": float(np.mean(x != 0)),
        })
    return pd.DataFrame(rows)


def yearly_excess_table(returns: pd.Series, benchmark: pd.Series, periods_per_year: int) -> pd.DataFrame:
    """Per calendar year: strategy and benchmark compounded returns, their difference, and the
    annualised Sharpe of the daily excess returns."""
    df = pd.concat({"r": returns, "b": benchmark}, axis=1).dropna()
    rows = []
    for year, g in df.groupby(df.index.year):
        x, b = g["r"].to_numpy(), g["b"].to_numpy()
        ret, bret = float(np.prod(1 + x) - 1), float(np.prod(1 + b) - 1)
        rows.append({
            "year": int(year), "n": x.size, "return": ret, "benchmark": bret, "excess": ret - bret,
            "excess_sr_annual": _sr(x - b) * math.sqrt(periods_per_year) if x.size >= 3 else float("nan"),
            "exposure": float(np.mean(x != 0)),
        })
    return pd.DataFrame(rows)


def vol_regime_table(returns: pd.Series, market: pd.Series, periods_per_year: int, window: int = 21) -> pd.DataFrame:
    """Strategy statistics by tercile of trailing market volatility.

    Volatility is the ``window``-day realised standard deviation of the market's returns,
    lagged one period so that the regime label is known before the return it classifies.
    Tercile cut points use the full sample (a descriptive split, not a trading rule).
    """
    df = pd.concat({"r": returns, "m": market}, axis=1).dropna()
    vol = df["m"].rolling(window).std().shift(1)
    df = df.assign(vol=vol).dropna()
    labels = ["low vol", "mid vol", "high vol"]
    df["regime"] = pd.qcut(df["vol"], 3, labels=labels)
    rows = []
    for lab in labels:
        x = df.loc[df["regime"] == lab, "r"].to_numpy()
        rows.append({
            "regime": lab,
            "n": x.size,
            "ann_return": float(np.mean(x) * periods_per_year),
            "sr_annual": _sr(x) * math.sqrt(periods_per_year),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ costs


@dataclass(frozen=True)
class CostResult:
    grid_bps: list
    sr_annual: list
    ann_return: list
    breakeven_bps: float  # cost per unit turnover at which the annualised mean return hits 0
    turnover_per_year: float


def cost_sensitivity(gross: pd.Series, turnover: pd.Series, periods_per_year: int,
                     grid_bps=(0, 1, 2, 5, 10, 20, 50)) -> CostResult:
    """Net returns r - turnover * cost for a grid of one-way costs (in basis points per unit traded)."""
    df = pd.concat({"r": gross, "to": turnover}, axis=1).dropna()
    r, to = df["r"].to_numpy(), df["to"].to_numpy()
    srs, rets = [], []
    for c in grid_bps:
        net = r - to * c / 1e4
        srs.append(_sr(net) * math.sqrt(periods_per_year))
        rets.append(float(net.mean() * periods_per_year))
    mean_to = to.mean()
    be = float(r.mean() / mean_to * 1e4) if mean_to > 0 else float("inf")
    return CostResult(list(grid_bps), srs, rets, be, float(mean_to * periods_per_year))


# ------------------------------------------------------------------ parameter surface


_PARAM_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([^|;,]+)")


def parse_params(name: str) -> dict:
    """Parse a variant column name like ``fast=50|slow=200`` into {"fast": 50, "slow": 200}."""
    out = {}
    for k, v in _PARAM_RE.findall(name):
        v = v.strip()
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


@dataclass(frozen=True)
class SurfaceResult:
    params: list  # parameter names
    table: pd.DataFrame  # one row per variant: params + sr_annual
    chosen: str
    chosen_sr: float
    best_sr: float
    median_sr: float
    share_positive: float
    neighbor_ratio: float  # mean SR of the chosen variant's grid neighbours / chosen SR
    rank_of_chosen: int


def parameter_surface(variants: pd.DataFrame, chosen: str, periods_per_year: int, values: dict | None = None) -> SurfaceResult | None:
    """Sharpe surface over a parameter grid encoded in the variant column names.

    Neighbours are variants that differ from the chosen one in exactly one parameter by one
    grid step. A ratio near 1 indicates a plateau; a ratio near 0 or negative an isolated peak.
    """
    parsed = {c: parse_params(str(c)) for c in variants.columns}
    if not all(parsed.values()):
        return None
    names: list[str] = []
    for p in parsed.values():  # keep the order in which parameters appear in the column names
        names += [k for k in p if k not in names]
    rows = []
    for c in variants.columns:
        v = values[c] if values is not None else _sr(variants[c].to_numpy()) * math.sqrt(periods_per_year)
        rows.append({**parsed[c], "variant": c, "sr_annual": v})  # "sr_annual" holds the metric (objective b: dCVaR)
    tab = pd.DataFrame(rows)
    levels = {n: sorted(tab[n].dropna().unique().tolist(), key=lambda v: (isinstance(v, str), v)) for n in names}
    ch = parsed[chosen]
    neigh = []
    for _, row in tab.iterrows():
        diff = [n for n in names if row[n] != ch.get(n)]
        if len(diff) != 1:
            continue
        n = diff[0]
        lv = levels[n]
        if abs(lv.index(row[n]) - lv.index(ch[n])) == 1:
            neigh.append(row["sr_annual"])
    chosen_sr = float(tab.loc[tab["variant"] == chosen, "sr_annual"].iloc[0])
    nr = float(np.mean(neigh) / chosen_sr) if neigh and chosen_sr > 0 else float("nan")
    ranks = tab["sr_annual"].rank(ascending=False, method="min")
    return SurfaceResult(
        params=names,
        table=tab,
        chosen=chosen,
        chosen_sr=chosen_sr,
        best_sr=float(tab["sr_annual"].max()),
        median_sr=float(tab["sr_annual"].median()),
        share_positive=float((tab["sr_annual"] > 0).mean()),
        neighbor_ratio=nr,
        rank_of_chosen=int(ranks[tab["variant"] == chosen].iloc[0]),
    )
