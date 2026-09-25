"""Sharpe-ratio inference: standard errors, PSR, DSR, minimum track record length.

References
----------
- Lo, A. W. (2002). "The Statistics of Sharpe Ratios." Financial Analysts Journal 58(4), 36-52.
- Mertens, E. (2002). "Comments on variance of the IID estimator in Lo (2002)." Working paper.
- Bailey, D. H. & Lopez de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier."
  Journal of Risk 15(2), 3-44.  (Probabilistic Sharpe Ratio, Minimum Track Record Length.)
- Bailey, D. H. & Lopez de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for
  Selection Bias, Backtest Overfitting and Non-Normality." Journal of Portfolio Management
  40(5), 94-107.

Conventions: all Sharpe ratios in this module are *per period* (e.g. daily) unless a
function name says ``annual``. Returns are simple returns and the risk-free rate is taken
as zero unless the caller subtracts it first. Kurtosis is the *raw* (non-excess) fourth
standardised moment, as in the papers (a normal distribution has kurtosis 3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

EULER_GAMMA = 0.5772156649015329


def _clean(returns) -> np.ndarray:
    r = np.asarray(returns, dtype=float).ravel()
    r = r[np.isfinite(r)]
    if r.size < 3:
        raise ValueError("need at least 3 finite returns")
    return r


def sharpe(returns) -> float:
    """Per-period Sharpe ratio mean/std (ddof=1). Returns 0.0 for a zero-variance series."""
    r = _clean(returns)
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def moments(returns) -> tuple[float, float]:
    """(skewness, raw kurtosis) of the returns, population estimators as used by the papers."""
    r = _clean(returns)
    if r.std() == 0:
        return 0.0, 3.0
    return float(stats.skew(r, bias=True)), float(stats.kurtosis(r, fisher=False, bias=True))


def se_sharpe_iid_normal(sr: float, t: int) -> float:
    """Lo (2002) eq. (8): asymptotic SE of the per-period SR for IID normal returns.

    SE = sqrt((1 + SR^2 / 2) / T).
    """
    return math.sqrt((1.0 + 0.5 * sr * sr) / t)


def se_sharpe_nonnormal(sr: float, t: int, skew: float, kurt: float) -> float:
    """SE of the per-period SR for IID but non-normal returns (Mertens 2002).

    SE = sqrt((1 - skew*SR + (kurt-1)/4 * SR^2) / (T - 1)).  With skew=0, kurt=3 this is
    Lo's formula up to the T vs T-1 denominator.
    """
    v = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    return math.sqrt(max(v, 1e-12) / (t - 1))


def lo_annualization_factor(returns, q: int, max_lag: int | None = None) -> float:
    """Lo (2002) eq. (15): eta(q) so that SR_annual = eta(q) * SR_period under serial correlation.

    eta(q) = q / sqrt(q + 2 * sum_{k=1}^{q-1} (q-k) rho_k).  For IID returns eta(q) = sqrt(q).
    Autocorrelations beyond ``max_lag`` (default 10) are set to zero, which keeps the estimate
    stable for daily data with q = 252.
    """
    r = _clean(returns)
    max_lag = 10 if max_lag is None else max_lag
    x = r - r.mean()
    denom = float((x * x).sum())
    acc = 0.0
    for k in range(1, min(q, max_lag + 1)):
        rho = float((x[k:] * x[:-k]).sum() / denom) if denom > 0 else 0.0
        acc += (q - k) * rho
    inner = q + 2.0 * acc
    if inner <= 0:
        return math.sqrt(q)
    return q / math.sqrt(inner)


def probabilistic_sharpe_ratio(sr: float, sr_benchmark: float, t: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """PSR (Bailey & Lopez de Prado 2012, eq. 11): P(true SR > SR*) given the estimate.

    PSR = Phi( (SR - SR*) * sqrt(T - 1) / sqrt(1 - skew*SR + (kurt-1)/4 * SR^2) ).
    Per-period SRs throughout.
    """
    v = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    z = (sr - sr_benchmark) * math.sqrt(t - 1) / math.sqrt(max(v, 1e-12))
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, var_trials: float) -> float:
    """Bailey & Lopez de Prado (2014), eq. (6): E[max SR] over N independent trials with true SR 0.

    SR0 = sqrt(V[SR_n]) * ((1-gamma) * Z^-1(1 - 1/N) + gamma * Z^-1(1 - 1/(N e))).
    Returns 0 for N <= 1.
    """
    if n_trials <= 1:
        return 0.0
    n = float(n_trials)
    z1 = stats.norm.ppf(1.0 - 1.0 / n)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n * math.e))
    return float(math.sqrt(var_trials) * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe_ratio(sr: float, t: int, skew: float, kurt: float, n_trials: int, var_trials: float) -> tuple[float, float]:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014): PSR against the expected max SR of N trials.

    Returns (DSR, SR0) with SR0 the per-period deflation benchmark.
    """
    sr0 = expected_max_sharpe(n_trials, var_trials)
    return probabilistic_sharpe_ratio(sr, sr0, t, skew, kurt), sr0


def min_track_record_length(sr: float, sr_benchmark: float, skew: float, kurt: float, prob: float = 0.95) -> float:
    """MinTRL (Bailey & Lopez de Prado 2012, eq. 13), in periods; inf if SR <= benchmark."""
    if sr <= sr_benchmark:
        return math.inf
    z = stats.norm.ppf(prob)
    v = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    return float(1.0 + v * (z / (sr - sr_benchmark)) ** 2)


@dataclass(frozen=True)
class SharpeSummary:
    periods_per_year: int
    n_obs: int
    mean: float
    std: float
    sr: float  # per period
    sr_annual: float  # sqrt(q) scaling
    sr_annual_lo: float  # Lo (2002) autocorrelation-adjusted scaling
    se_iid: float  # per period, Lo (2002)
    se_nonnormal: float  # per period, Mertens (2002)
    se_annual: float  # non-normal SE * sqrt(q)
    skew: float
    kurt: float
    psr_zero: float  # P(true SR > 0)
    min_trl_years: float

    @property
    def ci95_annual(self) -> tuple[float, float]:
        return (self.sr_annual - 1.96 * self.se_annual, self.sr_annual + 1.96 * self.se_annual)


def summarize(returns, periods_per_year: int) -> SharpeSummary:
    r = _clean(returns)
    t = r.size
    sr = sharpe(r)
    sk, ku = moments(r)
    q = periods_per_year
    se_n = se_sharpe_nonnormal(sr, t, sk, ku)
    mtrl = min_track_record_length(sr, 0.0, sk, ku)
    return SharpeSummary(
        periods_per_year=q,
        n_obs=t,
        mean=float(r.mean()),
        std=float(r.std(ddof=1)),
        sr=sr,
        sr_annual=sr * math.sqrt(q),
        sr_annual_lo=sr * lo_annualization_factor(r, q),
        se_iid=se_sharpe_iid_normal(sr, t),
        se_nonnormal=se_n,
        se_annual=se_n * math.sqrt(q),
        skew=sk,
        kurt=ku,
        psr_zero=probabilistic_sharpe_ratio(sr, 0.0, t, sk, ku),
        min_trl_years=mtrl / q if math.isfinite(mtrl) else math.inf,
    )
