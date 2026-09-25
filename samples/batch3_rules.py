"""Indicator Audit, Batch 3: "Strongest published evidence" (traditional markets).

Each rule is implemented as its source describes it and judged on the objective its source claims
(rubric v1.2): (c) improve Sharpe vs benchmark, or (b) reduce drawdown at acceptable cost. Monthly
rules rebalance at the last trading day of each month and hold to the next; daily returns use the
split- and dividend-adjusted close. Cash, and any borrowing implied by leverage above 1, is at 0%
(no T-bill series is a permitted instrument in these samples): this is disclosed in every report. No commodities.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from batch2_rules import month_end_mask, tri, weights_to_returns


def _month_end_weights(w_me: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    return w_me.reindex(idx).ffill().fillna(0.0)


# ------------------------------------------------------------------ 1. Moreira & Muir (2017)


def vol_managed(spy: pd.DataFrame, window: str = "1m", target: float = 0.16, cap: float = 1.5) -> pd.DataFrame:
    """Moreira, A. & Muir, T. (2017) 'Volatility-Managed Portfolios', J. Finance 72(4): at each month end set the
    equity weight to c / (last month's realised variance), with c fixed ex ante as target_vol^2 (not fitted on the
    sample), capped at `cap` (the paper's leverage-constrained version); hold until the next month end."""
    r = spy["tr"].fillna(0.0)
    idx = spy.index
    me = month_end_mask(idx)
    if window == "1m":
        rv = (r ** 2).groupby([idx.year, idx.month]).transform("mean") * 252
    else:
        rv = (r ** 2).rolling(63, min_periods=63).mean() * 252
    w = (target ** 2 / rv).clip(upper=cap)
    w_me = w[me.values].to_frame("SPY")
    w_me = w_me.where(rv[me.values].notna().to_frame("SPY").values)
    return weights_to_returns(_month_end_weights(w_me, idx), pd.DataFrame({"SPY": spy["tr"]}))


# ------------------------------------------------------------------ 2. Low volatility on sector ETFs


SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


def lowvol_sectors(prices: dict, lookback: int = 252, k: int = 3) -> pd.DataFrame:
    """Blitz, D. & van Vliet, P. (2007) 'The Volatility Effect', J. Portfolio Management 34(1); Baker, M., Bradley, B.
    & Wurgler, J. (2011) 'Benchmarks as Limits to Arbitrage', FAJ 67(1): at each month end hold, equally weighted, the
    `k` sector SPDRs with the lowest trailing `lookback`-day volatility of daily returns (a sector-level adaptation of
    the stock-level low-volatility portfolio)."""
    idx = prices["XLK"].index
    for s in SECTORS:
        idx = idx.intersection(prices[s].index)
    rets = pd.DataFrame({s: prices[s]["tr"] for s in SECTORS}).reindex(idx)
    vol = rets.rolling(lookback, min_periods=lookback).std()
    me = month_end_mask(idx)
    v = vol[me.values]
    rank = v.rank(axis=1, method="first")
    w = (rank <= k).astype(float) / k
    w = w.where(v.notna().all(axis=1), np.nan)
    return weights_to_returns(_month_end_weights(w, idx), rets)


# ------------------------------------------------------------------ 3. Low-volatility ETFs


def lowvol_etf(prices: dict, etf: str = "USMV") -> pd.DataFrame:
    """Buy-and-hold of a minimum/low-volatility ETF: USMV (MSCI USA Minimum Volatility) or SPLV (S&P 500 Low
    Volatility). The claim tested is the low-volatility anomaly's: a higher Sharpe ratio than the market."""
    p = prices[etf]
    return pd.DataFrame({"return": p["tr"].fillna(0.0), "turnover": 0.0}, index=p.index).assign(
        turnover=lambda d: np.r_[1.0, np.zeros(len(d) - 1)])


# ------------------------------------------------------------------ 4. Moskowitz, Ooi & Pedersen (2012) TSMOM


TSMOM_ASSETS = ("SPY", "EFA", "EEM", "IEF", "TLT")


def tsmom(prices: dict, lookback: int = 12, scaling: str = "vol40") -> pd.DataFrame:
    """Moskowitz, T., Ooi, Y. H. & Pedersen, L. H. (2012) 'Time Series Momentum', J. Financial Economics 104(2): at
    each month end, go long each asset whose trailing `lookback`-month return is positive and short each whose return
    is negative; size each position to 40% annualised ex-ante volatility (EWMA of squared daily returns, centre of
    mass 60 days) and average across assets ('vol40'), or use equal notional ('equal'). Equity-index and bond ETFs
    only (the paper also uses commodities and currencies, excluded here)."""
    idx = prices["SPY"].index
    for s in TSMOM_ASSETS:
        idx = idx.intersection(prices[s].index)
    rets = pd.DataFrame({s: prices[s]["tr"] for s in TSMOM_ASSETS}).reindex(idx)
    t = pd.DataFrame({s: tri(prices[s]).reindex(idx) for s in TSMOM_ASSETS})
    me = month_end_mask(idx)
    m = t[me.values]
    sig = np.sign(m / m.shift(lookback) - 1)
    n = len(TSMOM_ASSETS)
    if scaling == "vol40":
        ewvar = (rets.fillna(0.0) ** 2).ewm(com=60, min_periods=60).mean() * 252
        size = (0.40 / np.sqrt(ewvar))[me.values] / n
    else:
        size = pd.DataFrame(1.0 / n, index=m.index, columns=m.columns)
    w = (sig * size).where(sig.notna() & size.notna())
    w = w.where(w.notna().all(axis=1), np.nan)
    return weights_to_returns(_month_end_weights(w, idx), rets)


def equal_weight_hold(prices: dict, assets, start: str) -> pd.Series:
    """Benchmark: equal-weight portfolio of `assets`, rebalanced to equal weights at each month end."""
    idx = prices[assets[0]].index
    for s in assets:
        idx = idx.intersection(prices[s].index)
    idx = idx[idx >= pd.Timestamp(start)]
    rets = pd.DataFrame({s: prices[s]["tr"] for s in assets}).reindex(idx)
    w = pd.DataFrame(1.0 / len(assets), index=idx, columns=list(assets))
    return weights_to_returns(w, rets)["return"]


# ------------------------------------------------------------------ 5. Faber GTAA-style timing basket


GTAA_ASSETS = ("EEM", "VNQ", "TLT")


def gtaa(prices: dict, months: int = 10, basis: str = "price") -> pd.DataFrame:
    """Faber, M. (2007) 'A Quantitative Approach to Tactical Asset Allocation': equal thirds in each asset, each held
    only while its month-end close ('price') or total-return index ('tr') is above its `months`-month SMA; cash
    otherwise. Applied to markets not previously examined by us: EEM, VNQ, TLT."""
    idx = prices["EEM"].index
    for s in GTAA_ASSETS:
        idx = idx.intersection(prices[s].index)
    me = month_end_mask(idx)
    w = {}
    for s in GTAA_ASSETS:
        lvl = prices[s]["close"].reindex(idx) if basis == "price" else tri(prices[s]).reindex(idx)
        mc = lvl[me.values]
        ok = mc.rolling(months, min_periods=months).count() == months
        w[s] = ((mc > mc.rolling(months, min_periods=months).mean()).astype(float) / len(GTAA_ASSETS)).where(ok)
    w = pd.DataFrame(w)
    w = w.where(w.notna().all(axis=1), np.nan)
    rets = pd.DataFrame({s: prices[s]["tr"] for s in GTAA_ASSETS}).reindex(idx)
    return weights_to_returns(_month_end_weights(w, idx), rets)


# ------------------------------------------------------------------ 6. Risk parity (Asness, Frazzini & Pedersen)


def risk_parity(prices: dict, window: int = 756, bond: str = "TLT") -> pd.DataFrame:
    """Asness, C., Frazzini, A. & Pedersen, L. H. (2012) 'Leverage Aversion and Risk Parity', FAJ 68(1): at each month
    end weight stocks (SPY) and bonds inversely to their trailing `window`-day volatility (weights sum to 1, unlevered
    here); hold to the next month end. Benchmark: 60/40 SPY/bond rebalanced monthly."""
    idx = prices["SPY"].index.intersection(prices[bond].index)
    rets = pd.DataFrame({"SPY": prices["SPY"]["tr"], bond: prices[bond]["tr"]}).reindex(idx)
    inv = 1 / rets.rolling(window, min_periods=window).std()
    w = inv.div(inv.sum(axis=1), axis=0)
    me = month_end_mask(idx)
    return weights_to_returns(_month_end_weights(w[me.values], idx), rets)


def sixty_forty_monthly(prices: dict, bond: str, start: str) -> pd.Series:
    idx = prices["SPY"].index.intersection(prices[bond].index)
    idx = idx[idx >= pd.Timestamp(start)]
    rets = pd.DataFrame({"SPY": prices["SPY"]["tr"], bond: prices[bond]["tr"]}).reindex(idx)
    w = pd.DataFrame({"SPY": 0.6, bond: 0.4}, index=idx)
    return weights_to_returns(w, rets)["return"]


# ------------------------------------------------------------------ grids


GRIDS = {
    "vol_managed": dict(window=["1m", "3m"], target=[0.12, 0.16], cap=[1.0, 1.5, 2.0]),
    "lowvol_sectors": dict(lookback=[63, 126, 252], k=[2, 3, 4]),
    "lowvol_etf": dict(etf=["USMV", "SPLV"]),
    "tsmom": dict(lookback=[1, 3, 6, 12], scaling=["vol40", "equal"]),
    "gtaa": dict(months=[6, 8, 10, 12], basis=["price", "tr"]),
    "risk_parity": dict(window=[63, 126, 252, 756], bond=["TLT", "IEF"]),
}
DEFAULTS = {
    "vol_managed": dict(window="1m", target=0.16, cap=1.5), "lowvol_sectors": dict(lookback=252, k=3),
    "lowvol_etf": dict(etf="USMV"), "tsmom": dict(lookback=12, scaling="vol40"), "gtaa": dict(months=10, basis="price"),
    "risk_parity": dict(window=756, bond="TLT"),
}


def label(cell: dict) -> str:
    return "|".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in cell.items())


def cells(rule: str) -> list[dict]:
    g = GRIDS[rule]
    return [dict(zip(g, v)) for v in itertools.product(*g.values())]


def n_variants(rule: str) -> int:
    return len(cells(rule))


def run_cell(rule: str, c: dict, data: dict) -> pd.DataFrame:
    if rule == "vol_managed":
        return vol_managed(data["SPY"], c["window"], c["target"], c["cap"])
    if rule == "lowvol_sectors":
        return lowvol_sectors(data, c["lookback"], c["k"])
    if rule == "lowvol_etf":
        return lowvol_etf(data, c["etf"])
    if rule == "tsmom":
        return tsmom(data, c["lookback"], c["scaling"])
    if rule == "gtaa":
        return gtaa(data, c["months"], c["basis"])
    if rule == "risk_parity":
        return risk_parity(data, c["window"], c["bond"])
    raise KeyError(rule)


def run_grid(rule: str, data: dict) -> dict[str, pd.DataFrame]:
    return {label(c): run_cell(rule, c, data) for c in cells(rule)}
