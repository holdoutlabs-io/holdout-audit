"""Indicator Audit, Batch 2: "Classic market rules" (traditional markets only).

Ten published or traditional rules, each implemented as its source describes it, long or in cash
(cash earns 0%: see the preregistration). Signals are evaluated at the daily close (monthly rules at
the last trading day of the month) and held from that close to the next; there is no look-ahead
beyond the trading calendar itself.

Instruments are limited to the equity and bond ETFs and the equity-index signal listed in
samples/data/fetch.py (the samples' instrument policy). No commodities, metals or astronomical features.
The variant grids were preregistered and sealed before any market data were fetched.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from strategies import apply_positions, rsi_wilder, sma


# ------------------------------------------------------------------ helpers


def month_end_mask(idx: pd.DatetimeIndex) -> pd.Series:
    """True on the last trading day of each calendar month present in the index."""
    s = pd.Series(idx, index=idx)
    return s.groupby([idx.year, idx.month]).transform("max").eq(s)


def held_to_positions(held: pd.Series) -> pd.Series:
    """Convert "exposed on return-day d" into positions decided at the previous close."""
    return held.shift(-1).fillna(0.0)


def tri(px: pd.DataFrame) -> pd.Series:
    """Total-return index from the daily total return."""
    return (1 + px["tr"].fillna(0.0)).cumprod()


def weights_to_returns(w: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
    """Target weights decided at close t, held over t+1; turnover = sum of |weight changes| (drift ignored)."""
    w = w.fillna(0.0)
    held = w.shift(1).fillna(0.0)
    r = (held * rets.reindex(w.index).fillna(0.0)).sum(axis=1)
    to = held.diff().abs().sum(axis=1).fillna(held.abs().sum(axis=1))
    return pd.DataFrame({"return": r, "turnover": to})


# ------------------------------------------------------------------ 1. Faber (2007) 10-month SMA timing


def faber(px: pd.DataFrame, months: int = 10) -> pd.DataFrame:
    """Faber, M. (2007) 'A Quantitative Approach to Tactical Asset Allocation', J. Wealth Management 9(4):
    at each month end, long if the monthly close is above its `months`-month SMA, otherwise cash."""
    me = month_end_mask(px.index)
    mc = px.loc[me, "close"]
    sig = (mc > mc.rolling(months, min_periods=months).mean()).astype(float).where(mc.rolling(months).count() == months)
    pos = sig.reindex(px.index).ffill().fillna(0.0)
    return apply_positions(pos, px["tr"])


# ------------------------------------------------------------------ 2. Siegel 200-day SMA filter


def sma_filter(px: pd.DataFrame, n: int = 200, band: float = 0.01) -> pd.DataFrame:
    """Siegel, J. (2002) 'Stocks for the Long Run', 3rd ed., ch. 17: buy when the close rises `band` above its
    n-day SMA, sell to cash when it falls `band` below (hysteresis between)."""
    c = px["close"].to_numpy()
    m = sma(px["close"], n).to_numpy()
    pos = np.zeros(c.size)
    state = 0.0
    for i in range(c.size):
        if np.isnan(m[i]):
            continue
        if c[i] > m[i] * (1 + band):
            state = 1.0
        elif c[i] < m[i] * (1 - band):
            state = 0.0
        pos[i] = state
    return apply_positions(pd.Series(pos, index=px.index), px["tr"])


# ------------------------------------------------------------------ 3. Halloween / Sell in May


def halloween(px: pd.DataFrame, entry_month: int = 11, exit_month: int = 4) -> pd.DataFrame:
    """Bouman, S. & Jacobsen, B. (2002) 'The Halloween Indicator, Sell in May and Go Away: Another Puzzle',
    American Economic Review 92(5): invested from the start of `entry_month` through the end of `exit_month`
    (wrapping the year end), cash otherwise."""
    months = set(((entry_month - 1 + k) % 12) + 1 for k in range((exit_month - entry_month) % 12 + 1))
    held = pd.Series(px.index.month.isin(list(months)).astype(float), index=px.index)
    return apply_positions(held_to_positions(held), px["tr"])


# ------------------------------------------------------------------ 4. Turn of the month


def turn_of_month(px: pd.DataFrame, last_days: int = 1, first_days: int = 3) -> pd.DataFrame:
    """Lakonishok, J. & Smidt, S. (1988) RFS 1(4); McConnell, J. & Xu, W. (2008) 'Equity Returns at the Turn of
    the Month', FAJ 64(2): invested over the last `last_days` and the first `first_days` trading days of each month."""
    idx = px.index
    g = pd.Series(1, index=idx).groupby([idx.year, idx.month])
    k_first = g.cumcount() + 1
    k_last = g.cumcount(ascending=False) + 1
    held = ((k_first <= first_days) | (k_last <= last_days)).astype(float)
    return apply_positions(held_to_positions(held), px["tr"])


