"""London Breakout audit (samples/london-breakout): the port must match the author's own code.

Only hand-made and seeded synthetic series are used here. No real price is loaded.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

LB = Path(__file__).resolve().parents[1] / "samples" / "london-breakout"
sys.path.insert(0, str(LB))

import lb_data  # noqa: E402
import lb_original  # noqa: E402
import lb_port  # noqa: E402

# ------------------------------------------------------------------ hand-made example (PREREG §3.4)
# Fixed UTC-5 clock, as in HistData and as the original assumes. Expected signals worked out by hand
# from the original's source (comments give the rule that fires).
HAND = [
    # day 1: long, reversal to flat inside the window, short, target not checked inside the window,
    #        target hit at 03:30
    ("2020-01-06 02:00:00", 1.3000, 0),
    ("2020-01-06 02:30:00", 1.3010, 0),   # range high -> upper 1.3010
    ("2020-01-06 02:59:00", 1.2995, 0),   # range low  -> lower 1.2995
    ("2020-01-06 03:00:00", 1.3005, 0),   # thresholds fixed; no entry test on this bar
    ("2020-01-06 03:05:00", 1.3012, 1),   # above upper, <= 100 pips beyond, first -> long @1.3012
    ("2020-01-06 03:06:00", 1.3020, 0),   # above upper again, cumsum would be 2 -> ignored
    ("2020-01-06 03:10:00", 1.2990, -1),  # below lower, cumsum 0 >= -1 -> allowed: long -> FLAT (quirk A7)
    ("2020-01-06 03:11:00", 1.2980, -1),  # below lower, cumsum -1 -> short @1.2980
    ("2020-01-06 03:20:00", 1.2900, 0),   # 95 pips below lower, cumsum -2 -> ignored; no exit check yet (A6)
    ("2020-01-06 03:30:00", 1.2925, 1),   # window over; 1.2925 < 1.2980 - 0.005 -> cover (target)
    ("2020-01-06 05:00:00", 1.2800, 0),   # flat
    ("2020-01-06 12:00:00", 1.2850, 0),   # close hour, flat -> -0
    # day 2: false alarm (> 100 pips beyond), then a normal long held to the 12:00 flatten
    ("2020-01-07 02:00:00", 1.3000, 0),
    ("2020-01-07 02:40:00", 1.3004, 0),   # upper 1.3004, lower 1.3000
    ("2020-01-07 03:00:00", 1.3002, 0),
    ("2020-01-07 03:02:00", 1.3150, 0),   # 146 pips above upper -> false alarm, no trade
    ("2020-01-07 03:03:00", 1.3010, 1),   # long @1.3010
    ("2020-01-07 03:40:00", 1.3040, 0),   # +30 pips: inside the +/-50 pip band
    ("2020-01-07 12:00:00", 1.3030, -1),  # close hour -> flatten
    ("2020-01-07 12:01:00", 1.3100, 0),
    # day 3: entry on the last window minute (29), stopped out on minute 30; minute 30 is not an entry bar
    ("2020-01-08 02:00:00", 1.3000, 0),   # upper = lower = 1.3000
    ("2020-01-08 03:00:00", 1.3000, 0),
    ("2020-01-08 03:29:00", 1.2990, -1),  # short @1.2990
    ("2020-01-08 03:30:00", 1.3050, 1),   # 1.3050 > 1.2990 + 0.005 -> cover (stop)
    ("2020-01-08 03:31:00", 1.2900, 0),   # below lower but minute >= 30 -> no entry
    ("2020-01-08 12:00:00", 1.2950, 0),
]
HAND_DF = pd.DataFrame({"date": [r[0] for r in HAND], "price": [r[1] for r in HAND]})
HAND_SIGNALS = [r[2] for r in HAND]


def test_upstream_file_is_pinned():
    body = lb_original.upstream_source()
    assert "risky_stop=0.01\n" in body and "open_minutes=30\n" in body


def test_original_code_gives_hand_worked_signals():
    out = lb_original.run_original(HAND_DF)
    assert out["signals"].tolist() == HAND_SIGNALS
    assert out.loc[3, "upper"] == pytest.approx(1.3010) and out.loc[3, "lower"] == pytest.approx(1.2995)


def test_port_gives_hand_worked_signals():
    out = lb_port.signals_frame(HAND_DF)
    assert out["signals"].tolist() == HAND_SIGNALS
    ref = lb_original.run_original(HAND_DF)
    np.testing.assert_allclose(out["upper"], ref["upper"])
    np.testing.assert_allclose(out["lower"], ref["lower"])


def test_hand_example_accounting():
    t = pd.to_datetime(HAND_DF["date"])
    trades = lb_port.trade_list(t, HAND_DF["price"].to_numpy(), np.array(HAND_SIGNALS))
    assert trades["side"].tolist() == [1, -1, 1, -1]
    np.testing.assert_allclose(trades["pips"], [-22.0, 55.0, 20.0, -60.0], atol=1e-6)

    d = lb_port.daily_returns(t, HAND_DF["price"].to_numpy(), np.array(HAND_SIGNALS), cost_pips_per_side=1.0)
    assert d["turnover"].tolist() == [4.0, 2.0, 2.0]
    assert d["trades"].tolist() == [2, 1, 1]
    # day 1: long 1.3012 -> 1.2990 (ref 1.3012), short 1.2980 -> 1.2925 (ref 1.2980); 4 pips of cost
    day1 = (-0.0022 - 0.0002) / 1.3012 + (0.0055 - 0.0002) / 1.2980
    np.testing.assert_allclose(d["net"].iloc[0], day1, rtol=1e-9)
    np.testing.assert_allclose(d["gross"].iloc[1], 0.0020 / 1.3010, rtol=1e-9)
    np.testing.assert_allclose(d["net"].iloc[2], (-0.0060 - 0.0002) / 1.2990, rtol=1e-9)


def test_fill_lag_moves_fills_one_bar():
    t = pd.to_datetime(HAND_DF["date"])
    d = lb_port.daily_returns(t, HAND_DF["price"].to_numpy(), np.array(HAND_SIGNALS), 0.0, fill_lag=1)
    # day 2 with next-bar fills: long filled @1.3040 (03:40 bar), sold @1.3100 (12:01 bar)
    np.testing.assert_allclose(d["gross"].iloc[1], 0.0060 / 1.3040, rtol=1e-9)


# ------------------------------------------------------------------ port == original on synthetic data

@pytest.mark.parametrize("seed,sd,drop", [(1, 2e-4, 0.0), (2, 4e-4, 0.0), (3, 1.2e-3, 0.0), (4, 3e-4, 0.05)])
def test_port_matches_original_on_random_walks(seed, sd, drop):
    df = lb_data.random_walk_minutes(days=8, seed=seed, sd=sd, hours=(0, 14), drop_frac=drop)
    ref = lb_original.run_original(df)
    out = lb_port.signals_frame(df, on_empty_range="raise")
    assert (ref["signals"].to_numpy() != 0).sum() > 0
    np.testing.assert_array_equal(out["signals"].to_numpy(), ref["signals"].to_numpy())
    np.testing.assert_allclose(out["upper"].to_numpy(), ref["upper"].to_numpy())
    np.testing.assert_allclose(out["lower"].to_numpy(), ref["lower"].to_numpy())


@pytest.mark.parametrize("p", [lb_port.GRID[0], lb_port.GRID[-1], lb_port.Params(risky_stop=0.0075, open_minutes=15)])
def test_grid_variants_match_original_with_constants_swapped(p):
    df = lb_data.random_walk_minutes(days=8, seed=11, sd=6e-4, hours=(0, 14))
    ref = lb_original.run_original(df, risky_stop=p.risky_stop, open_minutes=p.open_minutes)
    out = lb_port.signals_frame(df, p)
    np.testing.assert_array_equal(out["signals"].to_numpy(), ref["signals"].to_numpy())


def test_grid_is_declared_size():
    assert lb_port.N_VARIANTS == 15
    assert lb_port.DEFAULT in lb_port.GRID
    assert len({p.label for p in lb_port.GRID}) == 15
    pre = json.loads((LB / "preregistration.json").read_text(encoding="utf-8"))
    assert pre["grid"]["n_variants"] == lb_port.N_VARIANTS
    assert sorted({p.label for p in lb_port.GRID}) == sorted(pre["grid"]["labels"])


def test_empty_range_crashes_original_and_is_skipped_by_port():
    df = pd.DataFrame({"date": ["2020-01-06 01:59:00", "2020-01-06 03:00:00", "2020-01-06 03:05:00"],
                       "price": [1.30, 1.30, 1.31]})
    with pytest.raises(ValueError):
        lb_original.run_original(df)
    out = lb_port.signals_frame(df, on_empty_range="skip")
    assert out["signals"].tolist() == [0, 0, 0]
    assert out.attrs["stats"]["empty_range_days"] == 1


# ------------------------------------------------------------------ data plumbing and locks

def test_histdata_parser_takes_close_bid():
    text = "20120201 000000;1.306600;1.306700;1.306500;1.306560;0\n20120201 000100;1.306560;1.3066;1.3065;1.306610;0\n"
    df = lb_data.parse_histdata_m1(text)
    assert df["date"].iloc[1] == pd.Timestamp("2012-02-01 00:01:00")
    assert df["price"].tolist() == [1.30656, 1.30661]


def test_real_data_refused_without_seal(tmp_path):
    with pytest.raises(lb_data.LockError):
        lb_data.require_prereg_seal(seal_dir=tmp_path / "prereg-seal", prereg=LB / "PREREG.md")


def test_holdout_refused_without_unlock(tmp_path):
    with pytest.raises(lb_data.LockError):
        lb_data.require_holdout_unlock(unlock=tmp_path / "HOLDOUT-UNLOCK.json", stage_a=tmp_path / "r.json")


def test_london_clock_conversion():
    s = pd.Series(pd.to_datetime(["2020-01-06 03:00:00", "2020-07-06 03:00:00"]))
    got = lb_port.to_london_clock(s)
    assert got.dt.hour.tolist() == [8, 9]  # 08:00 UTC is 08:00 GMT in winter, 09:00 BST in summer


def test_panel_hash_is_stable():
    df = lb_data.random_walk_minutes(days=1, seed=5, hours=(2, 3))
    assert lb_data.panel_sha256(df) == lb_data.panel_sha256(df.copy())


# ------------------------------------------------------------------ inference wording (PREREG §7)

def _run():
    """samples/london-breakout/run.py, loaded by path (other samples also have a module named run)."""
    import importlib.util

    if "lb_run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("lb_run", LB / "run.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["lb_run"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["lb_run"]


def test_holm_two_tests():
    adj = _run().holm({"P1": 0.01, "P2": 0.04})
    assert adj == {"P1": pytest.approx(0.02), "P2": pytest.approx(0.04)}
    adj = _run().holm({"P1": 0.03, "P2": 0.20})
    assert adj["P1"] == pytest.approx(0.06) and adj["P2"] == pytest.approx(0.20)


@pytest.mark.parametrize("p1,p2,mean,word", [
    (0.01, 0.04, 0.02, "SUPPORTED"), (0.01, 0.30, -0.01, "WENT THE OTHER WAY"), (0.01, 0.30, 0.01, "IN-SAMPLE ONLY"),
    (0.40, 0.01, 0.01, "HOLDOUT ONLY"), (0.40, 0.40, 0.01, "NOT SHOWN"), (0.40, 0.40, 0.0, "WENT THE OTHER WAY")])
def test_verdict_wording_is_fixed(p1, p2, mean, word):
    assert _run().verdict(p1, p2, mean).startswith(word)


def test_hand_example_exit_reasons():
    t = pd.to_datetime(HAND_DF["date"])
    trades = lb_port.trade_list(t, HAND_DF["price"].to_numpy(), np.array(HAND_SIGNALS))
    assert trades["exit_reason"].tolist() == ["window_reversal", "target", "close", "stop"]
