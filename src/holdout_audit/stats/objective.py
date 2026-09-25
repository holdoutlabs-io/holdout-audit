"""Statistics for the declared objective "reduce drawdown at acceptable cost" (rubric v1.1, objective b).

The objective metric is the reduction in daily tail loss, dCVaR = CVaR95(benchmark) - CVaR95(strategy),
where CVaR95 is the average loss on the worst 5% of days (reported as a positive number). A
positive value means the strategy's bad days are less bad than the benchmark's. It is paired with
the reduction in maximum drawdown, dMDD = MDD(benchmark) - MDD(strategy), and with the return
shortfall the client accepts in advance.

Selection corrections reuse published constructions:
- the Deflated Sharpe construction of Bailey & Lopez de Prado (2014) is applied to dCVaR: the
  observed dCVaR is compared with the expected maximum of N skill-less trials, sqrt(V) *
  ((1-g) Z^-1(1-1/N) + g Z^-1(1-1/(N e))), using a bootstrap standard error;
- CSCV (Bailey, Borwein, Lopez de Prado & Zhu 2016) ranks variants by dCVaR in each half;
- multiple-testing adjustment of one-sided p-values as in Harvey & Liu (2015).
CVaR follows Rockafellar & Uryasev (2000), "Optimization of conditional value-at-risk", J. Risk 2(3).
Bootstrap intervals use the paired stationary bootstrap (Politis & Romano 1994), resampling the
strategy and the benchmark on the same days.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from holdout_audit.stats.bootstrap import default_block_length, stationary_bootstrap_indices
from holdout_audit.stats.pbo import PBOResult, pbo_from_stats
from holdout_audit.stats.sharpe import expected_max_sharpe

ALPHA = 0.05


def cvar(x, alpha: float = ALPHA) -> float:
    """Average loss on the worst ceil(alpha*n) periods, as a positive number (Rockafellar-Uryasev)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    k = max(1, math.ceil(alpha * x.size))
    return float(-np.partition(x, k - 1)[:k].mean())


def _cvar_rows(m: np.ndarray, alpha: float) -> np.ndarray:
    """CVaR of each row of a 2-D array."""
    k = max(1, math.ceil(alpha * m.shape[1]))
    return -np.partition(m, k - 1, axis=1)[:, :k].mean(axis=1)


def _mdd_rows(m: np.ndarray) -> np.ndarray:
    eq = np.cumprod(1.0 + m, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((m.shape[0], 1)), eq], axis=1), axis=1)[:, 1:]
    return np.max(1.0 - eq / peak, axis=1)


def max_drawdown(x) -> float:
    return float(_mdd_rows(np.asarray(x, dtype=float)[None, :])[0])


def cvar_reduction(r, b, alpha: float = ALPHA) -> float:
    return cvar(b, alpha) - cvar(r, alpha)


@dataclass(frozen=True)
class ObjectiveBootstrap:
    n_boot: int
    mean_block: float
    mdd_strategy: float
    mdd_benchmark: float
    d_mdd: float
    d_mdd_lo: float  # 5th percentile (one-sided 95% lower bound)
    cvar_strategy: float
    cvar_benchmark: float
    d_cvar: float
    d_cvar_lo: float
    d_cvar_se: float
    shortfall: float  # annualised (mean benchmark - mean strategy) * periods per year
    shortfall_hi: float  # 95th percentile
    p_d_cvar: float  # one-sided bootstrap-z p-value for dCVaR > 0


def objective_bootstrap(r, b, periods_per_year: int, n_boot: int = 1000, mean_block: float | None = None,
                        seed: int = 0, alpha: float = ALPHA) -> ObjectiveBootstrap:
    r = np.asarray(r, dtype=float)
    b = np.asarray(b, dtype=float)
    t = r.size
    mean_block = mean_block or default_block_length(t)
    idx = stationary_bootstrap_indices(t, n_boot, mean_block, np.random.default_rng(seed))
    rs, bs = r[idx], b[idx]
    d_mdd_b = _mdd_rows(bs) - _mdd_rows(rs)
    d_cvar_b = _cvar_rows(bs, alpha) - _cvar_rows(rs, alpha)
    short_b = (bs.mean(axis=1) - rs.mean(axis=1)) * periods_per_year
    mdd_r, mdd_b = max_drawdown(r), max_drawdown(b)
    c_r, c_b = cvar(r, alpha), cvar(b, alpha)
    se = float(np.std(d_cvar_b, ddof=1))
    d_cvar = c_b - c_r
    return ObjectiveBootstrap(
        n_boot=n_boot, mean_block=float(mean_block),
        mdd_strategy=mdd_r, mdd_benchmark=mdd_b, d_mdd=mdd_b - mdd_r, d_mdd_lo=float(np.percentile(d_mdd_b, 5)),
        cvar_strategy=c_r, cvar_benchmark=c_b, d_cvar=d_cvar, d_cvar_lo=float(np.percentile(d_cvar_b, 5)),
        d_cvar_se=se, shortfall=float((b.mean() - r.mean()) * periods_per_year),
        shortfall_hi=float(np.percentile(short_b, 95)),
        p_d_cvar=float(stats.norm.sf(d_cvar / se)) if se > 0 else (0.0 if d_cvar > 0 else 1.0),
    )


