"""Rubric v1.0: benchmark-relative checks, the benchmark cap, and the frozen document."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from holdout_audit import AuditConfig, run_audit
from holdout_audit.grade import CAP_RULES, FAIL, PASS, RUBRIC_RULES, Check, grade_from_checks
from holdout_audit.rubric import RUBRIC_DOC_SHA256, RUBRIC_VERSION

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / f"RUBRIC-v{RUBRIC_VERSION}.md"


def _market_and_timer(n=3000, seed=0):
    """A market with a strong drift and a 'timer' that is in the market half the time at random:
    positive absolute Sharpe, but it trails buy-and-hold."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2008-01-01", periods=n)
    m = rng.normal(0.0012, 0.01, n)
    pos = (rng.random(n) < 0.5).astype(float)
    to = np.abs(np.diff(np.concatenate([[0.0], pos])))
    return pd.DataFrame({"return": pos * m, "turnover": to, "market": m}, index=idx)


def test_rubric_document_is_pinned():
    assert DOC.exists()
    assert hashlib.sha256(DOC.read_bytes()).hexdigest() == RUBRIC_DOC_SHA256


def test_rule_strings_appear_verbatim_in_document():
    text = DOC.read_text(encoding="utf-8")
    for rule in list(RUBRIC_RULES.values()) + CAP_RULES:
        assert rule in text, rule


def test_auto_benchmark_is_buy_and_hold_when_market_given():
    df = _market_and_timer()
    res = run_audit(AuditConfig(name="t", returns=df, n_trials=1, n_boot=150))
    assert res.benchmark == "market"
    assert res.sharpe.sr_annual > 0  # positive absolute Sharpe ...
    assert res.sharpe_excess.mean < 0  # ... but it trails buy-and-hold
    assert not res.beats_benchmark
    assert res.grade.letter in "CDF"


def test_zero_benchmark_when_no_market_column():
    df = _market_and_timer().drop(columns=["market"])
    res = run_audit(AuditConfig(name="t", returns=df, n_trials=1, n_boot=100))
    assert res.benchmark == "zero"
    assert res.sharpe_excess.sr == pytest.approx(res.sharpe.sr)
    assert "no benchmark series" in res.benchmark_note


def test_explicit_zero_benchmark_records_reason():
    df = _market_and_timer()
    res = run_audit(AuditConfig(name="t", returns=df, benchmark="zero", benchmark_reason="market-neutral long/short",
                                n_trials=1, n_boot=100))
    assert res.benchmark == "zero" and "market-neutral" in res.benchmark_note


def test_benchmark_cap_limits_grade_to_c():
    checks = [Check(k, k, PASS, "", "", "") for k in ("dsr", "haircut", "holdout", "stability")]
    assert grade_from_checks(checks, True, beats_benchmark=True).letter == "A"
    g = grade_from_checks(checks, True, beats_benchmark=False)
    assert g.letter == "C" and g.caps == [CAP_RULES[0]]


def test_most_severe_cap_wins():
    checks = [Check("dsr", "d", PASS, "", "", ""), Check("pbo", "p", FAIL, "", "", ""),
              Check("x", "x", PASS, "", "", ""), Check("y", "y", PASS, "", "", "")]
    assert grade_from_checks(checks, True, beats_benchmark=False).letter == "D"


def test_excess_rather_than_absolute_drives_dsr():
    df = _market_and_timer()
    rel = run_audit(AuditConfig(name="rel", returns=df, n_trials=10, n_boot=100))
    absolute = run_audit(AuditConfig(name="abs", returns=df, benchmark="zero", benchmark_reason="test",
                                     n_trials=10, n_boot=100))
    assert rel.dsr < absolute.dsr


def test_surface_fails_when_chosen_sharpe_not_positive():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2012-01-02", periods=1500)
    v = pd.DataFrame({f"a={a}": rng.normal(-0.0005, 0.01, 1500) for a in (1, 2, 3)}, index=idx)
    res = run_audit(AuditConfig(name="neg", returns=pd.DataFrame({"return": v["a=2"]}), variants=v,
                                chosen_variant="a=2", n_boot=100))
    assert {c.key: c.status for c in res.grade.checks}["surface"] == FAIL


def test_report_cites_rubric(returns_df):
    from holdout_audit.report import render_report

    res = run_audit(AuditConfig(name="t", returns=returns_df, n_trials=3, n_boot=100, rubric_version="1.0"))
    html = render_report(res)
    assert f"rubric v{RUBRIC_VERSION}" in html
    assert RUBRIC_DOC_SHA256 in html
    assert res.headline()["rubric_version"] == RUBRIC_VERSION


def test_rubric_is_sealed_and_seal_matches_package_record():
    import json

    from holdout_audit.rubric import rubric_seal_info
    from holdout_audit.seal import sha256_hex, verify_seal

    seal_dir = ROOT / "docs" / "rubric-seal"
    out = verify_seal(seal_dir)  # re-hashes the rubric in place and checks every stored token's hash
    assert out["status"] == "verified" and set(out["verified_tsas"]) == {"digicert", "freetsa"}
    assert out["subject_sha256"] == RUBRIC_DOC_SHA256
    info = rubric_seal_info()
    assert info["status"] == "verified"
    assert info["seal_sha256"] == sha256_hex((seal_dir / "seal.json").read_bytes())
    seal = json.loads((seal_dir / "seal.json").read_text())
    assert seal["subject_file"] == "../RUBRIC-v1.0.md"
