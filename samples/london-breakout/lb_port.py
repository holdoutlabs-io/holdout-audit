"""London Breakout: faithful port of je-suis-tm/quant-trading @ 611b73f2 (``signal_generation``).

The port is a single-pass state machine that reproduces the original bar for bar, including its
quirks (PREREG.md §3.3). It is O(n) where the original is O(n^2); ``tests/test_london_breakout.py``
checks that both produce identical ``signals``, ``upper`` and ``lower`` columns.

Clock. The original tests ``hour == 2``, ``hour == 3`` and ``hour == 12`` on the data's own
timestamps, which it assumes are HistData's fixed UTC-5 ("EST without DST"). ``Params`` keeps those
hours as fields so that the declared DST-aware sensitivity (London local clock: 7, 8, 17) uses the
same code. The defaults are the original's.

Nothing here reads files or prices. Callers pass arrays.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Params:
    risky_stop: float = 0.01  # original: false-alarm limit beyond the threshold; stop/target = risky_stop / 2
    open_minutes: int = 30  # original: entries allowed while hour == open_hour and minute < open_minutes
    range_hour: int = 2  # original: "the last trading hour before london starts" (hour == 2)
    open_hour: int = 3  # original: thresholds fixed at open_hour:00, entry window after it
    close_hour: int = 12  # original: flatten during hour == 12

    @property
    def label(self) -> str:
        return f"risky_stop={self.risky_stop:.4f}|open_minutes={self.open_minutes}"


DEFAULT = Params()
GRID_RISKY_STOP = (0.0050, 0.0075, 0.0100, 0.0125, 0.0150)
GRID_OPEN_MINUTES = (15, 30, 45)
GRID = tuple(Params(risky_stop=r, open_minutes=m) for r in GRID_RISKY_STOP for m in GRID_OPEN_MINUTES)
N_VARIANTS = len(GRID)  # 15
LONDON_CLOCK = dict(range_hour=7, open_hour=8, close_hour=17)  # DST-aware sensitivity (descriptive only)


class EmptyRangeError(ValueError):
    """The original's ``max(tokyo_price)`` on an empty list (it would crash with ValueError)."""


def generate_signals(hour: np.ndarray, minute: np.ndarray, price: np.ndarray, p: Params = DEFAULT,
                     on_empty_range: str = "skip") -> dict:
    """Bar-by-bar port of the original ``signal_generation``.

    Returns arrays ``signals`` (int: +1 buy one unit, -1 sell one unit, else 0), ``upper``, ``lower``
    (the original writes the thresholds on the open_hour:00 bar and on entry-window bars, 0.0
    elsewhere), plus counters of the declared edge cases.

    on_empty_range: what to do where the original would crash (no range-hour bars before an
    open_hour:00 bar). "raise" mimics the crash; "skip" (the declared interpretation, PREREG §3.3 A11)
    leaves the thresholds undefined until the next valid open_hour:00 bar, so no entry is possible.
    """
    n = len(price)
    hour = np.asarray(hour)
    minute = np.asarray(minute)
    price = np.asarray(price, dtype=float)
    sig = np.zeros(n, dtype=np.int64)
    upper_col = np.zeros(n)
    lower_col = np.zeros(n)
    tokyo: list[float] = []
    upper = lower = None  # undefined until the first open_hour:00 bar (original: NameError)
    executed = 0.0
    pos = 0  # the original's cumsum of signals before this bar
    half = p.risky_stop / 2
    stats = {"empty_range_days": 0, "entry_bars_without_thresholds": 0}

    for i in range(n):
        h, m, px = int(hour[i]), int(minute[i]), float(price[i])
        s = 0
        if h == p.range_hour:
            tokyo.append(px)
        elif h == p.open_hour and m == 0:
            if not tokyo:
                if on_empty_range == "raise":
                    raise EmptyRangeError(f"bar {i}: no range-hour prices before the open")
                stats["empty_range_days"] += 1
                upper = lower = None
            else:
                upper, lower = max(tokyo), min(tokyo)
                upper_col[i], lower_col[i] = upper, lower
            tokyo = []
        elif h == p.open_hour and m < p.open_minutes:
            if upper is None:
                stats["entry_bars_without_thresholds"] += 1
            else:
                upper_col[i], lower_col[i] = upper, lower
                if px - upper > 0:
                    s = 1
                    if px - upper > p.risky_stop:
                        s = 0
                    elif pos + 1 > 1:
                        s = 0
                    else:
                        executed = px
                if px - lower < 0:  # a separate `if` in the original; cannot co-fire (upper >= lower)
                    s = -1
                    if lower - px > p.risky_stop:
                        s = 0
                    elif pos - 1 < -1:
                        s = 0
                    else:
                        executed = px
        elif h == p.close_hour:
            s = -pos
        else:
            if pos != 0:
                if px > executed + half:
                    s = -pos
                if px < executed - half:
                    s = -pos
        sig[i] = s
        pos += s
    return {"signals": sig, "upper": upper_col, "lower": lower_col, "stats": stats}


