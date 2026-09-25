"""Rubric v1.1: one-sided haircut, declared objectives, and the drawdown objective's statistics."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from holdout_audit import AuditConfig, run_audit
from holdout_audit.grade import (CAP_RULES_V11, DECLARATION_RULE, FAIL, OBJECTIVE_DRAWDOWN, PASS,
                                 RUBRIC_RULES_V11_BEAT, RUBRIC_RULES_V11_DRAWDOWN, Check, grade_from_checks)
from holdout_audit.report import render_report
from holdout_audit.rubric import RUBRICS
from holdout_audit.stats import haircut as H
from holdout_audit.stats import objective as O

ROOT = Path(__file__).resolve().parents[1]
DOC11 = ROOT / RUBRICS["1.1"]["document"]


def _decl(tmp_path, **kw):
    d = {"objective": "reduce_drawdown", "max_return_shortfall_annual": 0.03,
         "declared_at_utc": "2026-09-01T00:00:00Z", "declared_by": "client-ref-001", "benchmark": "buy-and-hold"}
    d.update(kw)
    p = tmp_path / "declaration.json"
    p.write_text(json.dumps(d))
    return p


def _hedged(n=3000, seed=0, exposure=0.6):
    """Market with crashes; the strategy holds a constant partial exposure, so it cuts drawdown and
    tail loss by construction at a known return cost."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-01", periods=n)
    m = rng.standard_t(4, n) * 0.008 + 0.0004
    return pd.DataFrame({"return": exposure * m, "turnover": 0.0, "market": m}, index=idx)


# ---------------------------------------------------------------- document


def test_v11_document_pinned_and_contains_rules():
    assert hashlib.sha256(DOC11.read_bytes()).hexdigest() == RUBRICS["1.1"]["document_sha256"]
    text = DOC11.read_text(encoding="utf-8")
    for rule in list(RUBRIC_RULES_V11_BEAT.values()) + list(RUBRIC_RULES_V11_DRAWDOWN.values()) + CAP_RULES_V11:
        assert rule in text, rule
    assert DECLARATION_RULE in text


# ---------------------------------------------------------------- fix 1: one-sided haircut


def test_one_sided_haircut_never_rewards_underperformance():
    neg = H.haircut_sharpe(-1.0, 20, 5, one_sided=True)
    assert neg.p_single > 0.5 and neg.p_bonferroni == 1.0
    two = H.haircut_sharpe(-1.0, 20, 5, one_sided=False)
    assert two.p_bonferroni < 0.05  # the v1.0 defect: two-sided p "passes" a significantly negative Sharpe
    pos = H.haircut_sharpe(1.0, 10, 1, one_sided=True)
    assert pos.p_single == pytest.approx(H.p_two_sided(np.sqrt(10)) / 2)


def test_v11_haircut_fails_significant_underperformer_v10_passes_it():
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2000-01-03", periods=5000)
    m = rng.normal(0.0008, 0.01, 5000)
    df = pd.DataFrame({"return": m - 0.0006 + rng.normal(0, 0.002, 5000), "market": m}, index=idx)
    v10 = run_audit(AuditConfig(name="x", returns=df, n_trials=1, n_boot=100, rubric_version="1.0"))
    v11 = run_audit(AuditConfig(name="x", returns=df, n_trials=1, n_boot=100))
    s10 = {c.key: c.status for c in v10.grade.checks}["haircut"]
    s11 = {c.key: c.status for c in v11.grade.checks}["haircut"]
    assert v10.sharpe_excess.sr < 0
    assert s10 == PASS and s11 == FAIL


# ---------------------------------------------------------------- objective statistics


def test_cvar_definition():
    x = np.array([-0.10, -0.05, 0.0, 0.01] + [0.02] * 16)  # 20 obs, worst 5% = 1 obs
    assert O.cvar(x) == pytest.approx(0.10)
    assert O.cvar(x, alpha=0.10) == pytest.approx(0.075)


def test_objective_bootstrap_on_partial_exposure():
    df = _hedged()
    ob = O.objective_bootstrap(df["return"].to_numpy(), df["market"].to_numpy(), 252, n_boot=300, seed=1)
    assert ob.cvar_strategy == pytest.approx(0.6 * ob.cvar_benchmark)
    assert ob.d_mdd > 0 and ob.d_cvar_lo > 0 and ob.d_mdd_lo > 0
    assert ob.shortfall == pytest.approx(0.4 * df["market"].mean() * 252)
    assert ob.shortfall_hi >= ob.shortfall
    assert ob.p_d_cvar < 0.01


