"""The positive-control generator plants the edges it claims (no audit statistics are tuned here)."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "samples" / "controls"))
import positive_controls as PC  # noqa: E402


def test_planted_excess_edge_and_plateau():
    # average over replicates: realised excess Sharpe of the chosen variant is close to the planted edge
    est = []
    for s in range(12):
        ret, var, ch = PC.generate("a", "clean", "plateau", 1.0, 100 + s)
        e = var[ch] - ret["market"]
        est.append(e.mean() / e.std(ddof=1) * math.sqrt(PC.PPY))
        assert ch == "p=5" and var.shape[1] == 10
    assert np.mean(est) == pytest.approx(1.0, abs=0.12)
    ret, var, ch = PC.generate("a", "clean", "plateau", 1.0, 7)
    c = np.corrcoef((var["p=5"] - ret["market"]), (var["p=6"] - ret["market"]))[0, 1]
    assert c == pytest.approx(0.9, abs=0.03)


def test_zero_edge_and_isolated_grid():
    ret, var, ch = PC.generate("a", "clean", "isolated", 1.0, 3)
    ex = (var.sub(ret["market"], axis=0)).mean() * PC.PPY
    assert ex["p=5"] > 0.03 and abs(ex.drop("p=5")).max() < 0.04


def test_overfit_picks_in_sample_best_of_50():
    ret, var, ch = PC.generate("a", "clean", "overfit", 0.0, 5)
    assert var.shape[1] == 50 and ch != "p=5"
    cut = int(PC.T * 0.7)
    ex = var.iloc[:cut].sub(ret["market"].iloc[:cut], axis=0)
    assert ch == (ex.mean() / ex.std()).idxmax()


def test_heavy_tails_and_clustering():
    x = PC.garch_t(20000, np.random.default_rng(1), 0.16)
    kurt = ((x - x.mean()) ** 4).mean() / x.var() ** 2
    assert kurt > 5  # fat tails
    a2 = np.abs(x)
    assert np.corrcoef(a2[1:], a2[:-1])[0, 1] > 0.1  # volatility clustering
    assert x.std() * math.sqrt(252) == pytest.approx(0.16, rel=0.15)


def test_objective_c_planted_sharpe_improvement():
    d = []
    for s in range(12):
        ret, var, ch = PC.generate("c", "clean", "plateau", 0.5, 200 + s)
        r, b = var[ch].to_numpy(), ret["market"].to_numpy()
        d.append((r.mean() / r.std(ddof=1) - b.mean() / b.std(ddof=1)) * math.sqrt(PC.PPY))
    assert np.mean(d) == pytest.approx(0.5, abs=0.12)


def test_sealed_protocol_pins_the_generator_and_results_are_complete():
    import hashlib
    import json

    root = Path(__file__).resolve().parents[1]
    gen = hashlib.sha256((root / "samples" / "controls" / "positive_controls.py").read_bytes()).hexdigest()
    assert gen in (root / "docs" / "positive-controls" / "PROTOCOL.md").read_text(encoding="utf-8")
    from holdout_audit.seal import verify_seal

    assert verify_seal(root / "docs" / "positive-controls" / "seal")["status"] == "verified"
    res = json.loads((root / "samples" / "controls" / "results.json").read_text())
    assert res["reps"] == 200 and len(res["cells"]) == len(PC.CELLS)
    for c in res["cells"]:
        runs = [r for r in res["runs"] if r["cell"] == c["cell"]]
        assert len(runs) == 200 and sorted(r["rep"] for r in runs) == list(range(200))
        assert abs(c["pass_AB"] - sum(r["grade"] in "AB" for r in runs) / 200) < 1e-12
