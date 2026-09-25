import math

import numpy as np
import pytest
from scipy import stats

from holdout_audit.stats import haircut as H


def test_single_test_identity():
    r = H.haircut_sharpe(1.0, 10.0, 1)
    assert r.p_bonferroni == pytest.approx(r.p_single)
    assert r.sr_haircut_bonferroni == pytest.approx(1.0, rel=1e-6)


def test_bonferroni_hand_computation():
    # SR 1.0 over 10 years -> t = sqrt(10) = 3.1623, p = 0.001565; N = 10 -> p_adj = 0.01565
    r = H.haircut_sharpe(1.0, 10.0, 10)
    assert r.t_stat == pytest.approx(math.sqrt(10))
    assert r.p_single == pytest.approx(0.001565, abs=2e-6)
    assert r.p_bonferroni == pytest.approx(10 * r.p_single)
    t_adj = stats.norm.isf(r.p_bonferroni / 2)
    assert r.sr_haircut_bonferroni == pytest.approx(t_adj / math.sqrt(10))
    assert 0 < r.haircut_pct_bonferroni < 1


def test_haircut_grows_with_tests():
    hs = [H.haircut_sharpe(0.8, 15, n).haircut_pct_bonferroni for n in (1, 10, 100, 1000)]
    assert hs == sorted(hs)


def test_holm_and_bhy_hand_computed():
    p = np.array([0.01, 0.04, 0.03, 0.005, 0.2])
    # Holm: sorted .005,.01,.03,.04,.2 -> 5*.005=.025, 4*.01=.04, 3*.03=.09, 2*.04=.08 -> .09 (monotone), .2
    np.testing.assert_allclose(H.holm_adjusted(p), [0.04, 0.09, 0.09, 0.025, 0.2])
    c = sum(1 / k for k in range(1, 6))  # 2.2833
    # BHY sorted: p_(i) * n * c / i, then running minimum from the top.
    raw = np.array([0.005 * 5 / 1, 0.01 * 5 / 2, 0.03 * 5 / 3, 0.04 * 5 / 4, 0.2 * 5 / 5]) * c
    mono = np.minimum(np.minimum.accumulate(raw[::-1])[::-1], 1.0)
    out = np.empty(5)
    out[np.argsort(p)] = mono
    np.testing.assert_allclose(H.bhy_adjusted(p), out)
    assert H.bhy_adjusted(p)[3] == pytest.approx(0.005 * 5 * c)


def test_full_vector_path():
    srs = [1.2, 0.3, -0.1, 0.5, 0.0]
    r = H.haircut_sharpe(1.2, 10, 5, srs, 0)
    assert r.p_holm is not None and r.p_bhy is not None
    assert r.p_adjusted == r.p_bhy