def test_pbo_cvar_exact_tail_trick_matches_brute_force():
    rng = np.random.default_rng(5)
    t, n = 640, 4
    b = rng.standard_t(3, t) * 0.01
    v = np.stack([b * e + rng.normal(0, 0.002, t) for e in (0.3, 0.5, 0.7, 0.9)], axis=1)
    res = O.pbo_cscv_cvar(v, b, n_blocks=4)
    # brute force on the first split
    import itertools
    L = t // 4
    blocks = list(itertools.combinations(range(4), 2))
    c = blocks[0]
    rows = np.concatenate([np.arange(j * L, (j + 1) * L) for j in c])
    brute = [O.cvar(b[rows]) - O.cvar(v[rows, k]) for k in range(n)]
    assert res.is_sr_best[0] == pytest.approx(max(brute))
    assert res.n_splits == 6


def test_deflated_objective_decreases_with_trials():
    vals = [O.deflated_objective(0.002, 0.001, n, 0.001 ** 2)[0] for n in (1, 10, 100)]
    assert vals == sorted(vals, reverse=True)
    assert vals[0] == pytest.approx(0.97725, abs=1e-4)  # N = 1: Phi(2)


# ---------------------------------------------------------------- declaration rules


def test_no_declaration_means_objective_a(returns_df):
    res = run_audit(AuditConfig(name="t", returns=returns_df, n_trials=2, n_boot=100, rubric_version="1.1"))
    assert res.objective == "beat_benchmark" and res.declaration.source == "default"
    assert res.rubric["version"] == "1.1"


def test_drawdown_objective_requires_tolerance_and_date(tmp_path):
    df = _hedged()
    with pytest.raises(ValueError, match="max_return_shortfall_annual"):
        run_audit(AuditConfig(name="t", returns=df, n_boot=50,
                              declaration_file=str(_decl(tmp_path, max_return_shortfall_annual=None))))
    with pytest.raises(ValueError, match="declared_at_utc"):
        run_audit(AuditConfig(name="t", returns=df, n_boot=50, declaration_file=str(_decl(tmp_path, declared_at_utc=None))))


def test_declaration_after_data_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="after the audit data"):
        run_audit(AuditConfig(name="t", returns=_hedged(), n_boot=50, declaration_file=str(_decl(tmp_path)),
                              data_received_utc="2026-08-15T00:00:00Z"))


def test_v10_rejects_drawdown_objective(tmp_path):
    with pytest.raises(ValueError, match="v1.0"):
        run_audit(AuditConfig(name="t", returns=_hedged(), n_boot=50, declaration_file=str(_decl(tmp_path)),
                              rubric_version="1.0"))