def variant_cvar_reductions(variants: np.ndarray, b: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """dCVaR of every column of a T x N variant matrix against benchmark ``b``."""
    return cvar(b, alpha) - _cvar_rows(np.asarray(variants, dtype=float).T, alpha)


def variant_bootstrap_p(variants: np.ndarray, b: np.ndarray, n_boot: int = 1000, mean_block: float | None = None,
                        seed: int = 0, alpha: float = ALPHA) -> np.ndarray:
    """One-sided bootstrap-z p-values for dCVaR > 0, one per variant (same resampled days for all)."""
    v = np.asarray(variants, dtype=float)
    t, n = v.shape
    mean_block = mean_block or default_block_length(t)
    idx = stationary_bootstrap_indices(t, n_boot, mean_block, np.random.default_rng(seed))
    cb = _cvar_rows(b[idx], alpha)
    out = np.empty(n)
    for k in range(n):
        d = cb - _cvar_rows(v[:, k][idx], alpha)
        se = np.std(d, ddof=1)
        point = cvar(b, alpha) - cvar(v[:, k], alpha)
        out[k] = stats.norm.sf(point / se) if se > 0 else (0.0 if point > 0 else 1.0)
    return out


def deflated_objective(theta: float, se: float, n_trials: int, var_trials: float) -> tuple[float, float]:
    """DSR construction on an arbitrary objective statistic: Phi((theta - theta0) / se), where theta0 is
    the expected maximum of ``n_trials`` null trials with dispersion ``var_trials``."""
    theta0 = expected_max_sharpe(n_trials, var_trials)
    if se <= 0:
        return (1.0 if theta > theta0 else 0.0), theta0
    return float(stats.norm.cdf((theta - theta0) / se)), theta0


def pbo_cscv_cvar(variants, benchmark, n_blocks: int = 16, alpha: float = ALPHA) -> PBOResult:
    """PBO by CSCV with dCVaR (benchmark CVaR minus variant CVaR) as the performance statistic.

    Exact: the worst-m days of a union of blocks are contained in the union of each block's own
    worst-m days, so per-block tails are precomputed once.
    """
    v = np.asarray(variants, dtype=float)
    b = np.asarray(benchmark, dtype=float)
    ok = np.all(np.isfinite(v), axis=1) & np.isfinite(b)
    v, b = v[ok], b[ok]
    t, n = v.shape
    if n < 2:
        raise ValueError("need at least 2 variants")
    L = t // n_blocks
    v, b = v[t - L * n_blocks:], b[t - L * n_blocks:]
    allm = np.concatenate([v, b[:, None]], axis=1).reshape(n_blocks, L, n + 1)  # benchmark is the last column
    half = n_blocks // 2
    m = max(1, math.ceil(alpha * half * L))
    m = min(m, L)
    tails = np.sort(allm, axis=1)[:, :m, :]  # S x m x (N+1): each block's worst m values
    combos = list(itertools.combinations(range(n_blocks), half))
    is_s = np.empty((len(combos), n))
    oos_s = np.empty((len(combos), n))
    for i, c in enumerate(combos):
        comp = [j for j in range(n_blocks) if j not in c]
        for sel, out in ((list(c), is_s), (comp, oos_s)):
            pool = tails[sel].reshape(-1, n + 1)
            worst = np.partition(pool, m - 1, axis=0)[:m].mean(axis=0)  # mean of worst m per column
            out[i] = worst[:n] - worst[n]  # dCVaR = CVaR(b) - CVaR(k) = worst_k - worst_b
    return pbo_from_stats(is_s, oos_s, n_blocks)


def yearly_drawdown_table(r: pd.Series, b: pd.Series) -> pd.DataFrame:
    df = pd.concat({"r": r, "b": b}, axis=1).dropna()
    rows = []
    for year, g in df.groupby(df.index.year):
        rows.append({"year": int(year), "mdd": max_drawdown(g["r"].to_numpy()), "mdd_benchmark": max_drawdown(g["b"].to_numpy()),
                     "cvar": cvar(g["r"].to_numpy()), "cvar_benchmark": cvar(g["b"].to_numpy())})
    out = pd.DataFrame(rows)
    out["shallower"] = out["mdd"] < out["mdd_benchmark"]
    return out


def regime_cvar_table(r: pd.Series, b: pd.Series, market: pd.Series, window: int = 21) -> pd.DataFrame:
    df = pd.concat({"r": r, "b": b, "m": market}, axis=1).dropna()
    df["vol"] = df["m"].rolling(window).std().shift(1)
    df = df.dropna()
    labels = ["low vol", "mid vol", "high vol"]
    df["regime"] = pd.qcut(df["vol"], 3, labels=labels)
    rows = []
    for lab in labels:
        g = df[df["regime"] == lab]
        rows.append({"regime": lab, "n": len(g), "d_cvar": cvar(g["b"]) - cvar(g["r"])})
    return pd.DataFrame(rows)


def holdout_cvar(r: pd.Series, b: pd.Series, split_date) -> dict:
    split_date = pd.Timestamp(split_date)
    is_, oos = r.index < split_date, r.index >= split_date
    return {"split_date": split_date, "n_is": int(is_.sum()), "n_oos": int(oos.sum()),
            "d_cvar_is": cvar(b[is_]) - cvar(r[is_]), "d_cvar_oos": cvar(b[oos]) - cvar(r[oos]),
            "d_mdd_oos": max_drawdown(b[oos].to_numpy()) - max_drawdown(r[oos].to_numpy())}
