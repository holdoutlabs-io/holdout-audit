"""Rubric v1.2: objective (c) improve Sharpe vs benchmark; (a) and (b) unchanged from v1.1."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from holdout_audit import AuditConfig, run_audit
from holdout_audit.grade import (CAP_RULES_V11, CAP_RULES_V12, DECLARATION_RULE_V12, FAIL, OBJECTIVE_SHARPE, PASS,
                                 RUBRIC_RULES_V11_BEAT, RUBRIC_RULES_V11_DRAWDOWN, RUBRIC_RULES_V12_SHARPE, Check,
                                 grade_from_checks, rules_for)
from holdout_audit.report import render_report
from holdout_audit.rubric import RUBRICS
from holdout_audit.stats import objective_sharpe as S

ROOT = Path(__file__).resolve().parents[1]
DOC12 = ROOT / RUBRICS["1.2"]["document"]


def _decl(tmp_path):
    p = tmp_path / "decl.json"
    p.write_text(json.dumps({"objective": "improve_sharpe", "declared_at_utc": "2026-09-01T00:00:00Z", "declared_by": "t"}))
    return p


def _pair(n=5040, seed=0, lam=0.6, extra=0.0002):
    """Benchmark with a positive drift; strategy = de-risked benchmark plus an independent positive stream,
    so its Sharpe is higher by construction."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2005-01-03", periods=n)
    b = rng.normal(0.0003, 0.01, n)
    r = lam * b + rng.normal(extra, 0.003, n)
    return pd.DataFrame({"return": r, "turnover": 0.0, "market": b}, index=idx)


def test_v12_document_contains_every_rule():
    text = DOC12.read_text(encoding="utf-8")
    for rule in (list(RUBRIC_RULES_V11_BEAT.values()) + list(RUBRIC_RULES_V11_DRAWDOWN.values())
                 + list(RUBRIC_RULES_V12_SHARPE.values()) + CAP_RULES_V12):
        assert rule in text, rule
    assert DECLARATION_RULE_V12 in text


def test_a_and_b_unchanged_in_v12():
    assert rules_for("1.2", "beat_benchmark")[0] == rules_for("1.1", "beat_benchmark")[0]
    assert rules_for("1.2", "reduce_drawdown")[0] == rules_for("1.1", "reduce_drawdown")[0]
    assert [c for c in CAP_RULES_V12 if "improve Sharpe" not in c] == CAP_RULES_V11


def test_delta_sharpe_and_bootstrap():
    df = _pair()
    sb = S.sharpe_bootstrap(df["return"].to_numpy(), df["market"].to_numpy(), 252, n_boot=300, seed=1)
    assert sb.d_sr > 0.3 and sb.d_sr_lo > 0 and sb.p_d_sr < 0.01
    assert S.delta_sharpe(df["market"], df["market"]) == pytest.approx(0.0)


def test_pbo_delta_sharpe_true_edge_low():
    df = _pair(n=3200)
    rng = np.random.default_rng(3)
    v = np.stack([df["market"].to_numpy() * 1.0 + rng.normal(0, 0.002, 3200) for _ in range(5)] + [df["return"].to_numpy()], axis=1)
    res = S.pbo_cscv_delta_sharpe(v, df["market"].to_numpy())
    assert res.n_splits == 12870 and res.pbo < 0.2


def test_objective_c_detects_planted_improvement(tmp_path):
    df = _pair()
    res = run_audit(AuditConfig(name="c", returns=df, n_trials=1, n_boot=300, declaration_file=str(_decl(tmp_path))))
    st = {c.key: c.status for c in res.grade.checks}
    assert res.objective == OBJECTIVE_SHARPE and res.rubric["version"] == "1.2"
    assert st["sharpe"] == PASS and st["holdout"] in ("PASS", "CAUTION")
    assert "improve Sharpe vs benchmark" in render_report(res)


def test_objective_c_rejects_leverage_only(tmp_path):
    df = _pair(lam=1.5, extra=0.0)  # a levered copy of the benchmark plus noise: no Sharpe improvement
    res = run_audit(AuditConfig(name="c", returns=df, n_trials=1, n_boot=300, declaration_file=str(_decl(tmp_path))))
    st = {c.key: c.status for c in res.grade.checks}
    assert st["sharpe"] != PASS and res.grade.letter in "CDF"  # never a robust improvement


def test_objective_c_cap():
    checks = [Check(k, k, PASS, "", "", "") for k in ("dsr", "haircut", "holdout", "stability")]
    g = grade_from_checks(checks, True, version="1.2", objective=OBJECTIVE_SHARPE, objective_met=False)
    assert g.letter == "C" and g.caps == [CAP_RULES_V12[2]]


def test_objective_c_needs_v12(tmp_path):
    with pytest.raises(ValueError, match="v1.2"):
        run_audit(AuditConfig(name="c", returns=_pair(), n_boot=50, declaration_file=str(_decl(tmp_path)), rubric_version="1.1"))


def test_v12_is_sealed_pinned_and_cited(returns_df):
    from holdout_audit.rubric import rubric_seal_info
    from holdout_audit.seal import sha256_hex, verify_seal

    assert hashlib.sha256(DOC12.read_bytes()).hexdigest() == RUBRICS["1.2"]["document_sha256"]
    out = verify_seal(ROOT / "docs" / "rubric-seal-v1.2")
    assert out["status"] == "verified" and set(out["verified_tsas"]) == {"digicert", "freetsa"}
    info = rubric_seal_info("1.2")
    assert info["status"] == "verified" and info["seal_sha256"] == sha256_hex((ROOT / "docs" / "rubric-seal-v1.2" / "seal.json").read_bytes())
    res = run_audit(AuditConfig(name="t", returns=returns_df, n_trials=2, n_boot=100))
    assert res.rubric["version"] == "1.2" and info["seal_sha256"] in render_report(res)
