"""Multiple-testing haircut of the Sharpe ratio (Harvey & Liu 2015).

Reference
---------
Harvey, C. R. & Liu, Y. (2015). "Backtesting." Journal of Portfolio Management 42(1), 13-28.
See also Harvey, C. R., Liu, Y. & Zhu, H. (2016). "... and the Cross-Section of Expected
Returns." Review of Financial Studies 29(1), 5-68 (the t > 3 hurdle).

Procedure: convert the annualised Sharpe ratio to a t-statistic, t = SR_annual * sqrt(years);
take the two-sided p-value; adjust it for the number of strategies tried; map the adjusted
p-value back to a t-statistic and hence to a "haircut" Sharpe ratio.

- Bonferroni and Sidak need only the number of tests N.
- Holm (step-down) and BHY (Benjamini-Hochberg-Yekutieli, step-up, valid under arbitrary
  dependence) need the whole vector of p-values, so they are computed only when the variant
  return matrix is supplied. Harvey & Liu fill in unobserved tests by simulation; we do not
  invent unobserved p-values and report Bonferroni as the conservative bound instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


def t_stat_from_sharpe(sr_annual: float, years: float) -> float:
    return sr_annual * math.sqrt(years)


def p_two_sided(t: float) -> float:
    return float(2.0 * stats.norm.sf(abs(t)))


def p_one_sided(t: float) -> float:
    """P(T >= t) under the null: evidence *for* the strategy only (rubric v1.1)."""
    return float(stats.norm.sf(t))


def sharpe_from_p(p: float, years: float, sign: float = 1.0, one_sided: bool = False) -> float:
    """Annualised SR whose (two-sided, or one-sided) p-value equals ``p`` over ``years``."""
    p = min(max(p, 1e-300), 1.0)
    t = float(stats.norm.isf(p if one_sided else p / 2.0))
    return math.copysign(max(t, 0.0) / math.sqrt(years), sign)


def bonferroni(p: float, n: int) -> float:
    return min(1.0, p * n)


def sidak(p: float, n: int) -> float:
    return float(1.0 - (1.0 - p) ** n)


def holm_adjusted(pvals) -> np.ndarray:
    """Holm step-down adjusted p-values, returned in the original order."""
    p = np.asarray(pvals, dtype=float)
    n = p.size
    order = np.argsort(p)
    adj_sorted = np.minimum(1.0, (n - np.arange(n)) * p[order])
    adj_sorted = np.maximum.accumulate(adj_sorted)
    out = np.empty(n)
    out[order] = adj_sorted
    return out


def bhy_adjusted(pvals) -> np.ndarray:
    """Benjamini-Hochberg-Yekutieli step-up adjusted p-values (arbitrary dependence)."""
    p = np.asarray(pvals, dtype=float)
    n = p.size
    c = float(np.sum(1.0 / np.arange(1, n + 1)))
    order = np.argsort(p)
    ranks = np.arange(1, n + 1)
    raw = p[order] * n * c / ranks
    adj_sorted = np.minimum.accumulate(raw[::-1])[::-1]
    adj_sorted = np.minimum(adj_sorted, 1.0)
    out = np.empty(n)
    out[order] = adj_sorted
    return out


@dataclass(frozen=True)
class HaircutResult:
    sr_annual: float
    years: float
    n_tests: int
    t_stat: float
    p_single: float
    p_bonferroni: float
    p_sidak: float
    p_holm: float | None
    p_bhy: float | None
    sr_haircut_bonferroni: float
    sr_haircut_bhy: float | None
    haircut_pct_bonferroni: float

    @property
    def p_adjusted(self) -> float:
        """The adjusted p-value used for grading: BHY when available, else Bonferroni."""
        return self.p_bhy if self.p_bhy is not None else self.p_bonferroni


def haircut_sharpe(sr_annual: float, years: float, n_tests: int, all_sr_annual=None, index: int | None = None,
                   one_sided: bool = False) -> HaircutResult:
    """Harvey-Liu haircut for one strategy chosen from ``n_tests`` tries.

    If ``all_sr_annual`` (annualised SRs of every variant tried, same sample length) and the
    ``index`` of the chosen one are given, Holm and BHY are computed from the real p-values.
    """
    n_tests = max(int(n_tests), 1)
    pfun = p_one_sided if one_sided else p_two_sided
    t = t_stat_from_sharpe(sr_annual, years)
    p = pfun(t)
    pb = bonferroni(p, n_tests)
    ps = sidak(p, n_tests)
    p_holm = p_bhy = None
    sr_bhy = None
    if all_sr_annual is not None and index is not None:
        allp = np.array([pfun(t_stat_from_sharpe(s, years)) for s in all_sr_annual])
        if allp.size == n_tests:
            p_holm = float(holm_adjusted(allp)[index])
            p_bhy = float(bhy_adjusted(allp)[index])
            sr_bhy = sharpe_from_p(p_bhy, years, sr_annual, one_sided)
    sr_b = sharpe_from_p(pb, years, sr_annual, one_sided)
    hc = 1.0 - sr_b / sr_annual if sr_annual > 0 else 1.0
    return HaircutResult(
        sr_annual=sr_annual,
        years=years,
        n_tests=n_tests,
        t_stat=t,
        p_single=p,
        p_bonferroni=pb,
        p_sidak=ps,
        p_holm=p_holm,
        p_bhy=p_bhy,
        sr_haircut_bonferroni=sr_b,
        sr_haircut_bhy=sr_bhy,
        haircut_pct_bonferroni=hc,
    )