# ------------------------------------------------------------------ 5. Antonacci dual momentum (GEM)


def dual_momentum(prices: dict, lookback: int = 12, safe: str = "AGG") -> pd.DataFrame:
    """Antonacci, G. (2014) 'Dual Momentum Investing' (McGraw-Hill), Global Equities Momentum: at each month end,
    if SPY's `lookback`-month total return is positive (absolute momentum; the book uses T-bills, see the
    preregistration), hold the better of SPY and EFA over that lookback (relative momentum), else the bond ETF."""
    spy, efa, bond = prices["SPY"], prices["EFA"], prices[safe]
    idx = spy.index.intersection(efa.index).intersection(bond.index)
    t = pd.DataFrame({"SPY": tri(spy).reindex(idx), "EFA": tri(efa).reindex(idx), safe: tri(bond).reindex(idx)})
    me = month_end_mask(idx)
    m = t[me.values]
    look = m / m.shift(lookback) - 1
    choice = pd.Series(np.where(look["SPY"] > 0, np.where(look["SPY"] >= look["EFA"], "SPY", "EFA"), safe), index=m.index)
    choice = choice.where(look.notna().all(axis=1))
    w = pd.DataFrame(0.0, index=m.index, columns=t.columns)
    for c in t.columns:
        w[c] = (choice == c).astype(float)
    w = w.where(choice.notna())
    w = w.reindex(idx).ffill().fillna(0.0)
    rets = pd.DataFrame({"SPY": spy["tr"], "EFA": efa["tr"], safe: bond["tr"]}).reindex(idx)
    return weights_to_returns(w, rets)


# ------------------------------------------------------------------ 6. Sector momentum rotation


SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


def sector_momentum(prices: dict, lookback: int = 12, skip: int = 1, top: int = 3) -> pd.DataFrame:
    """Moskowitz, T. & Grinblatt, M. (1999) 'Do Industries Explain Momentum?', J. Finance 54(4); Faber, M. (2010)
    'Relative Strength Strategies for Investing': at each month end rank the nine original sector SPDRs by their
    total return from month m-skip-lookback to m-skip and hold the top `top` equally weighted until the next month end."""
    idx = prices["XLK"].index
    for s in SECTORS:
        idx = idx.intersection(prices[s].index)
    t = pd.DataFrame({s: tri(prices[s]).reindex(idx) for s in SECTORS})
    me = month_end_mask(idx)
    m = t[me.values]
    score = m.shift(skip) / m.shift(skip + lookback) - 1
    ranks = score.rank(axis=1, ascending=False, method="first")
    w = (ranks <= top).astype(float) / top
    w = w.where(score.notna().all(axis=1), np.nan)
    w = w.reindex(idx).ffill().fillna(0.0)
    rets = pd.DataFrame({s: prices[s]["tr"] for s in SECTORS}).reindex(idx)
    return weights_to_returns(w, rets)


# ------------------------------------------------------------------ 7. VIX stretches (Connors & Alvarez)


