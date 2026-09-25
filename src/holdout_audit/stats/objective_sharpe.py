"""Statistics for the declared objective "improve Sharpe vs benchmark" (rubric v1.2, objective c).

The objective metric is the Sharpe-ratio improvement dSR = SR(strategy) - SR(benchmark), computed per
period and reported annualised. Inference uses the paired stationary bootstrap (Politis & Romano 1994):
strategy and benchmark are resampled on the same days, as in the bootstrap test of Sharpe-ratio
differences of Ledoit, O. & Wolf, M. (2008), "Robust performance hypothesis testing with the Sharpe
ratio", Journal of Empirical Finance 15(5), 850-859 (see also Jobson & Korkie 1981; Memmel 2003).
Selection corrections reuse the DSR construction (Bailey & Lopez de Prado 2014), CSCV (Bailey,
Borwein, Lopez de Prado & Zhu 2016) and one-sided multiple-testing adjustment (Harvey & Liu 2015).
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


def _sr(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    sd = x.std(ddof=1) if x.size > 2 else 0.0
    return float(x.mean() / sd) if sd > 0 else 0.0


def _sr_rows(m: np.ndarray) -> np.ndarray:
    sd = m.std(axis=1, ddof=1)
    return np.where(sd > 0, m.mean(axis=1) / np.where(sd > 0, sd, 1.0), 0.0)


def delta_sharpe(r, b) -> float:
    """Per-period Sharpe(strategy) - Sharpe(benchmark)."""
    return _sr(np.asarray(r, float)) - _sr(np.asarray(b, float))


@dataclass(frozen=True)
class SharpeBootstrap:
    n_boot: int
    mean_block: float
    sr_strategy: float  # annualised
    sr_benchmark: float  # annualised
    d_sr: float  # annualised
    d_sr_lo: float  # annualised 5th percentile
    d_sr_se: float  # annualised
    p_d_sr: float  # one-sided bootstrap-z p-value for dSR > 0


def sharpe_bootstrap(r, b, periods_per_year: int, n_boot: int = 1000, mean_block: float | None = None,
                     seed: int = 0) -> SharpeBootstrap:
    r, b = np.asarray(r, float), np.asarray(b, float)
    t = r.size
    mean_block = mean_block or default_block_length(t)
    idx = stationary_bootstrap_indices(t, n_boot, mean_block, np.random.default_rng(seed))
    d = _sr_rows(r[idx]) - _sr_rows(b[idx])
    q = math.sqrt(periods_per_year)
    point = delta_sharpe(r, b)
    se = float(np.std(d, ddof=1))
    return SharpeBootstrap(n_boot, float(mean_block), _sr(r) * q, _sr(b) * q, point * q,
                           float(np.percentile(d, 5)) * q, se * q,
                           float(stats.norm.sf(point / se)) if se > 0 else (0.0 if point > 0 else 1.0))


def variant_delta_sharpes(variants: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Per-period dSR of every column of a T x N matrix."""
    return _sr_rows(np.asarray(variants, float).T) - _sr(np.asarray(b, float))


def variant_bootstrap_p(variants: np.ndarray, b: np.ndarray, n_boot: int = 1000, mean_block: float | None = None,
                        seed: int = 0) -> np.ndarray:
    v, b = np.asarray(variants, float), np.asarray(b, float)
    t, n = v.shape
    mean_block = mean_block or default_block_length(t)
    idx = stationary_bootstrap_indices(t, n_boot, mean_block, np.random.default_rng(seed))
    sb = _sr_rows(b[idx])
    out = np.empty(n)
    for k in range(n):
        d = _sr_rows(v[:, k][idx]) - sb
        se = np.std(d, ddof=1)
        point = delta_sharpe(v[:, k], b)
        out[k] = stats.norm.sf(point / se) if se > 0 else (0.0 if point > 0 else 1.0)
    return out


def pbo_cscv_delta_sharpe(variants, benchmark, n_blocks: int = 16) -> PBOResult:
    """PBO by CSCV with dSR (variant Sharpe minus benchmark Sharpe on the same half) as the statistic."""
    v = np.asarray(variants, float)
    b = np.asarray(benchmark, float)
    ok = np.all(np.isfinite(v), axis=1) & np.isfinite(b)
    m = np.concatenate([v[ok], b[ok][:, None]], axis=1)
    t, n1 = m.shape
    L = t // n_blocks
    m = m[t - L * n_blocks:]
    blocks = m.reshape(n_blocks, L, n1)
    bsum, bsq = blocks.sum(axis=1), (blocks * blocks).sum(axis=1)
    combos = list(itertools.combinations(range(n_blocks), n_blocks // 2))
    sel = np.zeros((len(combos), n_blocks))
    for i, c in enumerate(combos):
        sel[i, list(c)] = 1.0

    def sharpes(w):
        cnt = (w @ np.full(n_blocks, float(L)))[:, None]
        mean = (w @ bsum) / cnt
        var = ((w @ bsq) - cnt * mean * mean) / np.maximum(cnt - 1, 1)
        sd = np.sqrt(np.maximum(var, 0.0))
        return np.where(sd > 0, mean / np.where(sd > 0, sd, 1.0), 0.0)

    is_s, oos_s = sharpes(sel), sharpes(1.0 - sel)
    return pbo_from_stats(is_s[:, :-1] - is_s[:, -1:], oos_s[:, :-1] - oos_s[:, -1:], n_blocks)


def holdout_delta_sharpe(r: pd.Series, b: pd.Series, split_date, periods_per_year: int) -> dict:
    split_date = pd.Timestamp(split_date)
    q = math.sqrt(periods_per_year)
    i, o = r.index < split_date, r.index >= split_date
    return {"split_date": split_date, "n_is": int(i.sum()), "n_oos": int(o.sum()),
            "d_sr_is": delta_sharpe(r[i].to_numpy(), b[i].to_numpy()) * q,
            "d_sr_oos": delta_sharpe(r[o].to_numpy(), b[o].to_numpy()) * q}


def yearly_sharpe_table(r: pd.Series, b: pd.Series, periods_per_year: int) -> pd.DataFrame:
    q = math.sqrt(periods_per_year)
    df = pd.concat({"r": r, "b": b}, axis=1).dropna()
    rows = [{"year": int(y), "sr": _sr(g["r"].to_numpy()) * q, "sr_benchmark": _sr(g["b"].to_numpy()) * q}
            for y, g in df.groupby(df.index.year) if len(g) > 20]
    out = pd.DataFrame(rows)
    out["higher"] = out["sr"] > out["sr_benchmark"]
    return out


def regime_delta_sharpe(r: pd.Series, b: pd.Series, market: pd.Series, periods_per_year: int, window: int = 21) -> pd.DataFrame:
    q = math.sqrt(periods_per_year)
    df = pd.concat({"r": r, "b": b, "m": market}, axis=1).dropna()
    df["vol"] = df["m"].rolling(window).std().shift(1)
    df = df.dropna()
    labels = ["low vol", "mid vol", "high vol"]
    df["regime"] = pd.qcut(df["vol"], 3, labels=labels)
    return pd.DataFrame([{"regime": lab, "n": int((df["regime"] == lab).sum()),
                          "d_sr": delta_sharpe(df.loc[df["regime"] == lab, "r"].to_numpy(),
                                               df.loc[df["regime"] == lab, "b"].to_numpy()) * q} for lab in labels])
