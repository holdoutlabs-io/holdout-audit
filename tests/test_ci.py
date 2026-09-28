import re
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from holdout_audit import cli
from holdout_audit.ci import (COMMENT_MARKER, FOOTER, REPO_URL, TOOL_URL, badge_svg, below, parse_frequency)


def _write(tmp_path, n=600, mu=0.0006, seed=0, variants=True):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    market = rng.normal(0.0003, 0.01, n)
    r = 0.5 * market + mu + rng.normal(0, 0.005, n)
    rp = tmp_path / "returns.csv"
    pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "return": r, "turnover": 0.05}).to_csv(rp, index=False)
    bp = tmp_path / "bench.csv"
    pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "return": market}).to_csv(bp, index=False)
    vp = None
    if variants:
        vp = tmp_path / "variants.csv"
        cols = {f"k={k}": r + rng.normal(0, 0.002, n) for k in (1, 2, 3, 4)}
        cols["k=2"] = r
        pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), **cols}).to_csv(vp, index=False)
    return rp, bp, vp


def _run(argv, monkeypatch, tmp_path):
    summary, out = tmp_path / "summary.md", tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    code = cli.main(["ci", "--n-boot", "200", *argv])
    outputs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    return code, summary.read_text(encoding="utf-8"), outputs


def test_ci_with_variants_writes_summary_outputs_and_badge(tmp_path, monkeypatch, capsys):
    rp, bp, vp = _write(tmp_path)
    badge = tmp_path / "badges" / "holdout.svg"
    code, md, outs = _run(["--returns", str(rp), "--benchmark", str(bp), "--variants", str(vp), "--chosen", "k=2",
                           "--holdout-start", "2019-06-03", "--frequency", "daily", "--badge", str(badge),
                           "--summary-out", str(tmp_path / "c.md")], monkeypatch, tmp_path)
    assert code == 0
    assert outs["grade"] in "ABCDF" and len(outs["grade"]) == 1
    assert 0 <= float(outs["dsr"]) <= 1 and 0 <= float(outs["pbo"]) <= 1
    assert outs["n-trials"] == "4"
    assert md.startswith(COMMENT_MARKER)
    assert f"fragility grade **{outs['grade']}**" in md
    assert "Deflated Sharpe ratio (N = 4 trials)" in md and "from 2019-06-03" in md
    assert "benchmark: market" in md
    assert TOOL_URL in md and REPO_URL in md and FOOTER in md
    assert (tmp_path / "c.md").read_text(encoding="utf-8").strip() == md.strip()
    assert md.strip() in capsys.readouterr().out
    svg = badge.read_text(encoding="utf-8")
    ET.fromstring(svg)  # well-formed
    assert ">holdout grade<" in svg and f">{outs['grade']}<" in svg and TOOL_URL in svg


def test_ci_matches_audit_pipeline(tmp_path, monkeypatch):
    """The ci subcommand reuses run_audit: same inputs, same grade and DSR."""
    from holdout_audit.audit import AuditConfig, run_audit
    from holdout_audit.io import load_returns

    rp, _, _ = _write(tmp_path, variants=False)
    code, md, outs = _run(["--returns", str(rp), "--n-trials", "20"], monkeypatch, tmp_path)
    res = run_audit(AuditConfig(name="x", returns=load_returns(rp), n_trials=20, n_boot=200))
    assert code == 0
    assert outs["grade"] == res.grade.letter and float(outs["dsr"]) == pytest.approx(res.dsr, abs=1e-4)
    assert outs["pbo"] == "" and "not computed (no variants file)" in md
    assert "N = 20 trials" in md


def test_fail_below(tmp_path, monkeypatch):
    rp, _, _ = _write(tmp_path, mu=-0.0005, variants=False)  # losing noise: grade D or F
    code, _, outs = _run(["--returns", str(rp), "--fail-below", "c"], monkeypatch, tmp_path)
    assert outs["grade"] in "DF" and code == 1
    code, _, _ = _run(["--returns", str(rp), "--fail-below", "F"], monkeypatch, tmp_path)
    assert code == 0


def test_no_advice_wording(tmp_path, monkeypatch):
    rp, _, _ = _write(tmp_path, variants=False)
    _, md, _ = _run(["--returns", str(rp)], monkeypatch, tmp_path)
    low = md.lower()
    for bad in ("buy ", "sell ", "recommend", "profitable", "will make", "guarantee"):
        assert bad not in low
    assert "not a forecast" in low


def test_helpers():
    assert parse_frequency("auto") is None and parse_frequency("") is None
    assert parse_frequency("weekly") == 52 and parse_frequency("365") == 365
    with pytest.raises(ValueError):
        parse_frequency("hourly-ish")
    assert below("D", "C") and not below("C", "C") and not below("A", "F")
    for g in "ABCDF":
        svg = badge_svg(g)
        ET.fromstring(svg)
        width = int(re.search(r'<svg[^>]* width="(\d+)"', svg).group(1))
        assert 90 < width < 130
