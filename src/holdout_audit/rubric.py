"""The sealed fragility rubrics: versions, document hashes and RFC 3161 seal records.

docs/RUBRIC-v<version>.md is the normative text of each version. Its SHA-256 is pinned here;
the seal record (written by ``holdout-audit seal-doc``) is summarised in package data
``rubric_seal*.json`` so every report can cite it. Reports produced under one version are never
re-graded under another.
"""

from __future__ import annotations

import json
from pathlib import Path

RUBRICS = {
    "1.0": {"document": "docs/RUBRIC-v1.0.md",
            "document_sha256": "0c0420617f2f460d452d862b5e522171bef5e91a259a845d77449bfa115a7292",
            "seal_file": "rubric_seal.json"},
    "1.2": {"document": "docs/RUBRIC-v1.2.md",
            "document_sha256": "81bc60b5bf4520fdfb91c43b37883c30a9a2061903442d1e8a8b05f3d37a71fc",
            "seal_file": "rubric_seal_v1.2.json"},
    "1.1": {"document": "docs/RUBRIC-v1.1.md",
            "document_sha256": "2311b126336bab9f426a84f9c9cd9cb937e346b403a62f60e3c96ed8b5868e46",
            "seal_file": "rubric_seal_v1.1.json"},
}
CURRENT_VERSION = "1.2"

# Backwards-compatible names (v1.0).
RUBRIC_VERSION = "1.0"
RUBRIC_DOC = RUBRICS["1.0"]["document"]
RUBRIC_DOC_SHA256 = RUBRICS["1.0"]["document_sha256"]


def rubric_seal_info(version: str = "1.0") -> dict:
    meta = RUBRICS[version]
    info = {"version": version, "document": meta["document"], "document_sha256": meta["document_sha256"],
            "seal_sha256": None, "tsa_times": {}, "status": "unsealed"}
    path = Path(__file__).parent / meta["seal_file"]
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("subject_sha256") == meta["document_sha256"]:
            info.update(seal_sha256=rec["seal_sha256"], tsa_times=rec["tsa_times"], status=rec["status"])
    return info