def vix_stretch(spy: pd.DataFrame, vix: pd.DataFrame, stretch: float = 0.05, days: int = 3,
                exit_rsi: float = 65.0) -> pd.DataFrame:
    """Connors, L. & Alvarez, C. (2009) 'Short Term Trading Strategies That Work', 'VIX Stretches': buy SPY at the
    close when SPY is above its 200-day SMA and the VIX has closed at least `stretch` above its 10-day SMA for
    `days` or more consecutive days; exit at the close when SPY's RSI(2) exceeds `exit_rsi`. The VIX is used
    only as a signal and is never traded."""
    v = vix["close"].reindex(spy.index).ffill()
    stretched = (v >= (1 + stretch) * sma(v, 10)).astype(int)
    run = stretched.groupby((stretched != stretched.shift()).cumsum()).cumsum() * stretched
    trend = spy["close"] > sma(spy["close"], 200)
    r2 = rsi_wilder(spy["close"], 2)
    entry = (trend & (run >= days)).to_numpy()
    ex = (r2 > exit_rsi).to_numpy()
    pos = np.zeros(len(spy))
    state = 0.0
    for i in range(len(spy)):
        if state == 1.0 and ex[i]:
            state = 0.0
        elif state == 0.0 and entry[i]:
            state = 1.0
        pos[i] = state
    return apply_positions(pd.Series(pos, index=spy.index), spy["tr"])


# ------------------------------------------------------------------ 8. Golden cross (long / cash)


def golden_cross(px: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """The 50/200-day golden cross, long while SMA(fast) > SMA(slow), cash otherwise (as in sample audit 1)."""
    c = px["close"]
    pos = (sma(c, fast) > sma(c, slow)).astype(float).where(sma(c, slow).notna()).fillna(0.0)
    return apply_positions(pos, px["tr"])


# ------------------------------------------------------------------ 9. 60/40 rebalancing bands


def sixty_forty(stock: pd.DataFrame, bond: pd.DataFrame, band: float = 0.05, check: str = "monthly",
                start: str | None = None) -> pd.DataFrame:
    """Jaconetti, C., Kinniry, F. & Zilbering, Y. (2010) 'Best Practices for Portfolio Rebalancing', Vanguard: hold
    60% SPY / 40% IEF, letting weights drift, and rebalance to 60/40 on a check day (daily or month end) whenever the
    stock weight is more than `band` away from 60%. Turnover counts both legs."""
    idx = stock.index.intersection(bond.index)
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start)]
    rs, rb = stock["tr"].reindex(idx).fillna(0.0).to_numpy(), bond["tr"].reindex(idx).fillna(0.0).to_numpy()
    me = month_end_mask(idx).to_numpy()
    ws, out, to = 0.6, np.zeros(idx.size), np.zeros(idx.size)
    to[0] = 1.0  # initial purchase
    for i in range(idx.size):
        if i > 0:
            port = ws * rs[i] + (1 - ws) * rb[i]
            out[i] = port
            ws = ws * (1 + rs[i]) / (1 + port)
        if (check == "daily" or me[i]) and abs(ws - 0.6) > band:
            to[i] += 2 * abs(ws - 0.6)
            ws = 0.6
    return pd.DataFrame({"return": out, "turnover": to}, index=idx)


def buy_and_hold_60_40(stock: pd.DataFrame, bond: pd.DataFrame, start: str) -> pd.Series:
    """The benchmark for the 60/40 audit: 60/40 bought on the start date and never rebalanced."""
    return sixty_forty(stock, bond, band=10.0, check="daily", start=start)["return"]


# ------------------------------------------------------------------ 10. Connors RSI(2) with exit variants


def rsi2(px: pd.DataFrame, entry: float = 5.0, exit_rule: str = "sma5") -> pd.DataFrame:
    """Connors, L. & Alvarez, C. (2009) 'Short Term Trading Strategies That Work', RSI(2): buy at the close when
    the close is above its 200-day SMA and RSI(2) is below `entry`; exit at the close when the exit rule fires:
    close above its 5-day SMA (the book's exit), close above its 10-day SMA, RSI(2) above 70, or an up close."""
    c = px["close"]
    r2 = rsi_wilder(c, 2)
    ent = ((c > sma(c, 200)) & (r2 < entry)).to_numpy()
    ex = {"sma5": c > sma(c, 5), "sma10": c > sma(c, 10), "rsi70": r2 > 70, "upclose": c > c.shift(1)}[exit_rule].to_numpy()
    pos = np.zeros(len(c))
    state = 0.0
    for i in range(len(c)):
        if state == 1.0 and ex[i]:
            state = 0.0
        elif state == 0.0 and ent[i]:
            state = 1.0
        pos[i] = state
    return apply_positions(pd.Series(pos, index=px.index), px["tr"])


