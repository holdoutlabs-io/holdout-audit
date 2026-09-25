"""Indicator Audit, Batch 1: ports of TradingView's built-in strategies "as they ship".

Every built-in strategy below is a stop-and-reverse system: it enters long on its long signal and
short on its short signal, and otherwise keeps the current position. We port the signal logic from
Pine (ta.* functions reimplemented to Pine's definitions) and apply one execution convention to all:

- the signal is evaluated at the daily close t and the position is held from close t to close t+1;
- TradingView fills market orders at the next bar's open and stop orders intrabar. We use
  close-to-close returns and treat stop entries as triggered at the signal bar's close. These are
  documented deviations from TradingView's broker emulator, fixed in the sealed preregistration;
- before the first signal the position is 0;
- ``long_flat`` maps every short to flat (a common long-only variant).

The variant grids were preregistered and sealed before any run on market data.
Only SPY and BTC are used (the samples' instrument policy). No calendar or astronomical features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies import apply_positions, supertrend_direction

MODES = ("long_short", "long_flat")


# ------------------------------------------------------------------ Pine primitives


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def ema(x: pd.Series, n: int) -> pd.Series:
    """Pine ta.ema: alpha = 2/(n+1), seeded with the SMA of the first n values."""
    v = x.to_numpy(dtype=float)
    out = np.full(v.size, np.nan)
    a = 2.0 / (n + 1.0)
    first = np.flatnonzero(~np.isnan(v))
    if first.size == 0 or v.size - first[0] < n:
        return pd.Series(out, index=x.index)
    s = first[0]
    out[s + n - 1] = v[s:s + n].mean()
    for i in range(s + n, v.size):
        out[i] = a * v[i] + (1 - a) * out[i - 1]
    return pd.Series(out, index=x.index)


def rma(x: pd.Series, n: int) -> pd.Series:
    """Pine ta.rma: alpha = 1/n, seeded with the SMA of the first n values."""
    v = x.to_numpy(dtype=float)
    out = np.full(v.size, np.nan)
    first = np.flatnonzero(~np.isnan(v))
    if first.size == 0 or v.size - first[0] < n:
        return pd.Series(out, index=x.index)
    s = first[0]
    out[s + n - 1] = v[s:s + n].mean()
    for i in range(s + n, v.size):
        out[i] = out[i - 1] + (v[i] - out[i - 1]) / n
    return pd.Series(out, index=x.index)


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up, dn = rma(d.clip(lower=0), n), rma((-d).clip(lower=0), n)
    r = 100 - 100 / (1 + up / dn)
    r = r.where(dn != 0, 100.0).where(up != 0, 0.0)
    return r.where(up.notna() & dn.notna())


def stdev_pop(x: pd.Series, n: int) -> pd.Series:
    """Pine ta.stdev (biased/population by default)."""
    return x.rolling(n, min_periods=n).std(ddof=0)


def true_range(px: pd.DataFrame) -> pd.Series:
    pc = px["close"].shift(1)
    tr = pd.concat([px["high"] - px["low"], (px["high"] - pc).abs(), (px["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.where(pc.notna(), px["high"] - px["low"])


def crossover(a: pd.Series, b) -> pd.Series:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b) -> pd.Series:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a < b) & (a.shift(1) >= b.shift(1))


def _positions(long_sig: pd.Series, short_sig: pd.Series, mode: str) -> pd.Series:
    """Stop-and-reverse: +1 after a long signal, -1 after a short signal, else keep; 0 before the first."""
    state = pd.Series(np.nan, index=long_sig.index)
    state[short_sig.fillna(False).astype(bool)] = -1.0
    state[long_sig.fillna(False).astype(bool)] = 1.0  # if both fire on one bar, Pine's later entry wins; see each rule
    pos = state.ffill().fillna(0.0)
    return pos.clip(lower=0.0) if mode == "long_flat" else pos


def _run(px: pd.DataFrame, long_sig, short_sig, mode: str) -> pd.DataFrame:
    return apply_positions(_positions(long_sig, short_sig, mode), px["tr"])


# ------------------------------------------------------------------ the ten built-in strategies


def macd_strategy(px, fast=12, slow=26, signal=9, mode="long_short"):
    """'MACD Strategy': delta = MACD - EMA(MACD, signal); long on crossover(delta, 0), short on crossunder."""
    m = ema(px["close"], fast) - ema(px["close"], slow)
    delta = m - ema(m, signal)
    return _run(px, crossover(delta, 0.0), crossunder(delta, 0.0), mode)


def rsi_strategy(px, length=14, oversold=30, overbought=70, mode="long_short"):
    """'RSI Strategy': long on crossover(RSI, oversold), short on crossunder(RSI, overbought)."""
    r = rsi(px["close"], length)
    return _run(px, crossover(r, float(oversold)), crossunder(r, float(overbought)), mode)


def bollinger_strategy(px, length=20, mult=2.0, mode="long_short"):
    """'Bollinger Bands Strategy': long (stop at the lower band) when close crosses above the lower band;
    short (stop at the upper band) when close crosses below the upper band."""
    c = px["close"]
    basis = sma(c, length)
    dev = mult * stdev_pop(c, length)
    return _run(px, crossover(c, basis - dev), crossunder(c, basis + dev), mode)


def ma2line_strategy(px, fast=9, slow=18, mode="long_short"):
    """'MovingAvg2Line Cross': SMA(fast) crossing over / under SMA(slow)."""
    f, s = sma(px["close"], fast), sma(px["close"], slow)
    return _run(px, crossover(f, s), crossunder(f, s), mode)


def psar_direction(high: np.ndarray, low: np.ndarray, close: np.ndarray, start: float, inc: float, mx: float) -> np.ndarray:
    """Port of the 'Parabolic SAR Strategy' state machine: +1 uptrend, -1 downtrend, NaN on bar 0."""
    n = close.size
    out = np.full(n, np.nan)
    uptrend = None
    ep = sar = next_sar = np.nan
    af = start
    for i in range(1, n):
        first = False
        sar = next_sar
        if i == 1:
            if close[1] > close[0]:
                uptrend, ep, prev_sar, prev_ep = True, high[1], low[0], high[1]
            else:
                uptrend, ep, prev_sar, prev_ep = False, low[1], high[0], low[1]
            first = True
            sar = prev_sar + start * (prev_ep - prev_sar)
        if uptrend:
            if sar > low[i]:
                first, uptrend, sar, ep, af = True, False, max(ep, high[i]), low[i], start
        else:
            if sar < high[i]:
                first, uptrend, sar, ep, af = True, True, min(ep, low[i]), high[i], start
        if not first:
            if uptrend and high[i] > ep:
                ep, af = high[i], min(af + inc, mx)
            elif (not uptrend) and low[i] < ep:
                ep, af = low[i], min(af + inc, mx)
        if uptrend:
            sar = min(sar, low[i - 1])
            if i > 1:
                sar = min(sar, low[i - 2])
        else:
            sar = max(sar, high[i - 1])
            if i > 1:
                sar = max(sar, high[i - 2])
        next_sar = sar + af * (ep - sar)
        out[i] = 1.0 if uptrend else -1.0
    return out


def psar_strategy(px, start=0.02, increment=0.02, maximum=0.2, mode="long_short"):
    """'Parabolic SAR Strategy': stop-and-reverse at the SAR; the position follows the SAR trend."""
    d = pd.Series(psar_direction(px["high"].to_numpy(float), px["low"].to_numpy(float), px["close"].to_numpy(float),
                                 start, increment, maximum), index=px.index)
    return _run(px, d == 1.0, d == -1.0, mode)


def stoch_slow_strategy(px, length=14, oversold=20, overbought=80, smooth_k=3, smooth_d=3, mode="long_short"):
    """'Stochastic Slow Strategy': k = SMA(stoch, 3), d = SMA(k, 3); long on crossover(k, d) with k < oversold,
    short on crossunder(k, d) with k > overbought."""
    hh = px["high"].rolling(length, min_periods=length).max()
    ll = px["low"].rolling(length, min_periods=length).min()
    stoch = 100 * (px["close"] - ll) / (hh - ll)
    k = sma(stoch, smooth_k)
    d = sma(k, smooth_d)
    return _run(px, crossover(k, d) & (k < oversold), crossunder(k, d) & (k > overbought), mode)


def channel_breakout_strategy(px, length=5, mode="long_short"):
    """'Channel BreakOut Strategy': stop entries at the highest high / lowest low of the last `length` bars.
    Port: long when today's high exceeds the prior bar's channel high, short when today's low breaks the prior
    channel low; if both happen on one bar, the direction of the close relative to the channel midpoint decides."""
    up = px["high"].rolling(length, min_periods=length).max().shift(1)
    dn = px["low"].rolling(length, min_periods=length).min().shift(1)
    lb, sb = px["high"] > up, px["low"] < dn
    both = lb & sb
    mid = (up + dn) / 2
    lb = lb & ~(both & (px["close"] < mid))
    sb = sb & ~(both & (px["close"] >= mid))
    return _run(px, lb, sb, mode)


def keltner_strategy(px, length=20, mult=2.0, atr_length=10, mode="long_short"):
    """'Keltner Channels Strategy' (EMA basis, ATR bands): long after close crosses above the upper band,
    short after close crosses below the lower band (stop entries treated as filled at the signal close)."""
    c = px["close"]
    ma = ema(c, length)
    rng = rma(true_range(px), atr_length)
    return _run(px, crossover(c, ma + mult * rng), crossunder(c, ma - mult * rng), mode)


def momentum_strategy(px, length=12, mode="long_short"):
    """'Momentum Strategy': mom0 = close - close[length], mom1 = mom0 - mom0[1]; long when both > 0,
    short when both < 0 (stop entries treated as filled at the signal close)."""
    mom0 = px["close"] - px["close"].shift(length)
    mom1 = mom0 - mom0.shift(1)
    return _run(px, (mom0 > 0) & (mom1 > 0), (mom0 < 0) & (mom1 < 0), mode)


def supertrend_strategy(px, atr=10, mult=3.0, mode="long_short"):
    d = pd.Series(supertrend_direction(px["high"], px["low"], px["close"], atr, mult), index=px.index)
    return _run(px, d == -1.0, d == 1.0, mode)


# ------------------------------------------------------------------ preregistered grids

STRATEGIES = {
    "supertrend": dict(fn=supertrend_strategy, default=dict(atr=10, mult=3.0),
                       grid=dict(atr=[7, 10, 14], mult=[2.0, 2.5, 3.0, 3.5, 4.0])),
    "macd": dict(fn=macd_strategy, default=dict(fast=12, slow=26, signal=9),
                 grid=dict(fast=[5, 8, 12], slow=[17, 21, 26, 35], signal=[5, 9])),
    "rsi": dict(fn=rsi_strategy, default=dict(length=14, oversold=30, overbought=70),
                grid=dict(length=[7, 14, 21], band=[(20, 80), (25, 75), (30, 70), (35, 65)])),
    "bollinger": dict(fn=bollinger_strategy, default=dict(length=20, mult=2.0),
                      grid=dict(length=[10, 20, 30, 50], mult=[1.5, 2.0, 2.5, 3.0])),
    "ma_cross": dict(fn=ma2line_strategy, default=dict(fast=9, slow=18),
                     grid=dict(pair=[(5, 18), (5, 20), (5, 50), (5, 100), (5, 200), (9, 18), (9, 20), (9, 50), (9, 100),
                                     (9, 200), (10, 20), (10, 50), (10, 100), (10, 200), (20, 50), (20, 100), (20, 200),
                                     (50, 100), (50, 200), (100, 200)])),
    "psar": dict(fn=psar_strategy, default=dict(start=0.02, increment=0.02, maximum=0.2),
                 grid=dict(step=[0.01, 0.02, 0.03], maximum=[0.1, 0.2, 0.3])),
    "stochastic": dict(fn=stoch_slow_strategy, default=dict(length=14, oversold=20, overbought=80),
                       grid=dict(length=[5, 9, 14, 21], band=[(20, 80), (30, 70)])),
    "channel_breakout": dict(fn=channel_breakout_strategy, default=dict(length=5),
                             grid=dict(length=[5, 10, 20, 55])),
    "keltner": dict(fn=keltner_strategy, default=dict(length=20, mult=2.0, atr_length=10),
                    grid=dict(length=[10, 20, 50], mult=[1.5, 2.0, 2.5, 3.0])),
    "momentum": dict(fn=momentum_strategy, default=dict(length=12), grid=dict(length=[5, 10, 12, 20, 50])),
}


def _kwargs(name: str, cell: dict) -> dict:
    """Map a grid cell to the function's keyword arguments."""
    kw = dict(cell)
    if "band" in kw:
        lo, hi = kw.pop("band")
        kw.update(oversold=lo, overbought=hi)
    if "pair" in kw:
        f, s = kw.pop("pair")
        kw.update(fast=f, slow=s)
    if "step" in kw:
        st = kw.pop("step")
        kw.update(start=st, increment=st)
    return kw


