import re

import numpy as np
import pandas as pd
import pytest

from holdout_audit import AuditConfig, run_audit
from holdout_audit.grade import CAUTION, FAIL, NA, PASS, Check, grade_from_checks
from holdout_audit.report import render_report, write_report

BANNED = re.compile(r"\b(buy|sell|trade this)\b", re.I)


def _variants(n=2000, k=12, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2012-01-02", periods=n)
    cols = {f"fast={f}|slow={s}": rng.normal(0.0002, 0.01, n) for f in (10, 20, 30) for s in (50, 100, 150, 200)}
    return pd.DataFrame(cols, index=idx).iloc[:, :k]


def test_run_audit_single_series(returns_df):
    res = run_audit(AuditConfig(name="t", returns=returns_df, n_boot=200, base_cost_bps=2, n_trials=5))
    assert res.n_trials == 5
    assert res.pbo is None
    assert res.costs is not None and res.regimes is not None
    assert res.grade.letter in "ABCDF"
    keys = [c.key for c in res.grade.checks]
    assert keys == ["dsr", "pbo", "haircut", "spa", "holdout", "stability", "costs", "surface"]
    h = res.headline()
    assert set(h) >= {"grade", "dsr", "pbo", "sr_annual"}


def test_run_audit_with_variants():
    v = _variants()
    chosen = v.columns[3]
    df = pd.DataFrame({"return": v[chosen]})
    res = run_audit(AuditConfig(name="v", returns=df, variants=v, chosen_variant=chosen, n_boot=150))
    assert res.n_trials == v.shape[1]
    assert res.pbo is not None and 0 <= res.pbo.pbo <= 1
    assert res.surface is not None
    assert res.haircut.p_bhy is not None


def test_declared_trials_lower_dsr(returns_df):
    a = run_audit(AuditConfig(name="a", returns=returns_df, n_boot=100, n_trials=1))
    b = run_audit(AuditConfig(name="b", returns=returns_df, n_boot=100, n_trials=500))
    assert b.dsr < a.dsr


def test_undeclared_trials_caps_grade():
    checks = [Check(k, k, PASS, "", "", "") for k in ("dsr", "haircut", "spa", "holdout")]
    assert grade_from_checks(checks, variants_declared=True).letter == "A"
    g = grade_from_checks(checks, variants_declared=False)
    assert g.letter == "B" and g.caps


def test_grade_bands_and_caps():
    mk = lambda st: [Check("dsr", "d", st[0], "", "", ""), Check("pbo", "p", st[1], "", "", ""),
                     Check("x", "x", st[2], "", "", ""), Check("y", "y", st[3], "", "", "")]
    assert grade_from_checks(mk([PASS, PASS, PASS, CAUTION]), True).letter == "A"  # 7/8
    assert grade_from_checks(mk([FAIL, PASS, PASS, PASS]), True).letter == "C"  # 6/8 = B, capped to C
    assert grade_from_checks(mk([PASS, FAIL, PASS, PASS]), True).letter == "D"  # PBO cap
    assert grade_from_checks(mk([FAIL, FAIL, FAIL, FAIL]), True).letter == "F"
    g = grade_from_checks(mk([PASS, NA, PASS, PASS]), True)
    assert g.max_points == 6


def test_report_html(tmp_path, returns_df):
    v = _variants(n=len(returns_df))
    v.index = returns_df.index
    chosen = v.columns[0]
    res = run_audit(AuditConfig(name="Demo <strategy>", returns=returns_df.assign(**{"return": v[chosen]}),
                                variants=v, chosen_variant=chosen, n_boot=100, benchmark="market",
                                data_notes=["synthetic data"]))
    html = render_report(res)
    assert html.startswith("<!doctype html>")
    assert "Demo &lt;strategy&gt;" in html  # escaped
    for section in ("Executive summary", "What is fragile, and how to test the fix", "Methods appendix",
                    "Data and hash appendix", "not investment advice"):
        assert section in html
    assert "Deflated Sharpe" in html and "Probability of Backtest Overfitting" in html
    assert "<script" not in html.lower() and "http://" not in html and "https://" not in html
    text = re.sub(r"<[^>]+>", " ", html)
    # "buy-and-hold" names the benchmark and "buy, sell or hold" is in the disclaimer; nothing else may say buy/sell.
    text = re.sub(r"buy[- ]and[- ]hold|buy, sell or hold", "", text, flags=re.I)
    assert not BANNED.search(text), BANNED.search(text)
    p = write_report(res, tmp_path / "r.html")
    assert p.exists() and p.stat().st_size > 10000


def test_reproducible_hashes(returns_df):
    a = run_audit(AuditConfig(name="a", returns=returns_df, n_boot=100))
    b = run_audit(AuditConfig(name="a", returns=returns_df, n_boot=100))
    assert a.hashes["audited_series_sha256"] == b.hashes["audited_series_sha256"]
    assert a.spa.p_spa == b.spa.p_spa and a.dsr == b.dsr


def test_benchmark_market_requires_column():
    idx = pd.bdate_range("2015-01-01", periods=300)
    df = pd.DataFrame({"return": np.random.default_rng(0).normal(0, 0.01, 300)}, index=idx)
    with pytest.raises(ValueError):
        run_audit(AuditConfig(name="x", returns=df, benchmark="market", n_boot=50))


def test_pbo_high_but_no_losses_is_caution_not_fail():
    """Near-duplicate variants that all make money: ranking within the family is noise (PBO > 0.5)
    but the in-sample winner almost never loses out of sample, so the check is CAUTION."""
    rng = np.random.default_rng(3)
    n = 3000
    idx = pd.bdate_range("2010-01-01", periods=n)
    common = rng.normal(0.0008, 0.01, n)
    v = pd.DataFrame({f"k={i}": common + rng.normal(0, 0.001, n) for i in range(10)}, index=idx)
    res = run_audit(AuditConfig(name="dup", returns=pd.DataFrame({"return": v["k=0"]}), variants=v,
                                chosen_variant="k=0", n_boot=100))
    chk = {c.key: c for c in res.grade.checks}["pbo"]
    assert res.pbo.pbo > 0.5 and res.pbo.prob_oos_loss <= 0.10
    assert chk.status == CAUTION
    assert res.grade.letter != "D" or not res.grade.caps
