import numpy as np
import pytest

from holdout_audit.stats.pbo import pbo_cscv


def test_pbo_noise_at_least_half():
    """With pure-noise variants no in-sample winner is genuinely better, so it lands at or below the
    OOS median at least half the time. (Because IS and OOS are complementary halves of one sample,
    a lucky IS half implies a weaker OOS half, so CSCV gives PBO >= 0.5 on noise.)"""
    vals = [pbo_cscv(np.random.default_rng(s).normal(0, 0.01, (1600, 20)), n_blocks=10).pbo for s in range(8)]
    assert 0.45 <= np.mean(vals) <= 0.85


def test_pbo_true_edge_near_zero(rng):
    m = rng.normal(0, 0.01, (2000, 20))
    m[:, 3] += 0.004  # one variant with a large genuine edge
    res = pbo_cscv(m, n_blocks=16)
    assert res.pbo < 0.05
    assert res.prob_oos_loss < 0.05
    assert res.n_splits == 12870


def test_pbo_regime_flip_family_is_overfit():
    """Half the variants win in even blocks and lose in odd blocks, the other half the reverse:
    whatever wins in sample tends to lose out of sample, so PBO is high."""
    rng = np.random.default_rng(7)
    t, n = 1600, 10
    m = rng.normal(0, 0.01, (t, n))
    signs = np.where(np.arange(n) < 5, 1.0, -1.0)
    for b in range(16):
        s = 1.0 if b % 2 == 0 else -1.0
        m[b * 100:(b + 1) * 100] += 0.003 * s * signs
    res = pbo_cscv(m, n_blocks=16)
    assert res.logits.shape == (12870,)
    assert res.pbo > 0.5


def test_pbo_validates_input(rng):
    with pytest.raises(ValueError):
        pbo_cscv(rng.normal(size=(100, 1)))
    with pytest.raises(ValueError):
        pbo_cscv(rng.normal(size=(100, 3)), n_blocks=5)


def test_pbo_subsampling_is_seeded(rng):
    m = rng.normal(0, 0.01, (800, 6))
    a = pbo_cscv(m, n_blocks=16, max_splits=500, seed=1)
    b = pbo_cscv(m, n_blocks=16, max_splits=500, seed=1)
    assert a.n_splits == 500 and a.pbo == b.pbo
