"""Consistency of the published Batch 2 outputs (no market data needed)."""

import hashlib
import json
from pathlib import Path

from holdout_audit.seal import verify_seal
from holdout_audit.stats.haircut import holm_adjusted

B2 = Path(__file__).resolve().parents[1] / "samples" / "batch2"


def test_prereg_sealed_and_matches_summary():
    s = json.loads((B2 / "summary.json").read_text())
    out = verify_seal(B2 / "prereg" / "seal")
    assert out["status"] == "verified" and set(out["verified_tsas"]) == {"digicert", "freetsa"}
    assert out["subject_sha256"] == s["preregistration_sha256"] == hashlib.sha256(
        (B2 / "prereg" / "batch2-preregistration.json").read_bytes()).hexdigest()
    assert out["seal_sha256"] == s["preregistration_seal_sha256"]


def test_all_audits_published_with_holm_and_no_crypto():
    s = json.loads((B2 / "summary.json").read_text())
    pre = json.loads((B2 / "prereg" / "batch2-preregistration.json").read_text(encoding="utf-8"))
    rows = s["audits"]
    assert [r["id"] for r in rows] == [a["id"] for a in pre["audits"]]
    for r, h in zip(rows, holm_adjusted([r["spa_p"] for r in rows])):
        assert abs(r["spa_p_holm"] - round(float(h), 4)) < 1e-9 and r["survives_holm"] == (h <= 0.05)
        assert (B2 / r["report"]).exists()
    assert s["n_survive_holm"] == sum(r["survives_holm"] for r in rows)
    assert not any("BTC" in sym for a in pre["audits"] for sym in a["data_symbols"])
