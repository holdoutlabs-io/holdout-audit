"""Consistency of the published Batch 3 outputs (no market data needed)."""

import hashlib
import json
from pathlib import Path

from holdout_audit.seal import verify_seal
from holdout_audit.stats.haircut import holm_adjusted

B3 = Path(__file__).resolve().parents[1] / "samples" / "batch3"


def test_all_seven_documents_sealed_and_matching():
    s = json.loads((B3 / "summary.json").read_text())
    pre = json.loads((B3 / "prereg" / "batch3-preregistration.json").read_text(encoding="utf-8"))
    out = verify_seal(B3 / "prereg" / "seal-batch3-preregistration")
    assert out["subject_sha256"] == s["preregistration_sha256"] and out["seal_sha256"] == s["preregistration_seal_sha256"]
    for a in pre["audits"]:
        d = verify_seal(B3 / "prereg" / f"seal-declaration-{a['id']}")
        assert d["status"] == "verified" and d["subject_sha256"] == hashlib.sha256(
            (B3 / "prereg" / a["declaration_file"]).read_bytes()).hexdigest()
        decl = json.loads((B3 / "prereg" / a["declaration_file"]).read_text())
        assert decl["objective"] == a["objective"]


def test_holm_survival_rule_and_publication():
    s = json.loads((B3 / "summary.json").read_text())
    rows = s["audits"]
    assert len(rows) == 6
    for r, h in zip(rows, holm_adjusted([r["p_primary"] for r in rows])):
        assert abs(r["p_holm"] - round(float(h), 4)) < 1e-9
        assert r["survives_holm"] == (h <= 0.05 and r["primary_ok"])
        assert (B3 / r["report"]).exists()
    assert s["n_survive_holm"] == sum(r["survives_holm"] for r in rows)
