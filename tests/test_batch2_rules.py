"""Batch 2 rules on synthetic data only (no market data)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples"))
import batch2_rules as R  # noqa: E402


def _px(close, start="2000-01-03"):
    close = np.asarray(close, dtype=float)
    df = pd.DataFrame({"close": close, "dividend": 0.0}, index=pd.bdate_range(start, periods=close.size))
    df["tr"] = df["close"].pct_change()
    return df


def _held(df, px):
    return (df["return"] / px["tr"]).round()


def test_month_end_mask():
    idx = pd.bdate_range("2021-01-01", "2021-03-31")
    me = R.month_end_mask(idx)
    assert list(idx[me.values].strftime("%Y-%m-%d")) == ["2021-01-29", "2021-02-26", "2021-03-31"]


def test_faber_long_in_uptrend_cash_after_fall():
    px = _px(np.concatenate([np.linspace(100, 200, 500), np.linspace(200, 80, 400)]))
    h = _held(R.faber(px, 10), px)
    assert h.iloc[300:480].mean() > 0.95 and h.iloc[800:890].mean() < 0.05


def test_sma_filter_hysteresis():
    c = np.concatenate([np.full(210, 100.0), [100.5, 100.8, 102, 103, 103]])
    px = _px(c)
    df = R.sma_filter(px, 200, 0.01)
    pos = df["turnover"].cumsum()
    assert pos.iloc[212] == 0  # +0.8% above the SMA is inside the 1% band
    assert pos.iloc[-1] == 1  # bought once it cleared the band


def test_halloween_months():
    px = _px(np.linspace(100, 200, 800))
    h = _held(R.halloween(px, 11, 4), px).iloc[1:]
    m = px.index[1:].month
    assert (h[m.isin([11, 12, 1, 2, 3, 4])] == 1).all() and (h[m.isin([5, 6, 7, 8, 9, 10])] == 0).all()


def test_turn_of_month_days():
    px = _px(np.linspace(100, 110, 60), start="2021-01-01")
    h = _held(R.turn_of_month(px, 1, 3), px)
    feb = h.loc["2021-02"]
    assert feb.iloc[:3].tolist() == [1, 1, 1] and feb.iloc[3:-1].eq(0).all() and feb.iloc[-1] == 1


def test_dual_momentum_switches_to_bonds_in_a_downtrend():
    up = np.linspace(100, 300, 700)
    down = np.linspace(300, 150, 500)
    spy = _px(np.concatenate([up, down]))
    efa = _px(np.concatenate([np.linspace(100, 200, 700), np.linspace(200, 120, 500)]))
    agg = _px(np.linspace(100, 130, 1200))
    df = R.dual_momentum({"SPY": spy, "EFA": efa, "AGG": agg}, 12, "AGG")
    last = df["return"].iloc[-40:]
    assert np.allclose(last, agg["tr"].iloc[-40:])  # absolute momentum negative -> bonds
    mid = df["return"].iloc[600:650]
    assert np.allclose(mid, spy["tr"].iloc[600:650])  # SPY stronger than EFA -> SPY


def test_sector_momentum_holds_top_k():
    n = 600
    prices = {s: _px(np.linspace(100, 100 + 10 * (i + 1), n)) for i, s in enumerate(R.SECTORS)}
    df = R.sector_momentum(prices, 6, 1, 3)
    rets = pd.DataFrame({s: prices[s]["tr"] for s in R.SECTORS})
    expect = rets[["XLU", "XLV", "XLY"]].mean(axis=1)  # the three steepest trends
    assert np.allclose(df["return"].iloc[-30:], expect.iloc[-30:])


def test_vix_stretch_enters_and_exits():
    n = 400
    spy = _px(np.concatenate([np.linspace(100, 200, 380), [196, 193, 190, 199, 205] + [206] * 15]))
    v = np.full(n, 15.0)
    v[380:384] = [17, 18, 19, 19]
    vix = pd.DataFrame({"close": v}, index=spy.index)
    df = R.vix_stretch(spy, vix, 0.05, 3, 65)
    held = df["turnover"].cumsum()
    assert held.iloc[383] >= 1  # entered after three stretched closes
    assert df["turnover"].sum() == 2  # and exited on the RSI(2) bounce


def test_sixty_forty_band_and_benchmark():
    stock = _px(np.linspace(100, 300, 500))
    bond = _px(np.full(500, 100.0))
    reb = R.sixty_forty(stock, bond, 0.05, "daily")
    bh = R.buy_and_hold_60_40(stock, bond, str(stock.index[0].date()))
    assert reb["turnover"].iloc[1:].gt(0).sum() >= 2  # rebalanced as stocks drifted up
    assert bh.sum() > reb["return"].sum()  # never rebalancing kept more stock in a pure uptrend


def test_rsi2_exit_rules_differ():
    rng = np.random.default_rng(0)
    px = _px(np.cumprod(1 + rng.normal(0.0005, 0.01, 1500)) * 100)
    outs = {e: R.rsi2(px, 10, e)["turnover"].sum() for e in ("sma5", "sma10", "rsi70", "upclose")}
    assert len(set(outs.values())) > 1 and all(v > 0 for v in outs.values())


def test_grid_sizes():
    assert {r: R.n_variants(r) for r in R.GRIDS} == {"faber": 4, "sma_filter": 8, "halloween": 6, "turn_of_month": 6,
                                                   "dual_momentum": 6, "sector_momentum": 12, "vix_stretch": 18,
                                                   "golden_cross": 24, "sixty_forty": 10, "rsi2": 12}
    for r in R.GRIDS:
        assert R.label(R.DEFAULTS[r]) in [R.label(c) for c in R.cells(r)]
