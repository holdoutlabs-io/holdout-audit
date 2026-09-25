"""Public sample strategies used to demonstrate the audit (statistical illustrations only).

Execution convention for every rule: the signal is computed from the close of day t and the
position is held over day t+1 (no look-ahead). Turnover on day t+1 is |pos_t - pos_{t-1}|.
Out of the market the strategy earns zero (no interest), which slightly understates cash.

Only SPY and BTC prices are used. No other data and no calendar or astronomical features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def load_prices(path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    df["tr"] = (df["close"] + df["dividend"]) / df["close"].shift(1) - 1.0  # total return
    return df


def apply_positions(pos: pd.Series, ret: pd.Series) -> pd.DataFrame:
    """pos: desired position decided at the close of each day (0..1)."""
    held = pos.shift(1).fillna(0.0)
    return pd.DataFrame({"return": held * ret, "turnover": held.diff().abs().fillna(held.abs())})


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def rsi_wilder(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


# ------------------------------------------------------------------ 1. golden cross


GC_FAST = (20, 30, 50, 70, 100)
GC_SLOW = (100, 150, 200, 250, 300)


def golden_cross(px: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    c = px["close"]
    pos = (sma(c, fast) > sma(c, slow)).astype(float).where(sma(c, slow).notna())
    return apply_positions(pos.fillna(0.0), px["tr"])


def golden_cross_grid(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {f"fast={f}|slow={s}": golden_cross(px, f, s) for f in GC_FAST for s in GC_SLOW if f < s}


# ------------------------------------------------------------------ 2. RSI(2) mean reversion


RSI_N = (2, 3, 4)
RSI_ENTRY = (5, 10, 15, 20, 25)
RSI_EXIT_SMA = (5, 10)
RSI_TREND = ("on", "off")


def rsi_reversion(px: pd.DataFrame, n: int, entry: float, exit_sma: int, trend: str) -> pd.DataFrame:
    """Connors-style: enter long at the close when RSI(n) < entry (and, with the trend filter,
    close > 200-day SMA); exit at the close when close > SMA(exit_sma)."""
    c = px["close"].to_numpy()
    r = rsi_wilder(px["close"], n).to_numpy()
    s200 = sma(px["close"], 200).to_numpy()
    sx = sma(px["close"], exit_sma).to_numpy()
    pos = np.zeros(len(c))
    inpos = False
    for i in range(len(c)):
        if np.isnan(s200[i]) or np.isnan(sx[i]):
            continue
        if inpos:
            if c[i] > sx[i]:
                inpos = False
        elif r[i] < entry and (trend == "off" or c[i] > s200[i]):
            inpos = True
        pos[i] = 1.0 if inpos else 0.0
    return apply_positions(pd.Series(pos, index=px.index), px["tr"])


def rsi_grid(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {f"rsi={n}|entry={e}|exit={x}|trend={t}": rsi_reversion(px, n, e, x, t)
            for n in RSI_N for e in RSI_ENTRY for x in RSI_EXIT_SMA for t in RSI_TREND}


# ------------------------------------------------------------------ 3. BTC trend / momentum


BTC_LOOKBACK = (10, 20, 30, 50, 100, 150, 200)
BTC_SIGNAL = ("sma", "roc")


def btc_trend(px: pd.DataFrame, signal: str, lookback: int) -> pd.DataFrame:
    c = px["close"]
    if signal == "sma":
        ref = sma(c, lookback)
        pos = (c > ref).astype(float).where(ref.notna())
    else:
        roc = c / c.shift(lookback) - 1
        pos = (roc > 0).astype(float).where(roc.notna())
    return apply_positions(pos.fillna(0.0), px["tr"])


def btc_grid(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {f"signal={s}|lookback={n}": btc_trend(px, s, n) for s in BTC_SIGNAL for n in BTC_LOOKBACK}


# ------------------------------------------------------------------ 4. Supertrend (TradingView built-in)
#
# A port of TradingView's Pine `ta.supertrend(factor, atrPeriod)` and its built-in "Supertrend
# Strategy", which enters long when the direction turns up and short when it turns down. The
# variant grid and the chosen settings were preregistered and sealed before any run on BTC data;
# see samples/prereg/04-btc-supertrend/.

ST_ATR = (7, 10, 14)
ST_MULT = (2.0, 2.5, 3.0, 3.5, 4.0)
ST_MODE = ("long_short", "long_flat")


def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.atr: RMA (alpha = 1/n, seeded with the simple mean of the first n values) of the true range."""
    prev_close = np.concatenate([[np.nan], close[:-1]])
    tr = np.where(np.isnan(prev_close), high - low,
                  np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]))
    out = np.full(tr.size, np.nan)
    if tr.size >= n:
        out[n - 1] = tr[:n].mean()
        for i in range(n, tr.size):
            out[i] = out[i - 1] + (tr[i] - out[i - 1]) / n
    return out


def supertrend_direction(high, low, close, atr_period: int, factor: float) -> np.ndarray:
    """Pine ta.supertrend direction: -1 = uptrend, +1 = downtrend (TradingView's convention), NaN in warm-up."""
    high, low, close = (np.asarray(x, dtype=float) for x in (high, low, close))
    atr = atr_wilder(high, low, close, atr_period)
    src = (high + low) / 2.0
    n = close.size
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    st = np.full(n, np.nan)
    direction = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(atr[i]):
            continue
        ub, lb = src[i] + factor * atr[i], src[i] - factor * atr[i]
        pu = upper[i - 1] if i > 0 and not np.isnan(upper[i - 1]) else 0.0  # Pine nz()
        pl = lower[i - 1] if i > 0 and not np.isnan(lower[i - 1]) else 0.0
        pc = close[i - 1] if i > 0 else np.nan
        lower[i] = lb if (lb > pl or pc < pl) else pl
        upper[i] = ub if (ub < pu or pc > pu) else pu
        if i == 0 or np.isnan(atr[i - 1]):
            d = 1.0
        elif st[i - 1] == pu:
            d = -1.0 if close[i] > upper[i] else 1.0
        else:
            d = 1.0 if close[i] < lower[i] else -1.0
        direction[i] = d
        st[i] = lower[i] if d == -1.0 else upper[i]
    return direction


def supertrend(px: pd.DataFrame, atr_period: int, factor: float, mode: str) -> pd.DataFrame:
    """Position decided at the daily close: +1 in an uptrend; in a downtrend -1 (long_short, the
    TradingView built-in strategy) or 0 (long_flat). Held over the next day (close to close)."""
    d = supertrend_direction(px["high"], px["low"], px["close"], atr_period, factor)
    up = np.where(np.isnan(d), 0.0, (d == -1.0).astype(float))
    pos = up if mode == "long_flat" else np.where(np.isnan(d), 0.0, np.where(d == -1.0, 1.0, -1.0))
    return apply_positions(pd.Series(pos, index=px.index), px["tr"])


def supertrend_grid(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {f"atr={a}|mult={m:g}|mode={md}": supertrend(px, a, m, md)
            for a in ST_ATR for m in ST_MULT for md in ST_MODE}
