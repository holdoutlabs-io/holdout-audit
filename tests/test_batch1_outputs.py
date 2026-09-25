"""Consistency of the published Batch 1 outputs (no market data needed)."""

import hashlib
import json
from pathlib import Path

from holdout_audit.seal import verify_seal
from holdout_audit.stats.haircut import holm_adjusted

B1 = Path(__file__).resolve().parents[1] / "samples" / "batch1"


def test_prereg_sealed_and_matches_summary():
    s = json.loads((B1 / "summary.json").read_text())
    out = verify_seal(B1 / "prereg" / "seal")
    assert out["status"] == "verified" and set(out["verified_tsas"]) == {"digicert", "freetsa"}
    assert out["subject_sha256"] == s["preregistration_sha256"] == hashlib.sha256(
        (B1 / "prereg" / "batch1-preregistration.json").read_bytes()).hexdigest()
    assert out["seal_sha256"] == s["preregistration_seal_sha256"]


def test_all_twenty_published_with_holm():
    s = json.loads((B1 / "summary.json").read_text())
    rows = s["audits"]
    assert len(rows) == 20 and {r["asset"] for r in rows} == {"SPY", "BTC"}
    assert len({(r["asset"], r["strategy"]) for r in rows}) == 20
    holm = holm_adjusted([r["spa_p"] for r in rows])
    for r, h in zip(rows, holm):
        assert abs(r["spa_p_holm"] - round(float(h), 4)) < 1e-9
        assert r["survives_holm"] == (h <= 0.05)
        assert (B1 / r["report"]).exists()
    assert s["n_survive_holm"] == sum(r["survives_holm"] for r in rows)
    pre = json.loads((B1 / "prereg" / "batch1-preregistration.json").read_text(encoding="utf-8"))
    n = {p["key"]: p["n_variants"] for p in pre["strategies"]}
    assert all(r["n_variants"] == n[r["strategy"]] for r in rows)