def signals_frame(df: pd.DataFrame, p: Params = DEFAULT, on_empty_range: str = "skip") -> pd.DataFrame:
    """Same input as the original (columns ``date``, ``price``); returns a copy with the port's columns."""
    t = pd.to_datetime(df["date"])
    out = generate_signals(t.dt.hour.to_numpy(), t.dt.minute.to_numpy(), df["price"].to_numpy(), p,
                           on_empty_range)
    res = df.copy()
    res["signals"] = out["signals"]
    res["upper"] = out["upper"]
    res["lower"] = out["lower"]
    res["position"] = np.cumsum(out["signals"])
    res.attrs["stats"] = out["stats"]
    return res


# --------------------------------------------------------------------------------------------------
# Accounting (declared conventions, PREREG §4). The original has no P&L code; its sibling
# "Heikin-Ashi backtest.py" (same repo) books a fixed unit size filled at the signal bar's price
# without compounding, which is what we do here.
# --------------------------------------------------------------------------------------------------

PIP = 1e-4  # GBP/USD


def daily_returns(date: pd.Series, price: np.ndarray, signals: np.ndarray, cost_pips_per_side: float,
                  fill_lag: int = 0) -> pd.DataFrame:
    """Daily returns on the notional of one unit of GBP, net of costs.

    * The position after bar i is cumsum(signals)[i], filled at price[i] (as written) or at
      price[i + fill_lag] (execution sensitivity).
    * P&L per bar = position held into the bar x price change (mark to market, USD per GBP 1).
    * Cost per unit traded = cost_pips_per_side x 0.0001 (applied to every entry, exit and flip unit).
    * Return = P&L / reference price, where the reference is the fill price of the most recent
      entry from flat or flip (the notional at risk); a day's return is the sum over its bars (no compounding).
    * Rows: every calendar date (of the data's clock) that is a weekday and has at least one bar.
    Returns a frame indexed by date with columns gross, net, turnover, trades.
    """
    price = np.asarray(price, dtype=float)
    pos = np.cumsum(np.asarray(signals, dtype=np.int64))
    if fill_lag:
        pos = np.concatenate([np.zeros(fill_lag, dtype=np.int64), pos[:-fill_lag]])
    prev = np.concatenate([[0], pos[:-1]])
    traded = np.abs(pos - prev).astype(float)
    dp = np.concatenate([[0.0], np.diff(price)])
    pnl = prev * dp
    cost = traded * cost_pips_per_side * PIP
    opens = ((prev == 0) & (pos != 0)) | (np.sign(prev) * np.sign(pos) < 0)  # entries from flat, and flips
    ref = pd.Series(np.where(opens, price, np.nan)).ffill().to_numpy()
    ref = np.where(np.isnan(ref), 1.0, ref)  # only reached where pnl == cost == 0
    day = pd.to_datetime(pd.Series(date)).dt.normalize().to_numpy()
    frame = pd.DataFrame({"day": day, "gross": pnl / ref, "net": (pnl - cost) / ref, "turnover": traded,
                          "trades": opens.astype(int)})
    out = frame.groupby("day", sort=True).sum()
    out.index = pd.DatetimeIndex(out.index, name="date")
    return out[out.index.dayofweek < 5]


def trade_list(date: pd.Series, price: np.ndarray, signals: np.ndarray, p: Params = DEFAULT) -> pd.DataFrame:
    """One row per round trip (flat -> position -> flat, flips split in two), fills as written.

    exit_reason: "close" (hour == close_hour), "window_reversal" (opposite breakout inside the entry
    window, quirk A7), else "target" or "stop" by the sign of the result (bar-close fills can overshoot).
    """
    price = np.asarray(price, dtype=float)
    dates = pd.to_datetime(pd.Series(date)).to_numpy()
    pos = 0
    rows, entry = [], None
    for i, s in enumerate(np.asarray(signals, dtype=np.int64)):
        if s == 0:
            continue
        new = pos + s
        if pos != 0 and (new == 0 or np.sign(new) != np.sign(pos)):
            pips = float(np.sign(pos) * (price[i] - entry[1]) / PIP)
            ts = pd.Timestamp(dates[i])
            if ts.hour == p.close_hour:
                reason = "close"
            elif ts.hour == p.open_hour and ts.minute < p.open_minutes:
                reason = "window_reversal"
            else:
                reason = "target" if pips > 0 else "stop"
            rows.append({"entry_time": entry[0], "exit_time": dates[i], "side": int(np.sign(pos)),
                         "entry": entry[1], "exit": price[i], "pips": pips, "exit_reason": reason})
            entry = None
        if new != 0 and entry is None:
            entry = (dates[i], price[i])
        pos = new
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "side", "entry", "exit", "pips", "exit_reason"])


def to_london_clock(fixed_utc_minus5: pd.Series) -> pd.Series:
    """HistData fixed UTC-5 timestamps -> naive Europe/London local time (DST-aware sensitivity)."""
    t = pd.to_datetime(fixed_utc_minus5) + pd.Timedelta(hours=5)
    return t.dt.tz_localize("UTC").dt.tz_convert("Europe/London").dt.tz_localize(None)
