"""Supertrend port (samples/strategies.py) on synthetic data: no market data is used here."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples"))
import strategies as S  # noqa: E402


def _ohlc(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "dividend": 0.0},
                        index=pd.date_range("2020-01-01", periods=close.size))


def test_atr_wilder_seed_and_recursion():
    h = np.array([2.0, 3, 4, 5, 6]); l = np.array([1.0, 1, 2, 3, 4]); c = np.array([1.5, 2, 3, 4, 5])
    a = S.atr_wilder(h, l, c, 3)
    tr = np.array([1.0, 2.0, 2.0, 2.0, 2.0])  # first bar high-low; then max(h-l, |h-pc|, |l-pc|)
    assert np.isnan(a[:2]).all()
    assert a[2] == pytest.approx(tr[:3].mean())
    assert a[3] == pytest.approx(a[2] + (tr[3] - a[2]) / 3)


def test_direction_follows_clear_trends():
    up = np.linspace(100, 200, 120)
    down = np.linspace(200, 100, 120)
    px = _ohlc(np.concatenate([up, down]))
    d = S.supertrend_direction(px["high"], px["low"], px["close"], 10, 3.0)
    assert np.isnan(d[:9]).all()
    assert (d[60:119] == -1).all()  # uptrend
    assert (d[180:] == 1).all()  # downtrend after the turn


def test_positions_and_modes():
    px = _ohlc(np.concatenate([np.linspace(100, 200, 80), np.linspace(200, 120, 80)]))
    px["tr"] = px["close"].pct_change()
    ls = S.supertrend(px, 10, 3.0, "long_short")
    lf = S.supertrend(px, 10, 3.0, "long_flat")
    # long_short is short in the downtrend, so it earns the negative of the falling market there
    assert ls["return"].iloc[-20:].sum() > 0 and lf["return"].iloc[-20:].abs().sum() == 0
    assert set(S.supertrend_grid(px)) == {f"atr={a}|mult={m:g}|mode={md}" for a in S.ST_ATR for m in S.ST_MULT
                                         for md in S.ST_MODE}
    assert len(S.supertrend_grid(px)) == 30
