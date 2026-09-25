"""Batch 1 ports of TradingView built-in strategies, on synthetic data only (no market data)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples"))
import batch1_strategies as B  # noqa: E402


def _px(close, spread=0.01):
    close = np.asarray(close, dtype=float)
    df = pd.DataFrame({"open": close, "high": close * (1 + spread), "low": close * (1 - spread), "close": close,
                       "dividend": 0.0}, index=pd.bdate_range("2015-01-01", periods=close.size))
    df["tr"] = df["close"].pct_change()
    return df


UPDOWN = np.concatenate([np.linspace(100, 200, 150), np.linspace(200, 100, 150)])


def test_ema_rma_seed():
    x = pd.Series([1.0, 2, 3, 4, 5, 6])
    e = B.ema(x, 3)
    assert np.isnan(e[:2]).all() and e[2] == pytest.approx(2.0) and e[3] == pytest.approx(0.5 * 4 + 0.5 * 2)
    r = B.rma(x, 3)
    assert r[3] == pytest.approx(2 + (4 - 2) / 3)


def test_rsi_extremes():
    assert B.rsi(pd.Series(np.arange(1.0, 40)), 14).dropna().eq(100).all()
    assert B.rsi(pd.Series(np.arange(40.0, 1, -1)), 14).dropna().eq(0).all()


def test_crossover_definition():
    a = pd.Series([0.0, 1, 2, 1, 0])
    assert B.crossover(a, 1.5).tolist() == [False, False, True, False, False]
    assert B.crossunder(a, 1.5).tolist() == [False, False, False, True, False]


@pytest.mark.parametrize("name", list(B.STRATEGIES))
def test_every_strategy_runs_and_grid_labels(name):
    px = _px(UPDOWN + np.sin(np.arange(UPDOWN.size) / 3.0) * 3)
    grid = B.run_grid(name, px)
    assert len(grid) == B.n_variants(name)
    assert B.default_label(name) in grid
    for df in grid.values():
        assert set(df.columns) == {"return", "turnover"}
        assert df["turnover"].max() <= 2.0 + 1e-12
    lf = [k for k in grid if k.endswith("mode=long_flat")][0]
    r = grid[lf]["return"].iloc[1:]
    assert (r.eq(0) | (r * px["tr"].iloc[1:] > 0)).all()  # long-flat is only ever flat or long


def test_trend_followers_follow_a_clean_trend():
    # down, then up, then down: every trend follower must flip long after the first turn and short after the second
    path = np.concatenate([np.linspace(150, 100, 60), np.linspace(100, 200, 150), np.linspace(200, 100, 150)])
    px = _px(path, spread=0.002)
    for name in ("supertrend", "ma_cross", "psar", "momentum", "macd"):
        df = B.run_grid(name, px)[B.default_label(name)]
        pos = (df["return"] / px["tr"]).round()
        assert (pos.iloc[100:140] == 1).mean() > 0.9, name
        assert (pos.iloc[270:355] == -1).mean() > 0.9, name


def test_psar_direction_flips():
    px = _px(UPDOWN, spread=0.002)
    d = B.psar_direction(px["high"].to_numpy(), px["low"].to_numpy(), px["close"].to_numpy(), 0.02, 0.02, 0.2)
    assert np.isnan(d[0]) and d[120] == 1 and d[280] == -1


def test_grid_sizes_match_preregistration():
    sizes = {k: B.n_variants(k) for k in B.STRATEGIES}
    assert sizes == {"supertrend": 30, "macd": 48, "rsi": 24, "bollinger": 32, "ma_cross": 40, "psar": 18,
                     "stochastic": 16, "channel_breakout": 8, "keltner": 24, "momentum": 10}