# ------------------------------------------------------------------ preregistered grids


MONTHS = {"Jan": 1, "Mar": 3, "Apr": 4, "May": 5, "Oct": 10, "Nov": 11}
GRIDS = {
    "faber": dict(months=[6, 8, 10, 12]),
    "sma_filter": dict(n=[100, 150, 200, 250], band=[0.0, 0.01]),
    "halloween": dict(entry=["Oct", "Nov"], exit=["Mar", "Apr", "May"]),
    "turn_of_month": dict(last=[1, 2], first=[2, 3, 4]),
    "dual_momentum": dict(lookback=[6, 9, 12], safe=["AGG", "IEF"]),
    "sector_momentum": dict(lookback=[6, 9, 12], skip=[0, 1], top=[1, 3]),
    "vix_stretch": dict(stretch=[0.03, 0.05, 0.10], days=[2, 3, 4], exit=[65, 75]),
    "golden_cross": dict(fast=[20, 30, 50, 70, 100], slow=[100, 150, 200, 250, 300]),
    "sixty_forty": dict(band=[0.01, 0.03, 0.05, 0.10, 0.20], check=["daily", "monthly"]),
    "rsi2": dict(entry=[2, 5, 10], exit=["sma5", "sma10", "rsi70", "upclose"]),
}
DEFAULTS = {
    "faber": dict(months=10), "sma_filter": dict(n=200, band=0.01), "halloween": dict(entry="Nov", exit="Apr"),
    "turn_of_month": dict(last=1, first=3), "dual_momentum": dict(lookback=12, safe="AGG"),
    "sector_momentum": dict(lookback=12, skip=1, top=3), "vix_stretch": dict(stretch=0.05, days=3, exit=65),
    "golden_cross": dict(fast=50, slow=200), "sixty_forty": dict(band=0.05, check="monthly"),
    "rsi2": dict(entry=5, exit="sma5"),
}


def label(cell: dict) -> str:
    return "|".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in cell.items())


def cells(rule: str) -> list[dict]:
    g = GRIDS[rule]
    out = [dict(zip(g, vals)) for vals in itertools.product(*g.values())]
    if rule == "golden_cross":
        out = [c for c in out if c["fast"] < c["slow"]]
    return out


def n_variants(rule: str) -> int:
    return len(cells(rule))


def run_cell(rule: str, cell: dict, data: dict, start: str | None = None) -> pd.DataFrame:
    """`data` maps symbols to price frames; single-asset rules use data['asset'] (and 'VIX' for vix_stretch)."""
    c = cell
    if rule == "faber":
        return faber(data["asset"], c["months"])
    if rule == "sma_filter":
        return sma_filter(data["asset"], c["n"], c["band"])
    if rule == "halloween":
        return halloween(data["asset"], MONTHS[c["entry"]], MONTHS[c["exit"]])
    if rule == "turn_of_month":
        return turn_of_month(data["asset"], c["last"], c["first"])
    if rule == "dual_momentum":
        return dual_momentum(data, c["lookback"], c["safe"])
    if rule == "sector_momentum":
        return sector_momentum(data, c["lookback"], c["skip"], c["top"])
    if rule == "vix_stretch":
        return vix_stretch(data["asset"], data["VIX"], c["stretch"], c["days"], float(c["exit"]))
    if rule == "golden_cross":
        return golden_cross(data["asset"], c["fast"], c["slow"])
    if rule == "sixty_forty":
        return sixty_forty(data["SPY"], data["IEF"], c["band"], c["check"], start)
    if rule == "rsi2":
        return rsi2(data["asset"], float(c["entry"]), c["exit"])
    raise KeyError(rule)


def run_grid(rule: str, data: dict, start: str | None = None) -> dict[str, pd.DataFrame]:
    return {label(c): run_cell(rule, c, data, start) for c in cells(rule)}
