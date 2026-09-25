"""Command-line interface: ``holdout-audit audit|seal|verify-seal``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from holdout_audit.audit import AuditConfig, run_audit
from holdout_audit.io import load_returns, load_variants
from holdout_audit.rubric import CURRENT_VERSION
from holdout_audit.report import write_report


def _audit(a: argparse.Namespace) -> int:
    returns = load_returns(a.returns, percent=a.percent)
    variants = load_variants(a.variants, percent=a.percent) if a.variants else None
    files = {"returns_file_sha256": a.returns}
    if a.variants:
        files["variants_file_sha256"] = a.variants
    cfg = AuditConfig(
        name=a.name, returns=returns, variants=variants, chosen_variant=a.chosen, n_trials=a.n_trials,
        periods_per_year=a.periods_per_year, holdout_split=a.holdout_split, base_cost_bps=a.cost_bps,
        benchmark=a.benchmark, benchmark_reason=a.benchmark_reason, rubric_version=a.rubric_version,
        declaration_file=a.declaration, declaration_seal_dir=a.declaration_seal, data_received_utc=a.data_received, n_boot=a.n_boot, seed=a.seed, description=a.description or "", rules=a.rules or "",
        data_files=files,
    )
    res = run_audit(cfg)
    path = write_report(res, a.out)
    print(json.dumps(res.headline(), indent=2))
    print(f"report: {path}")
    return 0


def _seal(a: argparse.Namespace) -> int:
    from holdout_audit.seal import seal_preregistration

    prereg = json.loads(Path(a.prereg).read_text(encoding="utf-8"))
    res = seal_preregistration(prereg, Path(a.out_dir))
    print(json.dumps({"prereg_sha256": res.prereg_sha256, "status": res.status,
                      "receipts": [r.to_dict() for r in res.receipts]}, indent=2))
    return 0 if res.status == "verified" else 1


def _seal_doc(a: argparse.Namespace) -> int:
    from holdout_audit.seal import seal_document

    res = seal_document(Path(a.document), Path(a.out_dir))
    print(json.dumps({"subject_sha256": res.prereg_sha256, "status": res.status,
                      "seal_file": str(res.seal_path), "receipts": [r.to_dict() for r in res.receipts]}, indent=2))
    return 0 if res.status == "verified" else 1


def _verify(a: argparse.Namespace) -> int:
    from holdout_audit.seal import default_clients, verify_seal

    print(json.dumps(verify_seal(Path(a.seal_dir), default_clients()), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="holdout-audit", description="Scientific audits for trading strategies.")
    sub = p.add_subparsers(dest="cmd", required=True)

    au = sub.add_parser("audit", help="audit a return series and write an HTML report")
    au.add_argument("--returns", required=True, help="CSV of daily returns or a trade list (see docs/INPUT-FORMATS.md)")
    au.add_argument("--variants", help="CSV matrix of daily returns of every variant tried")
    au.add_argument("--chosen", help="variant column that is the audited strategy")
    au.add_argument("--n-trials", type=int, help="number of variants tried (if more than the matrix holds)")
    au.add_argument("--name", default="Strategy audit")
    au.add_argument("--description")
    au.add_argument("--rules")
    au.add_argument("--periods-per-year", type=int)
    au.add_argument("--holdout-split", help="YYYY-MM-DD; default: last 30%% of the sample")
    au.add_argument("--cost-bps", type=float, default=0.0, help="one-way cost per unit turnover (bps)")
    au.add_argument("--benchmark", choices=["auto", "zero", "market"], default="auto",
                    help="auto: buy-and-hold (market column) if present, else zero")
    au.add_argument("--benchmark-reason", default="", help="why a zero benchmark is appropriate")
    au.add_argument("--rubric-version", choices=["1.0", "1.1", "1.2"], default=CURRENT_VERSION,
                    help="1.2 (current); 1.0 and 1.1 only to reproduce reports published under them")
    au.add_argument("--declaration", help="objective declaration JSON (docs/objective-declaration-template.json)")
    au.add_argument("--declaration-seal", help="seal-doc directory sealing the declaration file (optional)")
    au.add_argument("--data-received", help="UTC time the audit data arrived; the declaration must predate it")
    au.add_argument("--n-boot", type=int, default=1000)
    au.add_argument("--seed", type=int, default=20260925)
    au.add_argument("--percent", action="store_true", help="returns are in percent, not fractions")
    au.add_argument("--out", default="audit-report.html")
    au.set_defaults(func=_audit)

    se = sub.add_parser("seal", help="preregister and RFC 3161-timestamp a forward trial (DigiCert + FreeTSA)")
    se.add_argument("prereg", help="preregistration JSON")
    se.add_argument("--out-dir", required=True)
    se.set_defaults(func=_seal)

    sd = sub.add_parser("seal-doc", help="RFC 3161-timestamp an existing document's SHA-256 (e.g. a frozen rubric)")
    sd.add_argument("document")
    sd.add_argument("--out-dir", required=True)
    sd.set_defaults(func=_seal_doc)

    ve = sub.add_parser("verify-seal", help="re-verify a sealed preregistration")
    ve.add_argument("seal_dir")
    ve.set_defaults(func=_verify)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
