"""Synthetic-data tests for the ONCHAIN-1 helpers (samples/onchain1). No market or chain data used."""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "samples" / "onchain1"))
sys.path.insert(0, str(ROOT / "samples"))

import p2p  # noqa: E402
import run as R  # noqa: E402


def test_genesis_header_hash_and_pow():
    # The genesis block header is a published constant of the Bitcoin protocol.
    hdr = (struct.pack("<I", 1) + b"\0" * 32
           + bytes.fromhex("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b")[::-1]
           + struct.pack("<III", 1231006505, 0x1D00FFFF, 2083236893))
    h = p2p.dsha(hdr)
    assert h == p2p.GENESIS
    assert p2p.verify_link(b"\0" * 32, hdr) == p2p.GENESIS


def test_verify_link_rejects_broken_chain():
    hdr = struct.pack("<I", 1) + b"\x01" * 32 + b"\0" * 32 + struct.pack("<III", 0, 0x1D00FFFF, 0)
    with pytest.raises(ValueError):
        p2p.verify_link(b"\0" * 32, hdr)


def test_subsidy_schedule_matches_consensus():
    for height, btc in [(0, 50), (209_999, 50), (210_000, 25), (420_000, 12.5), (630_000, 6.25), (840_000, 3.125)]:
        assert (5_000_000_000 >> (height // 210_000)) / 1e8 == btc


def test_episodes_merge_gaps_under_30_days():
    idx = pd.date_range("2020-01-01", periods=200, freq="D")
    z = pd.Series(False, index=idx)
    z.iloc[[0, 1, 20, 100, 150]] = True  # 0-20 merge (gap 19); 100 separate; 150 separate (gap 50)
    eps = R.episodes(z)
    assert [(a.day, b.day) for a, b in eps][0] == (1, 21)
    assert len(eps) == 3


def test_holm_matches_hand_computation():
    adj = R.holm([0.01, 0.04, 0.03, 1.0, 1.0, 1.0])
    assert adj[0] == pytest.approx(0.06)
    assert adj[2] == pytest.approx(0.15)  # 5 * 0.03
    assert adj[1] == pytest.approx(0.16)  # 4 * 0.04
    assert adj[3] == 1.0


def test_zone_test_detects_planted_effect_and_not_noise():
    rng = np.random.default_rng(1)
    idx = pd.date_range("2015-01-01", periods=3000, freq="D")
    r = rng.normal(0, 0.02, len(idx))
    zone = pd.Series(False, index=idx)
    for s in range(200, 2600, 300):  # 8 episodes of 20 days, each followed by a strong rise
        zone.iloc[s:s + 20] = True
        r[s + 20:s + 110] += 0.01
    close = pd.Series(100 * np.exp(np.cumsum(r)), index=idx)
    res = R.zone_test(zone, close, 90, +1, idx[0])
    assert res["inferential"] and res["episodes"] == 8
    assert res["D"] > 0 and res["p_one_sided"] < 0.05
    noise = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(idx)))), index=idx)
    res2 = R.zone_test(zone, noise, 90, +1, idx[0])
    assert res2["p_one_sided"] > 0.01


def test_zone_test_few_episodes_is_descriptive():
    idx = pd.date_range("2015-01-01", periods=1500, freq="D")
    close = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    zone = pd.Series(False, index=idx)
    zone.iloc[[300, 700]] = True
    res = R.zone_test(zone, close, 365, -1, idx[0])
    assert res["episodes"] == 2 and not res["inferential"]


def test_state_machine_enter_exit():
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    enter = pd.Series([0, 1, 0, 0, 1, 0], index=idx).astype(bool)
    exit_ = pd.Series([0, 0, 0, 1, 0, 0], index=idx).astype(bool)
    pos = R.state_machine(enter, exit_, pd.Series(True, index=idx))
    assert pos.tolist() == [0, 1, 1, 0, 1, 1]


def test_top_hit_window():
    idx = pd.date_range("2018-01-01", periods=1200, freq="D")
    close = pd.Series(np.r_[np.linspace(100, 200, 600), np.linspace(200, 50, 600)], index=idx)
    zone = pd.Series(False, index=idx)
    zone.iloc[597] = True  # top at index 599
    h = R.hits(zone, close, idx[0], "top", (3, 30))
    assert h[0]["hit_W3"] and h[0]["days_from_start_to_extreme"] == 2


def test_s2f_model_reproduces_planb_2019_example():
    # PlanB (2019): SF ~ 50 after the 2020 halving implies a market value of about USD 1 trillion.
    mv = np.exp(14.6) * 50 ** 3.3
    assert 0.8e12 < mv < 1.0e12