def test_declaration_seal_is_verified_and_reported(tmp_path):
    from holdout_audit.seal import seal_document
    from test_seal import FakeTSA

    p = _decl(tmp_path)
    seal_document(p, tmp_path / "decl-seal", [FakeTSA("digicert"), FakeTSA("freetsa")])
    res = run_audit(AuditConfig(name="t", returns=_hedged(), n_boot=100, n_trials=1, declaration_file=str(p),
                                declaration_seal_dir=str(tmp_path / "decl-seal"),
                                data_received_utc="2026-09-10T00:00:00Z"))
    assert res.hashes["objective_declaration_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    html = render_report(res)
    assert "objective declaration seal" in html and "reduce drawdown at acceptable cost" in html
    p.write_text(p.read_text().replace("0.03", "0.05"))  # edit after sealing
    with pytest.raises(Exception):
        run_audit(AuditConfig(name="t", returns=_hedged(), n_boot=50, declaration_file=str(p),
                              declaration_seal_dir=str(tmp_path / "decl-seal")))


# ---------------------------------------------------------------- objective (b) grading


def test_drawdown_objective_passes_primary_for_partial_exposure(tmp_path):
    res = run_audit(AuditConfig(name="hedge", returns=_hedged(), n_boot=300, n_trials=1,
                                declaration_file=str(_decl(tmp_path, max_return_shortfall_annual=0.10))))
    st = {c.key: c.status for c in res.grade.checks}
    assert res.objective == OBJECTIVE_DRAWDOWN
    assert set(st) == {"dsr", "pbo", "haircut", "drawdown", "tolerance", "holdout", "stability", "costs", "surface"}
    assert st["drawdown"] == PASS and st["tolerance"] == PASS
    assert not any("Objective cap" in c for c in res.grade.caps)


def test_tolerance_breach_caps_at_c(tmp_path):
    df = _hedged()
    df["market"] = df["market"] + 0.0008  # strong benchmark drift -> large return shortfall
    df["return"] = 0.6 * df["market"]
    res = run_audit(AuditConfig(name="hedge", returns=df, n_boot=200, n_trials=1,
                                declaration_file=str(_decl(tmp_path, max_return_shortfall_annual=0.01))))
    st = {c.key: c.status for c in res.grade.checks}
    assert st["tolerance"] == FAIL
    assert res.grade.letter in "CDF"


def test_objective_cap_rule_for_drawdown():
    checks = [Check(k, k, PASS, "", "", "") for k in ("dsr", "haircut", "holdout", "stability")]
    g = grade_from_checks(checks, True, version="1.1", objective=OBJECTIVE_DRAWDOWN, objective_met=False)
    assert g.letter == "C" and g.caps == [CAP_RULES_V11[1]]
    g2 = grade_from_checks(checks, True, version="1.1", objective=OBJECTIVE_DRAWDOWN, objective_met=True)
    assert g2.letter == "A"


def test_drawdown_objective_with_variant_grid(tmp_path):
    df = _hedged(n=2400)
    m = df["market"]
    v = pd.DataFrame({f"exp={e}|lag={k}": (e * m).shift(k).fillna(0.0) if k else e * m
                      for e in (0.4, 0.6, 0.8) for k in (0, 1)}, index=df.index)
    res = run_audit(AuditConfig(name="grid", returns=df.assign(**{"return": v["exp=0.6|lag=0"]}), variants=v,
                                chosen_variant="exp=0.6|lag=0", n_boot=100,
                                declaration_file=str(_decl(tmp_path, max_return_shortfall_annual=0.10))))
    assert res.obj["pbo"] is not None and res.obj["pbo"].n_splits == 12870
    assert res.obj["surface"] is not None
    html = render_report(res)
    assert "Declared objective: drawdown reduction" in html


def test_v11_is_sealed_and_reports_cite_it(returns_df):
    from holdout_audit.rubric import rubric_seal_info
    from holdout_audit.seal import sha256_hex, verify_seal

    seal_dir = ROOT / "docs" / "rubric-seal-v1.1"
    out = verify_seal(seal_dir)
    assert out["status"] == "verified" and set(out["verified_tsas"]) == {"digicert", "freetsa"}
    assert out["subject_sha256"] == RUBRICS["1.1"]["document_sha256"]
    info = rubric_seal_info("1.1")
    assert info["status"] == "verified" and info["seal_sha256"] == sha256_hex((seal_dir / "seal.json").read_bytes())
    res = run_audit(AuditConfig(name="t", returns=returns_df, n_trials=2, n_boot=100, rubric_version="1.1"))
    assert info["seal_sha256"] in render_report(res)


def test_sealed_preregistration_is_verified_and_cited(tmp_path, returns_df):
    from holdout_audit.seal import seal_document
    from test_seal import FakeTSA

    pre = tmp_path / "prereg.json"
    pre.write_text(json.dumps({"rule": "x", "grid": [1, 2]}))
    seal_document(pre, tmp_path / "pre-seal", [FakeTSA("digicert"), FakeTSA("freetsa")])
    res = run_audit(AuditConfig(name="t", returns=returns_df, n_trials=2, n_boot=100, preregistration_file=str(pre),
                                preregistration_seal_dir=str(tmp_path / "pre-seal")))
    assert res.hashes["preregistration_sha256"] == hashlib.sha256(pre.read_bytes()).hexdigest()
    assert "preregistration seal" in render_report(res)
    pre.write_text(json.dumps({"rule": "y"}))
    with pytest.raises(Exception):
        run_audit(AuditConfig(name="t", returns=returns_df, n_boot=50, preregistration_file=str(pre),
                              preregistration_seal_dir=str(tmp_path / "pre-seal")))
