"""Sharpe-ratio inference against published worked examples and simulation."""

import math

import numpy as np
import pytest

from holdout_audit.stats import sharpe as S


def test_dsr_worked_example_bailey_lopez_de_prado_2014():
    """Numerical example of Bailey & Lopez de Prado (2014): annualised SR 2.5 over 5 years of
    daily data (T = 1250), skew -3, kurtosis 10, N = 100 trials whose annualised SRs have
    variance 1/2. The paper reports a per-period benchmark SR0 = 0.1132 and DSR = 0.9004."""
    q = 250
    sr = 2.5 / math.sqrt(q)
    var_trials = 0.5 / q  # annualised variance 1/2 expressed per period
    dsr, sr0 = S.deflated_sharpe_ratio(sr, 1250, -3.0, 10.0, 100, var_trials)
    assert sr0 == pytest.approx(0.1132, abs=5e-4)
    assert dsr == pytest.approx(0.9004, abs=5e-4)


def test_expected_max_matches_simulation(rng):
    n, v = 50, 0.04
    sims = rng.normal(0, math.sqrt(v), size=(20000, n)).max(axis=1).mean()
    assert S.expected_max_sharpe(n, v) == pytest.approx(sims, rel=0.03)


def test_expected_max_single_trial_is_zero():
    assert S.expected_max_sharpe(1, 1.0) == 0.0


def test_dsr_decreases_with_trials():
    vals = [S.deflated_sharpe_ratio(0.08, 2520, 0.0, 3.0, n, 1 / 2520)[0] for n in (1, 10, 100, 1000)]
    assert vals == sorted(vals, reverse=True)


def test_lo_se_formula_and_simulation(rng):
    # Lo (2002) eq. 8: SE = sqrt((1 + SR^2/2)/T)
    assert S.se_sharpe_iid_normal(0.5, 100) == pytest.approx(math.sqrt(1.125 / 100))
    t, mu, sd = 500, 0.05, 1.0
    srs = [S.sharpe(rng.normal(mu, sd, t)) for _ in range(4000)]
    assert np.std(srs) == pytest.approx(S.se_sharpe_iid_normal(mu / sd, t), rel=0.06)


def test_nonnormal_se_reduces_to_normal():
    a = S.se_sharpe_nonnormal(0.1, 1001, 0.0, 3.0)
    b = math.sqrt((1 + 0.5 * 0.01) / 1000)
    assert a == pytest.approx(b)


def test_negative_skew_widens_se():
    assert S.se_sharpe_nonnormal(0.1, 1000, -2.0, 9.0) > S.se_sharpe_nonnormal(0.1, 1000, 0.0, 3.0)


def test_psr_properties():
    assert S.probabilistic_sharpe_ratio(0.0, 0.0, 100) == pytest.approx(0.5)
    assert S.probabilistic_sharpe_ratio(0.1, 0.0, 1000) > S.probabilistic_sharpe_ratio(0.1, 0.0, 100)
    # Hand computation: z = 0.1*sqrt(99)/sqrt(1 + 2*0.01/4) = 0.99251 -> Phi(z) = 0.83953
    assert S.probabilistic_sharpe_ratio(0.1, 0.0, 100) == pytest.approx(0.83953, abs=1e-4)


def test_min_track_record_length():
    z = 1.6448536269514722
    expected = 1 + (1 + 0.5 * 0.01) * (z / 0.1) ** 2
    assert S.min_track_record_length(0.1, 0.0, 0.0, 3.0) == pytest.approx(expected)
    assert math.isinf(S.min_track_record_length(-0.1, 0.0, 0.0, 3.0))


def test_lo_annualization_iid_and_autocorrelated(rng):
    x = rng.normal(0, 1, 20000)
    assert S.lo_annualization_factor(x, 12) == pytest.approx(math.sqrt(12), rel=0.05)
    ar = np.zeros(20000)
    e = rng.normal(0, 1, 20000)
    for i in range(1, 20000):
        ar[i] = 0.3 * ar[i - 1] + e[i]
    # Positive autocorrelation lowers the annualised SR relative to sqrt(q) scaling.
    assert S.lo_annualization_factor(ar, 12) < math.sqrt(12) * 0.85


def test_summarize(rng):
    r = rng.normal(0.0005, 0.01, 2520)
    s = S.summarize(r, 252)
    assert s.sr_annual == pytest.approx(s.sr * math.sqrt(252))
    assert s.ci95_annual[0] < s.sr_annual < s.ci95_annual[1]
    assert 0 <= s.psr_zero <= 1


def test_sharpe_rejects_short_input():
    with pytest.raises(ValueError):
        S.sharpe([0.01, 0.02])
