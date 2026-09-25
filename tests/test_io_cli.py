import json

import numpy as np
import pandas as pd
import pytest

from holdout_audit import cli
from holdout_audit.io import infer_periods_per_year, load_returns, load_variants, trades_to_daily


def _write_returns(path, n=400, percent=False):
    idx = pd.bdate_range("2018-01-01", periods=n)
    r = np.random.default_rng(0).normal(0.0005, 0.01, n) * (100 if percent else 1)
    pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "return": r, "turnover": 0.1}).to_csv(path, index=False)


def test_load_returns(tmp_path):
    p = tmp_path / "r.csv"
    _write_returns(p)
    df = load_returns(p)
    assert list(df.columns) == ["return", "turnover"] and len(df) == 400
    assert df.index.is_monotonic_increasing


def test_percent_guard(tmp_path):
    p = tmp_path / "r.csv"
    idx = pd.bdate_range("2018-01-01", periods=100)
    pd.DataFrame({"date": idx, "return": np.full(100, 5.0)}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="percent"):
        load_returns(p)
    assert load_returns(p, percent=True)["return"].iloc[0] == pytest.approx(0.05)


def test_too_short(tmp_path):
    p = tmp_path / "r.csv"
    _write_returns(p, n=30)
    with pytest.raises(ValueError, match="60"):
        load_returns(p)


def test_trade_list_conversion(tmp_path):
    trades = pd.DataFrame({"entry_date": ["2020-01-06", "2020-02-03"], "exit_date": ["2020-01-10", "2020-02-05"],
                           "return": [0.05, -0.02]})
    daily = trades_to_daily(trades)
    assert np.prod(1 + daily.loc["2020-01-06":"2020-01-10", "return"]) - 1 == pytest.approx(0.05)
    assert np.prod(1 + daily.loc["2020-02-03":"2020-02-05", "return"]) - 1 == pytest.approx(-0.02)
    assert daily["turnover"].sum() == 4


def test_load_variants(tmp_path):
    p = tmp_path / "v.csv"
    idx = pd.bdate_range("2018-01-01", periods=100)
    pd.DataFrame({"date": idx, "a=1": 0.0, "a=2": 0.001}).to_csv(p, index=False)
    v = load_variants(p)
    assert v.shape == (100, 2)


def test_infer_ppy():
    assert infer_periods_per_year(pd.bdate_range("2020-01-01", periods=50)) == 252
    assert infer_periods_per_year(pd.date_range("2020-01-01", periods=50)) == 365
    assert infer_periods_per_year(pd.date_range("2020-01-01", periods=50, freq="MS")) == 12


def test_cli_audit(tmp_path, capsys):
    p = tmp_path / "r.csv"
    _write_returns(p, n=800)
    out = tmp_path / "rep.html"
    rc = cli.main(["audit", "--returns", str(p), "--n-trials", "3", "--n-boot", "100", "--out", str(out),
                   "--cost-bps", "1"])
    assert rc == 0 and out.exists()
    text = capsys.readouterr().out
    head = json.loads(text[: text.index("report:")])
    assert head["n_trials"] == 3


def test_cli_audit_with_drawdown_declaration(tmp_path, capsys):
    idx = pd.bdate_range("2015-01-01", periods=900)
    m = np.random.default_rng(1).standard_t(4, 900) * 0.008 + 0.0004
    p = tmp_path / "r.csv"
    pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "return": 0.5 * m, "turnover": 0.0, "market": m}).to_csv(p, index=False)
    d = tmp_path / "decl.json"
    d.write_text(json.dumps({"objective": "reduce_drawdown", "max_return_shortfall_annual": 0.08,
                             "declared_at_utc": "2026-09-01T00:00:00Z", "declared_by": "c-1"}))
    out = tmp_path / "rep.html"
    rc = cli.main(["audit", "--returns", str(p), "--n-trials", "1", "--n-boot", "100", "--out", str(out),
                   "--declaration", str(d), "--data-received", "2026-09-02T00:00:00Z"])
    text = capsys.readouterr().out
    head = json.loads(text[: text.index("report:")])
    assert rc == 0 and head["objective"] == "reduce_drawdown" and head["rubric_version"] == "1.2"


def test_cli_defaults_to_current_rubric(tmp_path, capsys):
    from holdout_audit.rubric import CURRENT_VERSION

    p = tmp_path / "r.csv"
    _write_returns(p, n=600)
    cli.main(["audit", "--returns", str(p), "--n-trials", "2", "--n-boot", "100", "--out", str(tmp_path / "a.html")])
    text = capsys.readouterr().out
    assert json.loads(text[: text.index("report:")])["rubric_version"] == CURRENT_VERSION == "1.2"
