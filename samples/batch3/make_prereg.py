"""Writes the Batch 3 preregistration and one objective declaration per audit (before sealing and before any fetch)."""

import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import batch3_rules as R  # noqa: E402
import spec  # noqa: E402

now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
OUT = HERE / "prereg"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audits = []
    for aid, rule, market, syms, bench, start, holdout, cost in spec.AUDITS:
        meta = spec.RULES[rule]
        decl = {"objective": meta["objective"], "max_return_shortfall_annual": meta.get("max_return_shortfall_annual"),
                "benchmark": bench, "declared_at_utc": now, "declared_by": f"holdout-labs-batch-3/{aid}",
                "source_claim": meta["claim"]}
        (OUT / f"declaration-{aid}.json").write_bytes((json.dumps(decl, indent=2) + "\n").encode("utf-8"))
        audits.append({"id": aid, "rule": rule, "market": market, "data_symbols": syms, "benchmark": bench,
                       "objective": meta["objective"], "max_return_shortfall_annual": meta.get("max_return_shortfall_annual"),
                       "audit_period": f"{start} to {spec.END}", "holdout_split": holdout, "cost_bps_per_unit_turnover": cost,
                       "n_variants": R.n_variants(rule), "declaration_file": f"declaration-{aid}.json"})
    rules = [{"key": k, **{kk: vv for kk, vv in m.items()}, "audited_variant": R.label(R.DEFAULTS[k]),
              "variant_grid": R.GRIDS[k], "n_variants": R.n_variants(k), "implementation": f"samples/batch3_rules.py ({k})"}
             for k, m in spec.RULES.items()]
    doc = {
        "title": "Holdout Labs Indicator Audit, Batch 3: Strongest published evidence (traditional markets), 6 audits",
        "written_at_utc": now,
        "rubric": "Holdout Labs Fragility Rubric v1.2 (docs/RUBRIC-v1.2.md, SHA-256 81bc60b5bf4520fdfb91c43b37883c30a9a2061903442d1e8a8b05f3d37a71fc), sealed 2026-09-25T20:33:45Z. Each audit is judged on the objective its own source claims, declared here and in a sealed per-audit declaration file: (c) improve Sharpe vs benchmark, or (b) reduce drawdown at acceptable cost.",
        "scope_policy": "Instrument policy: equity and bond ETFs only; no commodities, metals or commodity ETFs; no crypto in this batch; no astronomical features.",
        "rules": rules,
        "audits": audits,
        "data": {
            "source": "Yahoo Finance public chart endpoint (daily): split-adjusted close for signals, split- and dividend-adjusted close for total returns. Files not already on disk (EEM, TLT, VNQ, USMV, SPLV) are fetched only AFTER this document and the declarations are sealed; hashes are recorded in MANIFEST.json. Previously fetched files (SPY, EFA, IEF, sector SPDRs) are reused unchanged, with their recorded hashes.",
            "terms_and_publication": "Derived statistics only, never raw prices; no redistribution (adopted 2026-09-25).",
        },
        "execution_convention": "Monthly rules rebalance at the last trading day of each month and hold to the next. Cash earns 0% and borrowing above 100% exposure costs 0% (no T-bill series is permitted). Borrowing at 0% flatters levered variants (vol_managed caps 1.5 and 2.0; tsmom's vol-scaled bond positions) and cash at 0% penalises de-risked positions; both are stated in every report. Shorting (tsmom) has no borrow cost.",
        "settings": {"bootstrap_draws": 1000, "cscv_blocks": 16, "seed": 20260925, "periods_per_year": 252,
                     "declared_n_trials": "equal to n_variants of each rule"},
        "batch_level_inference": {
            "primary_statistic": "each audit's one-sided bootstrap p-value for its own primary objective statistic, adjusted within the audit's variant family (the rubric's multiple-testing check value: BHY when every variant is supplied): dSR for objective (c); dCVaR for objective (b).",
            "multiplicity": "Holm step-down correction across the 6 audits at family-wise alpha 0.05.",
            "survives": "An audit survives only if its Holm-adjusted p <= 0.05 AND its primary objective check (sharpe for c; drawdown and tolerance for b) is not FAIL. No rule will be described as meeting its claim unless it survives. The rubric v1.2 grade is reported for every audit regardless."},
        "publication_commitment": "All 6 results are published in samples/batch3/ and on holdoutlabs.io/audits/batch-3/, pass or fail, with every report, the summary table, this preregistration and the declarations. No audit will be dropped, re-run with different settings, or re-graded under another objective. No Batch 1, Batch 2 or sample 1-4 audit is re-graded.",
        "prior_exposure": {
            "prices_already_seen_by_us": spec.SEEN_PRICES,
            "prices_not_seen_before_this_seal": spec.UNSEEN_PRICES,
            "results_already_seen": "Samples 1-4 (SPY golden cross, SPY RSI(2), BTC SMA-50, BTC Supertrend); Batch 1 (ten TradingView built-ins on SPY and BTC); Batch 2 (ten classic rules on SPY, QQQ, IWM, EFA, IEF, AGG, sector SPDRs, ^VIX); the on-chain batch. None of these was volatility-managed, low-volatility, time-series momentum across ETFs or risk parity; Faber timing was run on SPY, EFA and IEF (Batch 2), which is why this batch's Faber audit uses only EEM, VNQ and TLT.",
            "implications": "vol_managed uses SPY and lowvol_sectors uses the sector SPDRs, whose prices and several other rules' results we have seen; tsmom includes SPY, EFA and IEF; risk parity includes SPY. The implementations were tested on synthetic data only."},
        "deviations": "Any deviation from this document will be listed on the summary page and in the affected reports.",
    }
    (OUT / "batch3-preregistration.json").write_bytes((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(len(audits), sum(a["n_variants"] for a in audits), now)


if __name__ == "__main__":
    main()
