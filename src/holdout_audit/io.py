"""Input loading: daily strategy returns, trade lists and variant-return matrices (CSV).

Accepted formats (see docs/INPUT-FORMATS.md):

1. Daily returns:  ``date,return[,turnover][,market]``
   - ``return``: simple fractional return for the period (0.01 = +1%), net or gross of costs.
   - ``turnover`` (optional): fraction of capital traded that period (entering a full position
     = 1, flipping long to short = 2). Enables the cost-sensitivity analysis.
   - ``market`` (optional): the underlying/benchmark's return, for regime analysis and the
     Reality Check / SPA benchmark.
2. Trade list:  ``entry_date,exit_date,return`` (one row per closed trade, fractional return).
   Converted to daily returns by spreading each trade's compounded return evenly over its
   holding days (an approximation stated in the report), with turnover 1 on entry and exit.
3. Variant matrix: ``date,<variant_1>,<variant_2>,...`` of daily returns. Column names of the
   form ``fast=50|slow=200`` enable the parameter-sensitivity surface.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

_RETURN_ALIASES = ("return", "returns", "ret", "strategy_return", "daily_return", "r")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _date_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if c.lower() in ("date", "datetime", "timestamp", "time", "day"):
            return c
    raise ValueError("no date column (expected one of date/datetime/timestamp)")


def load_returns(path, percent: bool = False) -> pd.DataFrame:
    """Load a daily-returns CSV into a DataFrame indexed by date with column ``return``
    (and ``turnover`` / ``market`` when present)."""
    df = _read(path)
    lower = {c.lower(): c for c in df.columns}
    if "entry_date" in lower and "exit_date" in lower:
        return trades_to_daily(df, percent=percent)
    dc = _date_col(df)
    rc = next((lower[a] for a in _RETURN_ALIASES if a in lower), None)
    if rc is None:
        raise ValueError(f"no return column (expected one of {_RETURN_ALIASES})")
    out = pd.DataFrame({"return": pd.to_numeric(df[rc], errors="coerce")})
    for opt in ("turnover", "market"):
        if opt in lower:
            out[opt] = pd.to_numeric(df[lower[opt]], errors="coerce")
    dates = pd.to_datetime(df[dc])
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    out.index = pd.DatetimeIndex(dates)
    out.index.name = "date"
    if percent:
        out["return"] /= 100.0
        if "market" in out:
            out["market"] /= 100.0
    out = out.sort_index()
    if out.index.has_duplicates:
        raise ValueError("duplicate dates in returns file")
    _sanity(out["return"])
    return out


def trades_to_daily(trades: pd.DataFrame, percent: bool = False, calendar: str = "business") -> pd.DataFrame:
    lower = {c.lower(): c for c in trades.columns}
    ent = pd.to_datetime(trades[lower["entry_date"]])
    ext = pd.to_datetime(trades[lower["exit_date"]])
    rc = next((lower[a] for a in _RETURN_ALIASES if a in lower), None)
    if rc is None:
        raise ValueError("trade list needs a 'return' column (fractional return per trade)")
    rets = pd.to_numeric(trades[rc], errors="coerce") / (100.0 if percent else 1.0)
    freq = "B" if calendar == "business" else "D"
    idx = pd.date_range(ent.min(), ext.max(), freq=freq)
    daily = pd.Series(0.0, index=idx)
    growth = pd.Series(1.0, index=idx)
    turnover = pd.Series(0.0, index=idx)
    for e, x, r in zip(ent, ext, rets):
        if x <= e or not np.isfinite(r):
            raise ValueError(f"bad trade row: entry {e}, exit {x}, return {r}")
        days = idx[(idx > e) & (idx <= x)]
        if len(days) == 0:
            days = idx[idx >= x][:1]
        g = (1.0 + r) ** (1.0 / len(days))
        growth.loc[days] *= g
        turnover.loc[idx[idx >= e][:1]] += 1.0
        turnover.loc[idx[idx >= x][:1]] += 1.0
    daily = growth - 1.0
    out = pd.DataFrame({"return": daily, "turnover": turnover})
    out.index.name = "date"
    return out


def load_variants(path, percent: bool = False) -> pd.DataFrame:
    df = _read(path)
    dc = _date_col(df)
    out = df.drop(columns=[dc]).apply(pd.to_numeric, errors="coerce")
    out.index = pd.to_datetime(df[dc])
    out.index.name = "date"
    if percent:
        out /= 100.0
    if out.shape[1] < 2:
        raise ValueError("a variant matrix needs at least 2 variant columns")
    return out.sort_index()


def _sanity(r: pd.Series) -> None:
    x = r.dropna()
    if len(x) < 60:
        raise ValueError(f"only {len(x)} return observations; at least 60 are needed for a meaningful audit")
    if (x <= -1).any():
        raise ValueError("returns <= -100% found; returns must be simple fractions (0.01 = 1%)")
    if x.abs().median() > 0.2:
        raise ValueError("median |return| > 20%: are these percentages? pass percent=True")


def infer_periods_per_year(index: pd.DatetimeIndex) -> int:
    """252 for business-day data, 365 for 7-day (crypto) calendars, 52 weekly, 12 monthly."""
    if len(index) < 3:
        return 252
    gaps = np.diff(index.values).astype("timedelta64[D]").astype(int)
    med = np.median(gaps)
    if med >= 25:
        return 12
    if med >= 5:
        return 52
    weekend_share = np.mean(pd.DatetimeIndex(index).dayofweek >= 5)
    return 365 if weekend_share > 0.2 else 252
