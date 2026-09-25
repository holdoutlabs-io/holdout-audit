"""Stationary bootstrap, White's Reality Check, Hansen's SPA and bootstrap drawdown distributions.

References
----------
- Politis, D. N. & Romano, J. P. (1994). "The Stationary Bootstrap." JASA 89(428), 1303-1313.
- White, H. (2000). "A Reality Check for Data Snooping." Econometrica 68(5), 1097-1126.
- Hansen, P. R. (2005). "A Test for Superior Predictive Ability." Journal of Business &
  Economic Statistics 23(4), 365-380.

Performance convention: ``d[t, k] = r_k[t] - benchmark[t]`` so that *larger is better*. The
null hypothesis of both tests is that no variant beats the benchmark in expectation,
H0: max_k E[d_k] <= 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def default_block_length(t: int) -> float:
    """Rule-of-thumb mean block length T^(1/3), floored at 5 (documented in METHODS.md)."""
    return max(5.0, round(t ** (1.0 / 3.0)))


def stationary_bootstrap_indices(t: int, n_boot: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """n_boot x t matrix of resampled indices (Politis & Romano 1994), wrapping circularly."""
    p = 1.0 / mean_block
    idx = np.empty((n_boot, t), dtype=np.int64)
    idx[:, 0] = rng.integers(0, t, size=n_boot)
    new_start = rng.random((n_boot, t)) < p
    starts = rng.integers(0, t, size=(n_boot, t))
    for j in range(1, t):
        idx[:, j] = np.where(new_start[:, j], starts[:, j], (idx[:, j - 1] + 1) % t)
    return idx


def _boot_means(d: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """n_boot x K matrix of bootstrap means of the columns of d."""
    return np.stack([d[ib].mean(axis=0) for ib in idx])


@dataclass(frozen=True)
class RealityCheckResult:
    n_variants: int
    n_boot: int
    mean_block: float
    best_index: int
    best_mean_excess: float  # per period
    p_reality_check: float  # White (2000)
    p_spa: float  # Hansen (2005), consistent version
    p_spa_lower: float
    p_spa_upper: float


def reality_check_spa(variant_returns, benchmark=None, n_boot: int = 1000, mean_block: float | None = None,
                      seed: int = 0) -> RealityCheckResult:
    """White's Reality Check and Hansen's SPA test over all variants against ``benchmark``.

    ``variant_returns``: T x K (or a length-T vector for a single strategy).
    ``benchmark``: length-T returns, or None for a zero benchmark.
    """
    r = np.asarray(variant_returns, dtype=float)
    if r.ndim == 1:
        r = r[:, None]
    b = np.zeros(r.shape[0]) if benchmark is None else np.asarray(benchmark, dtype=float)
    d = r - b[:, None]
    d = d[np.all(np.isfinite(d), axis=1)]
    t, k = d.shape
    mean_block = mean_block or default_block_length(t)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(t, n_boot, mean_block, rng)
    dbar = d.mean(axis=0)
    boot = _boot_means(d, idx)  # B x K
    sqt = math.sqrt(t)

    # White's Reality Check (non-studentised).
    v = sqt * dbar.max()
    v_star = (sqt * (boot - dbar)).max(axis=1)
    p_rc = float(np.mean(v_star >= v))

    # Hansen's SPA (studentised, with recentring).
    omega = np.sqrt(np.mean((sqt * (boot - dbar)) ** 2, axis=0))
    omega = np.where(omega > 0, omega, np.finfo(float).eps)
    t_spa = max(0.0, float((sqt * dbar / omega).max()))
    thresh = -np.sqrt(omega**2 / t * 2.0 * math.log(math.log(t)))
    g_c = np.where(dbar >= thresh, dbar, 0.0)
    g_l = np.maximum(dbar, 0.0)
    g_u = dbar

    def _p(g: np.ndarray) -> float:
        z = sqt * (boot - g) / omega
        ts = np.maximum(z.max(axis=1), 0.0)
        return float(np.mean(ts >= t_spa))

    best = int(np.argmax(dbar))
    return RealityCheckResult(
        n_variants=k,
        n_boot=n_boot,
        mean_block=float(mean_block),
        best_index=best,
        best_mean_excess=float(dbar[best]),
        p_reality_check=p_rc,
        p_spa=_p(g_c),
        p_spa_lower=_p(g_l),
        p_spa_upper=_p(g_u),
    )


def max_drawdown(returns) -> float:
    """Maximum peak-to-trough decline of the compounded equity curve (a positive fraction)."""
    r = np.asarray(returns, dtype=float)
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float(np.max(1.0 - eq / peak)) if r.size else 0.0


def drawdown_series(returns) -> np.ndarray:
    r = np.asarray(returns, dtype=float)
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return 1.0 - eq / peak


@dataclass(frozen=True)
class DrawdownResult:
    realized: float
    boot: np.ndarray
    percentiles: dict  # {5: .., 50: .., 95: ..}
    prob_worse_than_realized: float


def bootstrap_drawdowns(returns, n_boot: int = 1000, mean_block: float | None = None, seed: int = 0) -> DrawdownResult:
    """Distribution of the maximum drawdown over re-orderings that keep short-range dependence."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    t = r.size
    mean_block = mean_block or default_block_length(t)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(t, n_boot, mean_block, rng)
    sims = r[idx]
    eq = np.cumprod(1.0 + sims, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((n_boot, 1)), eq], axis=1), axis=1)[:, 1:]
    mdd = np.max(1.0 - eq / peak, axis=1)
    realized = max_drawdown(r)
    return DrawdownResult(
        realized=realized,
        boot=mdd,
        percentiles={q: float(np.percentile(mdd, q)) for q in (5, 25, 50, 75, 95)},
        prob_worse_than_realized=float(np.mean(mdd > realized)),
    )
