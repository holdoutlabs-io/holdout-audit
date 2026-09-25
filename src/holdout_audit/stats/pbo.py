"""Probability of Backtest Overfitting via Combinatorially Symmetric Cross-Validation (CSCV).

Reference
---------
Bailey, D. H., Borwein, J. M., Lopez de Prado, M. & Zhu, Q. J. (2016).
"The Probability of Backtest Overfitting." Journal of Computational Finance 20(4), 39-69.

Algorithm (Section 2 of the paper):
1. Stack the T x N matrix M of variant returns (rows = time, columns = variants) and cut it
   row-wise into S disjoint, equal, contiguous blocks (S even).
2. For every one of the C(S, S/2) ways of choosing S/2 blocks as the in-sample set J (the
   complement is the out-of-sample set J-bar):
   a. compute the performance statistic (Sharpe ratio) of every variant on J and on J-bar;
   b. take n* = argmax in-sample;
   c. compute the relative rank w of n* among the out-of-sample statistics, w in (0, 1);
   d. record the logit lambda = ln(w / (1 - w)).
3. PBO = share of combinations with lambda <= 0, i.e. where the in-sample winner is at or
   below the out-of-sample median.

We also return the paper's companion diagnostics: the out-of-sample Sharpe of the IS winner
for every split (performance degradation), and the probability that it loses (OOS SR < 0).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PBOResult:
    pbo: float
    n_splits: int
    n_blocks: int
    n_variants: int
    logits: np.ndarray
    is_sr_best: np.ndarray  # IS Sharpe of the IS winner, per split
    oos_sr_best: np.ndarray  # OOS Sharpe of the IS winner, per split
    prob_oos_loss: float  # P(OOS SR of IS winner < 0)
    degradation_slope: float  # OLS slope of OOS SR on IS SR (paper Fig. 4)


def _block_sharpes(sums: np.ndarray, sumsq: np.ndarray, counts: np.ndarray) -> np.ndarray:
    n = counts[:, None]
    mean = sums / n
    var = (sumsq - n * mean * mean) / np.maximum(n - 1, 1)
    sd = np.sqrt(np.maximum(var, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(sd > 0, mean / sd, 0.0)
    return out


def pbo_cscv(variant_returns, n_blocks: int = 16, max_splits: int | None = None, seed: int = 0) -> PBOResult:
    """Compute PBO by CSCV with the Sharpe ratio as performance statistic.

    ``variant_returns``: array-like T x N (N >= 2). Rows with any NaN are dropped. When the
    number of combinations exceeds ``max_splits`` a seeded random subset is used.
    """
    m = np.asarray(variant_returns, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        raise ValueError("need a T x N matrix with at least 2 variants")
    m = m[np.all(np.isfinite(m), axis=1)]
    if n_blocks % 2 or n_blocks < 2:
        raise ValueError("n_blocks must be an even number >= 2")
    t, n = m.shape
    t_use = (t // n_blocks) * n_blocks
    if t_use < 2 * n_blocks:
        raise ValueError("too few observations for the requested number of blocks")
    m = m[t - t_use:]  # drop the oldest remainder rows so blocks are equal
    blocks = m.reshape(n_blocks, t_use // n_blocks, n)
    bsum = blocks.sum(axis=1)  # S x N
    bsq = (blocks * blocks).sum(axis=1)
    bcount = np.full(n_blocks, t_use // n_blocks, dtype=float)

    combos = list(itertools.combinations(range(n_blocks), n_blocks // 2))
    if max_splits is not None and len(combos) > max_splits:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(combos), size=max_splits, replace=False)
        combos = [combos[i] for i in sorted(idx)]
    sel = np.zeros((len(combos), n_blocks))
    for i, c in enumerate(combos):
        sel[i, list(c)] = 1.0
    osel = 1.0 - sel

    is_sr = _block_sharpes(sel @ bsum, sel @ bsq, sel @ bcount)  # C x N
    oos_sr = _block_sharpes(osel @ bsum, osel @ bsq, osel @ bcount)

    return pbo_from_stats(is_sr, oos_sr, n_blocks)


def pbo_from_stats(is_stat: np.ndarray, oos_stat: np.ndarray, n_blocks: int) -> PBOResult:
    """PBO from per-split in-sample and out-of-sample statistics (C x N, larger is better)."""
    n_splits, n = is_stat.shape
    best = np.argmax(is_stat, axis=1)
    rows = np.arange(n_splits)
    oos_best = oos_stat[rows, best]
    # Relative rank in (0,1): rank 1..N of n* among OOS values (average rank for ties) / (N+1).
    below = (oos_stat < oos_best[:, None]).sum(axis=1)
    ties = (oos_stat == oos_best[:, None]).sum(axis=1)
    rank = below + (ties + 1) / 2.0
    w = rank / (n + 1.0)
    logits = np.log(w / (1.0 - w))
    is_best = is_stat[rows, best]
    slope = float(np.polyfit(is_best, oos_best, 1)[0]) if np.std(is_best) > 0 else float("nan")
    return PBOResult(
        pbo=float(np.mean(logits <= 0)),
        n_splits=n_splits,
        n_blocks=n_blocks,
        n_variants=n,
        logits=logits,
        is_sr_best=is_best,
        oos_sr_best=oos_best,
        prob_oos_loss=float(np.mean(oos_best < 0)),
        degradation_slope=slope,
    )
