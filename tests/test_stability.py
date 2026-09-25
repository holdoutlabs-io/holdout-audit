import numpy as np
import pandas as pd
import pytest

from conftest import make_returns
from holdout_audit.stats import stability as St


def test_holdout_split_and_ratio():
    s = make_returns(n=2000, mu=0.001)
    s.iloc[1400:] = np.random.default_rng(3).normal(-0.001, 0.01, 600)
    h = St.holdout_degradation(s, 252)
    assert h.n_is == 1400 and h.n_oos == 600
    assert h.sr_oos_annual < h.sr_is_annual
    assert h.p_oos_consistent < 0.2


def test_holdout_explicit_split():
    s = make_returns(n=1000)
    h = St.holdout_degradation(s, 252, split_date=s.index[500])
    assert h.n_is == 500 and h.n_oos == 500


def test_yearly_and_regimes():
    s = make_returns(n=2520)
    m = make_returns(seed=9)
    y = St.yearly_table(s, 252)
    assert y["year"].tolist() == sorted(y["year"].tolist())
    reg = St.vol_regime_table(s, m, 252)
    assert list(reg["regime"]) == ["low vol", "mid vol", "high vol"]
    assert reg["n"].sum() > 2400


def test_cost_sensitivity_breakeven():
    idx = pd.bdate_range("2020-01-01", periods=500)
    r = pd.Series(0.001, index=idx)
    to = pd.Series(0.5, index=idx)
    c = St.cost_sensitivity(r, to, 252, grid_bps=(0, 10, 20, 30))
    assert c.breakeven_bps == pytest.approx(20.0)
    assert c.ann_return[2] == pytest.approx(0.0, abs=1e-12)


def test_parse_params():
    assert St.parse_params("fast=50|slow=200") == {"fast": 50, "slow": 200}
    assert St.parse_params("rsi=2|entry=10.5|mode=trend") == {"rsi": 2, "entry": 10.5, "mode": "trend"}
    assert St.parse_params("plain") == {}


def test_parameter_surface_plateau_vs_peak():
    idx = pd.bdate_range("2015-01-01", periods=1500)
    rng = np.random.default_rng(0)
    base = rng.normal(0, 0.01, 1500)
    cols = {}
    for a in (1, 2, 3):
        for b in (1, 2, 3):
            edge = 0.002 if (a, b) == (2, 2) else 0.0
            cols[f"a={a}|b={b}"] = base * 0.2 + rng.normal(edge, 0.01, 1500)
    peak = St.parameter_surface(pd.DataFrame(cols, index=idx), "a=2|b=2", 252)
    assert peak.rank_of_chosen == 1
    assert peak.neighbor_ratio < 0.4
    flat = {k: base * 0.2 + rng.normal(0.002, 0.01, 1500) for k in cols}
    plat = St.parameter_surface(pd.DataFrame(flat, index=idx), "a=2|b=2", 252)
    assert plat.neighbor_ratio > 0.7


def test_surface_none_without_grid_names():
    idx = pd.bdate_range("2015-01-01", periods=100)
    df = pd.DataFrame({"x": np.zeros(100), "y": np.zeros(100)}, index=idx)
    assert St.parameter_surface(df, "x", 252) is None