def _label(cell: dict, mode: str) -> str:
    parts = []
    for k, v in cell.items():
        if k == "pair":
            parts += [f"fast={v[0]}", f"slow={v[1]}"]
        elif isinstance(v, tuple):
            parts.append(f"{k}={v[0]}-{v[1]}")
        else:
            parts.append(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}")
    return "|".join(parts + [f"mode={mode}"])


def grid_cells(name: str) -> list[dict]:
    import itertools

    g = STRATEGIES[name]["grid"]
    keys = list(g)
    cells = [dict(zip(keys, vals)) for vals in itertools.product(*(g[k] for k in keys))]
    if name == "macd":
        cells = [c for c in cells if c["fast"] < c["slow"]]
    return cells


def default_label(name: str) -> str:
    """Grid label of the TradingView default (as it ships: long_short)."""
    d = STRATEGIES[name]["default"]
    cell = {"supertrend": dict(atr=d.get("atr"), mult=d.get("mult")),
            "macd": dict(fast=12, slow=26, signal=9),
            "rsi": dict(length=14, band=(30, 70)),
            "bollinger": dict(length=20, mult=2.0),
            "ma_cross": dict(pair=(9, 18)),
            "psar": dict(step=0.02, maximum=0.2),
            "stochastic": dict(length=14, band=(20, 80)),
            "channel_breakout": dict(length=5),
            "keltner": dict(length=20, mult=2.0),
            "momentum": dict(length=12)}[name]
    return _label(cell, "long_short")


def run_grid(name: str, px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    fn = STRATEGIES[name]["fn"]
    return {_label(c, m): fn(px, **_kwargs(name, c), mode=m) for c in grid_cells(name) for m in MODES}


def n_variants(name: str) -> int:
    return len(grid_cells(name)) * len(MODES)
