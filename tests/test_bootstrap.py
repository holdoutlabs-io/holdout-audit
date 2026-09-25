import numpy as np
import pytest

from holdout_audit.stats import bootstrap as B


def test_stationary_indices_shape_and_blocks(rng):
    idx = B.stationary_bootstrap_indices(1000, 50, 20.0, rng)
    assert idx.shape == (50, 1000)
    assert idx.min() >= 0 and idx.max() < 1000
    cont = np.mean(np.diff(idx, axis=1) % 1000 == 1)
    assert cont == pytest.approx(1 - 1 / 20, abs=0.02)


def test_rc_spa_detects_real_edge(rng):
    m = rng.normal(0, 0.01, (2000, 10))
    m[:, 2] += 0.002
    res = B.reality_check_spa(m, n_boot=300, seed=1)
    assert res.best_index == 2
    assert res.p_reality_check < 0.05 and res.p_spa < 0.05


def test_rc_spa_null_not_rejected_often():
    rej = 0
    for s in range(20):
        m = np.random.default_rng(s).normal(0, 0.01, (500, 8))
        rej += B.reality_check_spa(m, n_boot=200, seed=s).p_spa < 0.05
    assert rej <= 4  # nominal 5%; conservative under the least-favourable null


def test_spa_uses_benchmark(rng):
    b = rng.normal(0.001, 0.01, 1500)
    r = b + rng.normal(0, 0.001, 1500)  # tracks the benchmark: no excess return
    assert B.reality_check_spa(r, b, n_boot=300, seed=2).p_spa > 0.05


def test_max_drawdown_simple():
    assert B.max_drawdown([0.1, -0.5, 0.2]) == pytest.approx(0.5)
    assert B.max_drawdown([0.01, 0.01]) == 0.0


def test_bootstrap_drawdowns(rng):
    r = rng.normal(0.0003, 0.01, 1500)
    d = B.bootstrap_drawdowns(r, n_boot=200, seed=3)
    assert d.boot.shape == (200,)
    assert d.percentiles[5] <= d.percentiles[50] <= d.percentiles[95]
    assert 0 <= d.prob_worse_than_realized <= 1
