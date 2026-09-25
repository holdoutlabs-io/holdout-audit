"""Batch 3 rules on synthetic data only (no market data)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples"))
import batch3_rules as R  # noqa: E402


def _px(r, start="2000-01-03"):
    r = np.asarray(r, float)
    idx = pd.bdate_range(start, periods=r.size)
    close = 100 * np.cumprod(1 + r)
    return pd.DataFrame({"close": close, "adjclose": close, "dividend": 0.0, "tr": np.r_[np.nan, r[1:]]}, index=idx)


def test_vol_managed_scales_down_in_turbulent_months():
    rng = np.random.default_rng(0)
    r = np.r_[rng.normal(0, 0.005, 300), rng.normal(0, 0.03, 60), rng.normal(0, 0.005, 300)]
    spy = _px(r)
    df = R.vol_managed(spy, "1m", 0.16, 1.5)
    w = (df["return"] / spy["tr"]).replace([np.inf, -np.inf], np.nan)
    calm, wild = w.iloc[250:290].median(), w.iloc[330:360].median()
    assert calm == pytest.approx(1.5) and wild < 0.5  # capped at 1.5 when calm, cut when volatile


def test_lowvol_sectors_picks_the_calmest():
    rng = np.random.default_rng(1)
    prices = {s: _px(rng.normal(0.0003, 0.005 * (i + 1), 700)) for i, s in enumerate(R.SECTORS)}
    df = R.lowvol_sectors(prices, 252, 3)
    rets = pd.DataFrame({s: prices[s]["tr"] for s in R.SECTORS})
    assert np.allclose(df["return"].iloc[-20:], rets[["XLB", "XLE", "XLF"]].mean(axis=1).iloc[-20:])


def test_tsmom_signs_and_vol_scaling():
    n = 800
    up, down = np.full(n, 0.001), np.full(n, -0.001)
    rng = np.random.default_rng(2)
    prices = {s: _px((up if i % 2 == 0 else down) + rng.normal(0, 0.004 * (i + 1), n)) for i, s in enumerate(R.TSMOM_ASSETS)}
    df = R.tsmom(prices, 12, "vol40")
    assert df["return"].iloc[-200:].mean() > 0  # long the risers, short the fallers
    eq = R.tsmom(prices, 12, "equal")
    assert not np.allclose(df["return"].iloc[-50:], eq["return"].iloc[-50:])


def test_gtaa_goes_to_cash_below_sma():
    n = 700
    fall = np.r_[np.full(400, 0.001), np.full(300, -0.002)]
    prices = {s: _px(fall) for s in R.GTAA_ASSETS}
    df = R.gtaa(prices, 10, "price")
    assert df["return"].iloc[-60:].abs().sum() == 0  # all three in cash after a long fall


def test_risk_parity_weights_inverse_vol():
    rng = np.random.default_rng(3)
    prices = {"SPY": _px(rng.normal(0.0004, 0.015, 900)), "TLT": _px(rng.normal(0.0002, 0.005, 900))}
    df = R.risk_parity(prices, 252, "TLT")
    rets = pd.DataFrame({"SPY": prices["SPY"]["tr"], "TLT": prices["TLT"]["tr"]})
    # implied SPY weight about 0.25 (inverse of 3x volatility)
    tail = df["return"].iloc[-100:]
    w = np.linalg.lstsq(rets.iloc[-100:].to_numpy(), tail.to_numpy(), rcond=None)[0]
    assert w[0] == pytest.approx(0.25, abs=0.05) and w.sum() == pytest.approx(1.0, abs=0.02)


def test_grid_sizes_and_defaults():
    assert {r: R.n_variants(r) for r in R.GRIDS} == {"vol_managed": 12, "lowvol_sectors": 9, "lowvol_etf": 2,
                                                   "tsmom": 8, "gtaa": 8, "risk_parity": 8}
    for r in R.GRIDS:
        assert R.label(R.DEFAULTS[r]) in [R.label(c) for c in R.cells(r)]
